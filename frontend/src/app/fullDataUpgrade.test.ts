import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createFullDataUpgradeController,
  FullDataUpgradeTimeoutError,
  type FullDataUpgradeSnapshot,
} from "./fullDataUpgrade";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("full data upgrade controller", () => {
  it("keeps concurrent and rerender-triggered ensures single-flight, then reuses the cached value", async () => {
    const request = deferred<{ mode: string }>();
    const load = vi.fn(() => request.promise);
    const transitions: FullDataUpgradeSnapshot[] = [];
    const controller = createFullDataUpgradeController({
      load,
      timeoutMs: 30_000,
      onTransition: (snapshot) => transitions.push(snapshot),
    });

    const first = controller.ensure();
    const second = controller.ensure();
    expect(second).toBe(first);
    await Promise.resolve();
    expect(load).toHaveBeenCalledTimes(1);
    expect(controller.getSnapshot()).toMatchObject({
      mode: "loading-full",
      requestGeneration: 1,
      fullLoadStartCount: 1,
      settleResult: null,
    });

    request.resolve({ mode: "full" });
    await expect(first).resolves.toEqual({ mode: "full" });
    expect(controller.getSnapshot()).toMatchObject({
      mode: "full",
      requestGeneration: 1,
      fullLoadStartCount: 1,
      settleResult: "success",
    });
    await expect(controller.ensure()).resolves.toEqual({ mode: "full" });
    expect(load).toHaveBeenCalledTimes(1);
    expect(transitions.map((snapshot) => snapshot.mode)).toEqual(["idle", "loading-full", "full"]);
  });

  it("settles failures as full-error and starts a new request only when retried", async () => {
    const load = vi.fn()
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValueOnce("full-data");
    const controller = createFullDataUpgradeController({ load, timeoutMs: 30_000 });

    await expect(controller.ensure()).rejects.toThrow("network unavailable");
    expect(controller.getSnapshot()).toMatchObject({
      mode: "full-error",
      requestGeneration: 1,
      fullLoadStartCount: 1,
      settleResult: "error",
    });

    await expect(controller.ensure()).resolves.toBe("full-data");
    expect(load).toHaveBeenCalledTimes(2);
    expect(controller.getSnapshot()).toMatchObject({
      mode: "full",
      requestGeneration: 2,
      fullLoadStartCount: 2,
      settleResult: "success",
    });
  });

  it("aborts a stalled request at the bounded timeout and permits a successful retry", async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    const load = vi.fn()
      .mockImplementationOnce((signal: AbortSignal) => {
        signals.push(signal);
        return new Promise<string>(() => undefined);
      })
      .mockResolvedValueOnce("retried-full-data");
    const controller = createFullDataUpgradeController({ load, timeoutMs: 1_000 });

    const timedOut = controller.ensure();
    const rejection = expect(timedOut).rejects.toBeInstanceOf(FullDataUpgradeTimeoutError);
    await vi.advanceTimersByTimeAsync(1_000);
    await rejection;
    expect(signals[0]?.aborted).toBe(true);
    expect(controller.getSnapshot()).toMatchObject({
      mode: "full-error",
      requestGeneration: 1,
      fullLoadStartCount: 1,
      settleResult: "timeout",
    });

    await expect(controller.ensure()).resolves.toBe("retried-full-data");
    expect(load).toHaveBeenCalledTimes(2);
    expect(controller.getSnapshot()).toMatchObject({
      mode: "full",
      requestGeneration: 2,
      fullLoadStartCount: 2,
      settleResult: "success",
    });
  });
});
