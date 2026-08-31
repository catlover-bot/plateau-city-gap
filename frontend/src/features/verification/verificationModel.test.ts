import { describe, expect, it } from "vitest";
import { investigationFixture } from "../investigation/investigationFixture";
import { buildInvestigationWorkspace } from "../investigation/investigationModel";
import {
  buildPublicVerificationLoop,
  PUBLIC_SPATIAL_PACK_ID,
} from "./verificationModel";

describe("public verification loop", () => {
  const workspace = buildInvestigationWorkspace(investigationFixture());
  const detailed = workspace.candidates[0];

  it("derives at most four deterministic unverified tasks", () => {
    const first = buildPublicVerificationLoop(detailed);
    const second = buildPublicVerificationLoop(detailed);
    expect(first).toEqual(second);
    expect(first.tasks).toHaveLength(4);
    expect(first.tasks.every((task) => task.status === "unverified")).toBe(true);
  });

  it("keeps every required checklist bounded to three through five items", () => {
    const loop = buildPublicVerificationLoop(detailed);
    expect(loop.tasks.every((task) =>
      task.requirements.length >= 3 && task.requirements.length <= 5,
    )).toBe(true);
  });

  it("links the detailed candidate to tracked real object ids", () => {
    const loop = buildPublicVerificationLoop(detailed);
    const targets = loop.tasks.flatMap((task) => task.targets);
    expect(targets).toEqual(expect.arrayContaining([
      expect.objectContaining({
        sourceObjectId: "bus-071",
        spatialPackId: PUBLIC_SPATIAL_PACK_ID,
      }),
      expect.objectContaining({
        sourceObjectId: "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0",
        objectType: "road",
        isPlateauObject: true,
      }),
      expect.objectContaining({
        sourceObjectId: "bldg_00962182-17d0-4fde-8970-784dd489dcf5",
        objectType: "building",
        isPlateauObject: true,
      }),
      expect.objectContaining({ sourceObjectId: "medical-105" }),
    ]));
  });

  it("uses only the candidate mesh when PLATEAU coverage is unavailable", () => {
    const loop = buildPublicVerificationLoop(workspace.candidates[1]);
    expect(loop.tasks.flatMap((task) => task.targets).every((target) =>
      target.scope === "mesh" &&
      target.sourceObjectId === workspace.candidates[1].meshCode &&
      target.spatialPackId === null,
    )).toBe(true);
  });
});
