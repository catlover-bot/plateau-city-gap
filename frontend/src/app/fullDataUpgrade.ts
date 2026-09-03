export const FULL_MAIZURU_DATA_TIMEOUT_MS = 30_000;

export type FullDataUpgradeMode = "idle" | "loading-full" | "full" | "full-error";
export type FullDataUpgradeSettleResult = null | "success" | "error" | "timeout";

export interface FullDataUpgradeSnapshot {
  mode: FullDataUpgradeMode;
  requestGeneration: number;
  fullLoadStartCount: number;
  settleResult: FullDataUpgradeSettleResult;
  timeoutMs: number;
}

export interface FullDataUpgradeController<T> {
  ensure(): Promise<T>;
  getSnapshot(): FullDataUpgradeSnapshot;
  hasCachedValue(): boolean;
}

interface FullDataUpgradeOptions<T> {
  load(signal: AbortSignal): Promise<T>;
  timeoutMs: number;
  onTransition?(snapshot: FullDataUpgradeSnapshot): void;
}

export class FullDataUpgradeTimeoutError extends Error {
  constructor(readonly timeoutMs: number) {
    super(`Full data load timed out after ${timeoutMs} ms`);
    this.name = "FullDataUpgradeTimeoutError";
  }
}

export function createFullDataUpgradeController<T>({
  load,
  timeoutMs,
  onTransition,
}: FullDataUpgradeOptions<T>): FullDataUpgradeController<T> {
  let snapshot: FullDataUpgradeSnapshot = {
    mode: "idle",
    requestGeneration: 0,
    fullLoadStartCount: 0,
    settleResult: null,
    timeoutMs,
  };
  let inFlight: Promise<T> | null = null;
  let cachedValue: T | undefined;
  let hasCachedValue = false;

  const transition = (next: FullDataUpgradeSnapshot) => {
    snapshot = { ...next };
    onTransition?.({ ...snapshot });
  };

  onTransition?.({ ...snapshot });

  const ensure = (): Promise<T> => {
    if (hasCachedValue) return Promise.resolve(cachedValue as T);
    if (inFlight) return inFlight;

    const requestGeneration = snapshot.requestGeneration + 1;
    const controller = new AbortController();
    let timedOut = false;
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;

    transition({
      mode: "loading-full",
      requestGeneration,
      fullLoadStartCount: snapshot.fullLoadStartCount + 1,
      settleResult: null,
      timeoutMs,
    });

    const timeout = new Promise<T>((_resolve, reject) => {
      timeoutHandle = setTimeout(() => {
        timedOut = true;
        controller.abort();
        reject(new FullDataUpgradeTimeoutError(timeoutMs));
      }, timeoutMs);
    });
    const request = Promise.resolve().then(() => load(controller.signal));

    const settled = Promise.race([request, timeout])
      .then((value) => {
        cachedValue = value;
        hasCachedValue = true;
        transition({
          mode: "full",
          requestGeneration,
          fullLoadStartCount: snapshot.fullLoadStartCount,
          settleResult: "success",
          timeoutMs,
        });
        return value;
      })
      .catch((reason: unknown) => {
        const timeoutError = timedOut || reason instanceof FullDataUpgradeTimeoutError;
        transition({
          mode: "full-error",
          requestGeneration,
          fullLoadStartCount: snapshot.fullLoadStartCount,
          settleResult: timeoutError ? "timeout" : "error",
          timeoutMs,
        });
        if (timeoutError && !(reason instanceof FullDataUpgradeTimeoutError)) {
          throw new FullDataUpgradeTimeoutError(timeoutMs);
        }
        throw reason;
      })
      .finally(() => {
        if (timeoutHandle !== null) clearTimeout(timeoutHandle);
        if (snapshot.requestGeneration === requestGeneration) inFlight = null;
      });

    inFlight = settled;
    return settled;
  };

  return {
    ensure,
    getSnapshot: () => ({ ...snapshot }),
    hasCachedValue: () => hasCachedValue,
  };
}

declare global {
  interface Window {
    __cityGapFullDataUpgrade?: FullDataUpgradeSnapshot;
  }
}
