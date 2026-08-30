import { describe, expect, it } from "vitest";
import {
  applySyncResponse,
  saveLocalInvestigationSheet,
  type LocalInvestigationSheet,
  type QueuedFieldOperation,
} from "./fieldOffline";

const operation: QueuedFieldOperation = {
  client_operation_id: "op-1",
  offline_package_id: "package-1",
  organization_id: "organization-1",
  city_key: "maizuru",
  scenario_run_id: "scenario-1",
  site_order: 1,
  base_record_version: 3,
  client_updated_at: "2026-08-28T12:00:00+09:00",
  payload: { notes: "現地確認" },
  status: "pending",
};

describe("offline field conflict boundary", () => {
  it("keeps HTTP 409 as an explicit unresolved conflict", () => {
    expect(
      applySyncResponse(operation, 409, {
        conflict_id: "conflict-1",
        silent_last_write_wins: false,
      }),
    ).toEqual({ ...operation, status: "conflict", conflict_id: "conflict-1" });
  });

  it("rejects a conflict response that could hide last-write-wins", () => {
    expect(() =>
      applySyncResponse(operation, 409, {
        conflict_id: "conflict-1",
        silent_last_write_wins: true,
      }),
    ).toThrow("明示的なconflict応答");
  });

  it("refuses to persist field notes with a public classification", async () => {
    const invalid = {
      sheet_id: "sheet-1",
      candidate_id: "maizuru-533513314",
      updated_at: "2026-08-30T00:00:00Z",
      classification: "public",
      content: { generalNote: "内部メモ" },
    } as unknown as LocalInvestigationSheet;

    await expect(saveLocalInvestigationSheet(invalid)).rejects.toThrow(
      "現地メモをpublic分類では保存できません",
    );
  });
});
