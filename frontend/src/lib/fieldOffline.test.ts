import { describe, expect, it } from "vitest";
import { applySyncResponse, type QueuedFieldOperation } from "./fieldOffline";

const operation: QueuedFieldOperation = {
  client_operation_id: "op-1",
  offline_package_id: "package-1",
  base_record_version: 3,
  payload: { notes: "現地確認" },
  status: "pending"
};

describe("offline field conflict boundary", () => {
  it("keeps HTTP 409 as an explicit unresolved conflict", () => {
    expect(applySyncResponse(operation, 409, {
      conflict_id: "conflict-1",
      silent_last_write_wins: false
    })).toEqual({ ...operation, status: "conflict", conflict_id: "conflict-1" });
  });

  it("rejects a conflict response that could hide last-write-wins", () => {
    expect(() => applySyncResponse(operation, 409, {
      conflict_id: "conflict-1",
      silent_last_write_wins: true
    })).toThrow("明示的なconflict応答");
  });
});
