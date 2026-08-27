"""Small PostgreSQL-backed worker with durable claims, retries and stage events."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Protocol

from backend.citygap_platform.domain.jobs import JOB_STAGES


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job_id: str
    job_type: str
    parameters: dict[str, Any]
    attempt_number: int
    city_id: str


class StageExecutor(Protocol):
    def execute(self, job: ClaimedJob, stage: str) -> None: ...


class ConfiguredCommandExecutor:
    """Run only operator-configured argv; job payloads can never provide commands."""

    def execute(self, job: ClaimedJob, stage: str) -> None:
        variable = f"CITYGAP_JOB_{job.job_type}_{stage}_COMMAND".upper()
        configured = os.getenv(variable)
        if not configured:
            raise RuntimeError(f"Required worker stage is not configured: {variable}")
        environment = os.environ.copy()
        environment.update(
            {
                "CITYGAP_JOB_ID": job.job_id,
                "CITYGAP_JOB_TYPE": job.job_type,
                "CITYGAP_JOB_STAGE": stage,
                "CITYGAP_JOB_ATTEMPT": str(job.attempt_number),
            }
        )
        timeout = int(os.getenv("CITYGAP_JOB_STAGE_TIMEOUT_SECONDS", "3600"))
        subprocess.run(
            shlex.split(configured),
            check=True,
            timeout=timeout,
            env=environment,
            shell=False,
        )


class PostgresWorker:
    def __init__(
        self,
        database_url: str,
        worker_id: str,
        stale_after_seconds: int | None = None,
    ):
        self.database_url = database_url
        self.worker_id = worker_id
        stage_timeout = int(os.getenv("CITYGAP_JOB_STAGE_TIMEOUT_SECONDS", "3600"))
        self.stale_after_seconds = (
            stale_after_seconds
            if stale_after_seconds is not None
            else int(os.getenv("CITYGAP_JOB_STALE_AFTER_SECONDS", str(stage_timeout + 300)))
        )
        if self.stale_after_seconds <= 0:
            raise ValueError("Job stale timeout must be positive")

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def _recover_stale(self, connection) -> int:
        """Requeue or fail abandoned claims under row locks.

        The timeout defaults to longer than the configured per-stage process timeout,
        so another worker cannot reclaim a legitimate bounded stage prematurely.
        """

        rows = connection.execute(
            """SELECT job.id, job.retry_count, job.max_retries, job.current_stage,
                      job.locked_by, city.city_code
               FROM job_runs AS job JOIN cities AS city ON city.id=job.city_id
               WHERE job.state = 'running'
                 AND COALESCE(job.last_heartbeat_at, job.started_at, job.queued_at)
                     < now() - (%s * interval '1 second')
               ORDER BY COALESCE(job.last_heartbeat_at, job.started_at, job.queued_at), job.id
               FOR UPDATE OF job SKIP LOCKED""",
            (self.stale_after_seconds,),
        ).fetchall()
        for job_id, retry_count, max_retries, current_stage, previous_worker, city_id in rows:
            retry = int(retry_count) < int(max_retries)
            state = "queued" if retry else "failed"
            attempt_result = "requeued" if retry else "failed"
            next_retry_count = int(retry_count) + (1 if retry else 0)
            message = (
                f"Worker heartbeat expired after {self.stale_after_seconds} seconds; "
                f"previous worker={previous_worker or 'unknown'}"
            )[:4000]
            connection.execute(
                """UPDATE job_runs SET state=%s, current_stage=NULL, retry_count=%s,
                          queued_at=CASE WHEN %s THEN now() ELSE queued_at END,
                          started_at=CASE WHEN %s THEN NULL ELSE started_at END,
                          completed_at=CASE WHEN %s THEN NULL ELSE now() END,
                          finished_at=CASE WHEN %s THEN NULL ELSE now() END,
                          locked_by=NULL, last_heartbeat_at=now(), error_message=%s
                   WHERE id=%s""",
                (
                    state,
                    next_retry_count,
                    retry,
                    retry,
                    retry,
                    retry,
                    message,
                    job_id,
                ),
            )
            connection.execute(
                """UPDATE job_attempts SET finished_at=now(), result=%s, error_message=%s
                   WHERE job_run_id=%s AND finished_at IS NULL""",
                (attempt_result, message, job_id),
            )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, stage, message)
                   VALUES (%s, %s, %s, %s)""",
                (job_id, state, current_stage, message),
            )
            connection.execute(
                """INSERT INTO audit_log (
                       actor, action, resource_type, resource_id, city_id, request_id,
                       before_state, after_state
                   ) VALUES (%s, 'job.stale.recover', 'job', %s, %s, %s, %s, %s)""",
                (
                    f"worker:{self.worker_id}"[:200],
                    str(job_id),
                    str(city_id),
                    f"worker-recovery:{job_id}"[:200],
                    json.dumps(
                        {
                            "state": "running",
                            "stage": current_stage,
                            "worker": previous_worker,
                            "retry_count": int(retry_count),
                        }
                    ),
                    json.dumps(
                        {
                            "state": state,
                            "stage": None,
                            "retry_count": next_retry_count,
                        }
                    ),
                ),
            )
        return len(rows)

    def _audit_job(
        self,
        connection,
        job: ClaimedJob,
        action: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        connection.execute(
            """INSERT INTO audit_log (
                   actor, action, resource_type, resource_id, city_id, request_id,
                   before_state, after_state
               ) VALUES (%s,%s,'job',%s,%s,%s,%s,%s)""",
            (
                f"worker:{self.worker_id}"[:200],
                action,
                job.job_id,
                job.city_id,
                f"worker:{job.job_id}:{job.attempt_number}"[:200],
                json.dumps(before),
                json.dumps(after),
            ),
        )

    def recover_stale(self) -> int:
        with self._connect() as connection:
            recovered = self._recover_stale(connection)
            connection.commit()
        return recovered

    def claim(self) -> ClaimedJob | None:
        with self._connect() as connection:
            self._recover_stale(connection)
            row = connection.execute(
                """SELECT job.id, job.job_type, job.parameters, job.retry_count,
                          city.city_code
                   FROM job_runs AS job JOIN cities AS city ON city.id=job.city_id
                   WHERE job.state = 'queued'
                   ORDER BY job.queued_at, job.id
                   FOR UPDATE OF job SKIP LOCKED LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            attempt = int(row[3]) + 1
            connection.execute(
                """UPDATE job_runs SET state = 'running', current_stage = %s,
                          started_at = now(), completed_at = NULL, finished_at = NULL,
                          last_heartbeat_at = now(), locked_by = %s, error_message = NULL
                   WHERE id = %s""",
                (JOB_STAGES[str(row[1])][0], self.worker_id, row[0]),
            )
            connection.execute(
                """INSERT INTO job_attempts (job_run_id, attempt_number, worker_id)
                   VALUES (%s, %s, %s)""",
                (row[0], attempt, self.worker_id),
            )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, stage, message)
                   VALUES (%s, 'running', %s, %s)""",
                (row[0], JOB_STAGES[str(row[1])][0], f"claimed by {self.worker_id}"),
            )
            claimed = ClaimedJob(
                str(row[0]), str(row[1]), dict(row[2]), attempt, str(row[4])
            )
            self._audit_job(
                connection,
                claimed,
                "job.start",
                {"state": "queued", "retry_count": int(row[3])},
                {
                    "state": "running",
                    "stage": JOB_STAGES[str(row[1])][0],
                    "attempt_number": attempt,
                },
            )
            connection.commit()
        return claimed

    def _stage_complete(self, job: ClaimedJob, stage: str, next_stage: str | None) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state, current_stage, locked_by FROM job_runs WHERE id=%s FOR UPDATE",
                (job.job_id,),
            ).fetchone()
            if row != ("running", stage, self.worker_id):
                raise RuntimeError("Job claim or stage changed while worker was executing")
            if next_stage is None:
                connection.execute(
                    """UPDATE job_runs SET state='succeeded', current_stage=NULL,
                              completed_at=now(), finished_at=now(), last_heartbeat_at=now(),
                              locked_by=NULL, error_message=NULL WHERE id=%s""",
                    (job.job_id,),
                )
                state = "succeeded"
                message = "all declared stages completed"
                connection.execute(
                    """UPDATE job_attempts SET finished_at=now(), result='succeeded'
                       WHERE job_run_id=%s AND attempt_number=%s""",
                    (job.job_id, job.attempt_number),
                )
                self._audit_job(
                    connection,
                    job,
                    "job.succeed",
                    {"state": "running", "stage": stage},
                    {"state": "succeeded", "stage": None},
                )
            else:
                connection.execute(
                    """UPDATE job_runs SET current_stage=%s, last_heartbeat_at=now()
                       WHERE id=%s""",
                    (next_stage, job.job_id),
                )
                state = "running"
                message = f"completed {stage}"
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, stage, message)
                   VALUES (%s, %s, %s, %s)""",
                (job.job_id, state, next_stage, message),
            )
            connection.commit()

    def _fail(self, job: ClaimedJob, error: Exception) -> None:
        message = f"{type(error).__name__}: {error}"[:4000]
        with self._connect() as connection:
            row = connection.execute(
                """SELECT retry_count, max_retries FROM job_runs
                   WHERE id=%s AND locked_by=%s FOR UPDATE""",
                (job.job_id, self.worker_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed job is no longer owned by this worker")
            retry_count, max_retries = map(int, row)
            retry = retry_count < max_retries
            state = "queued" if retry else "failed"
            result = "requeued" if retry else "failed"
            connection.execute(
                """UPDATE job_runs SET state=%s, current_stage=NULL, retry_count=%s,
                          started_at=CASE WHEN %s THEN NULL ELSE started_at END,
                          completed_at=CASE WHEN %s THEN NULL ELSE now() END,
                          finished_at=CASE WHEN %s THEN NULL ELSE now() END,
                          locked_by=NULL, last_heartbeat_at=now(), error_message=%s
                   WHERE id=%s""",
                (
                    state,
                    retry_count + (1 if retry else 0),
                    retry,
                    retry,
                    retry,
                    message,
                    job.job_id,
                ),
            )
            connection.execute(
                """UPDATE job_attempts SET finished_at=now(), result=%s, error_message=%s
                   WHERE job_run_id=%s AND attempt_number=%s""",
                (result, message, job.job_id, job.attempt_number),
            )
            connection.execute(
                """INSERT INTO job_events (job_run_id, state, message)
                   VALUES (%s, %s, %s)""",
                (job.job_id, state, message),
            )
            self._audit_job(
                connection,
                job,
                "job.retry" if retry else "job.fail",
                {"state": "running"},
                {
                    "state": state,
                    "retry_count": retry_count + (1 if retry else 0),
                    "error": message,
                },
            )
            connection.commit()

    def run_once(self, executor: StageExecutor) -> bool:
        job = self.claim()
        if job is None:
            return False
        stages = JOB_STAGES[job.job_type]
        try:
            for index, stage in enumerate(stages):
                executor.execute(job, stage)
                next_stage = stages[index + 1] if index + 1 < len(stages) else None
                self._stage_complete(job, stage, next_stage)
        except Exception as error:  # noqa: BLE001 - every task failure must become durable state
            self._fail(job, error)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="CITY GAP PostgreSQL worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    database_url = os.getenv("CITYGAP_DATABASE_URL")
    if not database_url:
        raise SystemExit("CITYGAP_DATABASE_URL is required")
    worker_id = os.getenv("CITYGAP_WORKER_ID", f"{socket.gethostname()}:{os.getpid()}")
    worker = PostgresWorker(database_url, worker_id)
    executor = ConfiguredCommandExecutor()
    while True:
        handled = worker.run_once(executor)
        if args.once:
            break
        if not handled:
            time.sleep(max(args.poll_seconds, 0.1))


if __name__ == "__main__":
    main()
