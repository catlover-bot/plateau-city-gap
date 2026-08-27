"""Small PostgreSQL-backed worker with durable claims, retries and stage events."""

from __future__ import annotations

import argparse
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
    def __init__(self, database_url: str, worker_id: str):
        self.database_url = database_url
        self.worker_id = worker_id

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def claim(self) -> ClaimedJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, job_type, parameters, retry_count
                   FROM job_runs WHERE state = 'queued'
                   ORDER BY queued_at, id FOR UPDATE SKIP LOCKED LIMIT 1"""
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
            connection.commit()
        return ClaimedJob(str(row[0]), str(row[1]), dict(row[2]), attempt)

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
