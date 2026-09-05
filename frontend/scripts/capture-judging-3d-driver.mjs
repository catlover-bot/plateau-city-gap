import { readFile, readdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
const hash = (buffer) => createHash("sha256").update(buffer).digest("hex");

// The clean master is captured once; captions are applied offline afterward.
// This driver uses only production UI controls, actual mouse camera movement,
// and real Cesium scene picking. It never edits layer visibility or app data.
export default async function run({ page, context, viewport, directory, mode, sourceUrl, sourceCommit, pagesRun, helpers }) {
  const { waitForReal3D, sceneEvidence, createNativeScreencast, clickFeaturedBuilding, moveRealCamera, pause, monotonicMilliseconds } = helpers;
  if (!sourceUrl || !sourceCommit || !pagesRun) throw new Error("Explicit production URL, UI commit, and Pages run are required");
  const url = new URL(sourceUrl);
  if (url.origin !== "https://catlover-bot.github.io" || !url.pathname.startsWith("/plateau-city-gap/")) throw new Error("Final capture must use the deployed production service");
  const rootUrl = new URL("/plateau-city-gap/", url);
  process.stdout.write("[capture] verify production metadata and build\n");
  const metadata = await (await context.request.get(new URL("data/plateau/metadata.json", rootUrl).href, { timeout: 30_000 })).json();
  const liveIndex = await (await context.request.get(rootUrl.href, { timeout: 30_000 })).body();
  const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist");
  if (!(await readFile(path.join(dist, "index.html"))).equals(liveIndex)) throw new Error("Live production index differs from the declared local UI build");
  const assets = [];
  for (const filename of (await readdir(path.join(dist, "assets"))).filter((value) => /\.(js|css)$/.test(value))) {
    const assetPath = `assets/${filename}`;
    const bytes = await (await context.request.get(new URL(assetPath, rootUrl).href, { timeout: 30_000 })).body();
    if (!(await readFile(path.join(dist, assetPath))).equals(bytes)) throw new Error(`Live built asset differs, including lazy 3D chunks: ${assetPath}`);
    assets.push({ path: assetPath, bytes: bytes.length, sha256: hash(bytes), matches_local_build: true });
  }
  process.stdout.write(`[capture] live index and ${assets.length} JS/CSS assets match; prewarm 3D\n`);
  const evidence = {
    production_url: url.href, ui_source_commit: sourceCommit, pages_run: pagesRun,
    selected_area: metadata.selection.deep_dive.mesh_code,
    metadata_featured_building: metadata.featured_building,
    source: metadata.official_dataset, dataset_url: metadata.official_dataset_url,
    scope: { building_subset_records: metadata.deep_dive_buildings.records, meaning: "Verified subset catalog count, not a claim that all buildings are currently visible", geometry_lod: metadata.deep_dive_buildings.geometry_lod },
    prewarmed: true, cold_load_performance_evidence: false,
    viewport, live_build: { index_sha256: hash(liveIndex), assets },
    composition: { images_composited: false, images_cropped: false, browser_chrome: false },
    scenes: [], files: [],
  };
  const recordScene = async (label, extra = {}) => {
    const value = { label, ...extra, evidence: await sceneEvidence(page) };
    evidence.scenes.push(value);
    return value;
  };
  const screenshot = async (filename, label) => {
    await waitForReal3D(page);
    await page.mouse.move(8, viewport.height - 8);
    const bytes = await page.screenshot({ type: "png", fullPage: false, animations: "allow", caret: "hide" });
    const width = bytes.readUInt32BE(16);
    const height = bytes.readUInt32BE(20);
    if (width !== viewport.width || height !== viewport.height) throw new Error("Actual PNG dimensions differ from the native viewport");
    await writeFile(path.join(directory, filename), bytes, { flag: "wx" });
    evidence.files.push({ filename, bytes: bytes.length, sha256: hash(bytes), width, height });
    await recordScene(label);
  };
  const sectionButton = () => page.getByRole("button", { name: "街の断面", exact: true });
  const verifyButton = () => page.getByRole("button", { name: "確認場所を見る", exact: true });
  const waitChecks = async () => {
    await page.locator('.guided-spatial-app[data-guided-story="verify"][data-target-resolution="exact"]').waitFor();
    const count = await page.locator(".guided-check-list > li").count();
    if (count < 3 || count > 5) throw new Error(`Expected 3–5 sourced checks; received ${count}`);
    if (!(await page.locator(".guided-task-heading").innerText()).includes("未確認")) throw new Error("Field target is not marked unconfirmed");
  };
  const zoomToBuilding = async () => {
    const point = await clickFeaturedBuilding(page, metadata, { click: false });
    await page.mouse.move(point.x, point.y);
    await page.mouse.wheel(0, -120);
    await pause(700);
    await waitForReal3D(page, 10_000);
  };
  const restoreWideHeight = async (height) => {
    const canvas = await page.locator(".guided-3d-view .cesium-widget canvas").boundingBox();
    await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const current = await page.evaluate(() => window.__cityGapCesiumViewer.camera.positionCartographic.height);
      if (current >= height * 0.97) break;
      await page.mouse.wheel(0, 60);
      await pause(180);
    }
    await waitForReal3D(page, 10_000);
  };
  try {
    await page.goto(url.href, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitForReal3D(page);
    await page.locator('.guided-spatial-app[data-area-id="533513314"][data-context-status="ready"]').waitFor();
    await recordScene("production 3D ready before choreography");
    process.stdout.write("[capture] production real 3D content ready\n");

    if (mode === "area-image") {
      // Wait only for imagery attached to tiles selected by this camera.
      // Do not wait for the globe's global request queue or change any layers.
      await page.mouse.click(viewport.width / 2, 28);
      await page.waitForFunction(() => {
        const tiles = window.__cityGapCesiumViewer?.scene.globe._surface?._tilesToRender ?? [];
        return tiles.length > 0 && tiles.every((tile) => tile.data?.imagery?.some((imagery) => imagery.readyImagery?.texture));
      }, null, { timeout: 12_000, polling: 200 });
      await pause(1200);
      await waitForReal3D(page);
      evidence.current_camera_background = await page.evaluate(() => {
        const tiles = window.__cityGapCesiumViewer.scene.globe._surface._tilesToRender;
        return { selected_globe_tiles: tiles.length, tiles_with_ready_imagery: tiles.filter((tile) => tile.data?.imagery?.some((imagery) => imagery.readyImagery?.texture)).length, wait_scope: "Only current-camera selected globe tiles", timeout_ms: 12_000, stable_hold_ms: 1200 };
      });
      await screenshot("02-area-to-3d.png", "Same Area statistics and real city model");
      return;
    }

    if (mode === "images") {
      await screenshot("02-area-to-3d.png", "Same Area statistics and real city model");
      await moveRealCamera(page, 3);
      await waitForReal3D(page);
      evidence.picked_building = await clickFeaturedBuilding(page, metadata);
      await zoomToBuilding();
      await screenshot("01-plateau-3d-hero.png", "Real selected building with source attributes");
      // Reopen the actual same-Area URL for its verified wide A–B framing.
      await page.goto(url.href, { waitUntil: "domcontentloaded", timeout: 45_000 });
      await waitForReal3D(page);
      await clickFeaturedBuilding(page, metadata);
      await sectionButton().click();
      await page.locator('.guided-map-stage[data-section-expanded="true"] .urban-section').waitFor();
      await screenshot("03-3d-and-section.png", "Same A–B in 3D and Section");
      await verifyButton().click();
      await waitChecks();
      await page.locator(`.guided-spatial-app[data-target-key="building:${metadata.featured_building.id}"]`).waitFor();
      await zoomToBuilding();
      await screenshot("04-3d-field-target.png", "Same selected building and its unconfirmed field checks");
      return;
    }
    if (!new Set(["trial", "master"]).has(mode)) throw new Error(`Unsupported capture mode: ${mode}`);
    if (mode === "master") {
      // Warm the Section and checks before starting the one clean master.
      await sectionButton().click();
      await page.locator('.guided-map-stage[data-section-expanded="true"] .urban-section').waitFor();
      await sectionButton().click();
      await verifyButton().click();
      await waitChecks();
      await page.getByRole("button", { name: "街の形へ戻る", exact: true }).click();
      await page.locator('.guided-spatial-app[data-guided-story="understand"]').waitFor();
      await waitForReal3D(page);
    }
    const recorder = await createNativeScreencast({ page, context, directory, viewport });
    const start = await recorder.start();
    process.stdout.write(`[capture] ${mode} recording started\n`);
    const visibilitySamples = [];
    let samplePending = null;
    let sampleError = null;
    const sampleVisibility = () => {
      if (samplePending) return samplePending;
      samplePending = page.evaluate(() => {
        const viewer = window.__cityGapCesiumViewer;
        const stage = document.querySelector(".guided-map-stage");
        const container = document.querySelector("[data-building-source][data-local-dem]");
        const bounds = viewer?.scene.canvas.getBoundingClientRect();
        let selectedBuildingFeatures = 0;
        let selectedDemTiles = 0;
        for (let index = 0; index < (viewer?.scene.primitives.length ?? 0); index += 1) {
          const primitive = viewer.scene.primitives.get(index);
          if (!primitive.show || !primitive.statistics || !primitive.root) continue;
          const resource = primitive._url ?? primitive.resource?.url ?? "";
          if (resource.includes("plateau-terrain")) selectedDemTiles += primitive._selectedTiles?.length ?? 0;
          else selectedBuildingFeatures += primitive.statistics.numberOfFeaturesSelected ?? 0;
        }
        const visible = stage?.getAttribute("data-guided-map-mode") === "plateau3d"
          && bounds?.width > 200 && bounds?.height > 200 && bounds.top < innerHeight && bounds.bottom > 0
          && document.querySelector(".guided-3d-view")?.getAttribute("data-guided-3d-state") !== "error"
          && selectedBuildingFeatures > 0 && selectedDemTiles > 0 && container?.dataset.roadsReady === "true";
        return { real_3d_visible: Boolean(visible), selected_building_features: selectedBuildingFeatures, selected_dem_tiles: selectedDemTiles, roads_ready: container?.dataset.roadsReady === "true", canvas_width: bounds?.width, canvas_height: bounds?.height };
      }).then((sample) => visibilitySamples.push({ at_seconds: (monotonicMilliseconds() - start) / 1000, ...sample }))
        .catch((error) => { sampleError ??= error; })
        .finally(() => { samplePending = null; });
      return samplePending;
    };
    await sampleVisibility();
    const visibilityTimer = setInterval(() => { void sampleVisibility(); }, 250);
    const duration = mode === "trial" ? 9 : 42;
    const holdUntil = async (seconds) => {
      const remaining = start + seconds * 1000 - monotonicMilliseconds();
      if (remaining > 0) await pause(remaining);
    };
    try {
      await holdUntil(0.7);
      evidence.camera_motion = { start_seconds: (monotonicMilliseconds() - start) / 1000, ...(await moveRealCamera(page, 3)) };
      evidence.camera_motion.end_seconds = (monotonicMilliseconds() - start) / 1000;
      await waitForReal3D(page, 10_000);
      const wideHeight = await page.evaluate(() => window.__cityGapCesiumViewer.camera.positionCartographic.height);
      await holdUntil(mode === "trial" ? 5 : 10);
      evidence.picked_building = await clickFeaturedBuilding(page, metadata);
      await recordScene("Real building selected during recording", { start_seconds: (monotonicMilliseconds() - start) / 1000 });
      if (mode === "master") {
        await zoomToBuilding();
        await holdUntil(22);
        await restoreWideHeight(wideHeight);
        await sectionButton().click();
        await page.locator('.guided-map-stage[data-section-expanded="true"] .urban-section').waitFor();
        const section = page.locator(".guided-section-dock .urban-section svg");
        await section.focus();
        await page.keyboard.press("ArrowRight");
        await recordScene("Same A–B and focused Section", { start_seconds: (monotonicMilliseconds() - start) / 1000 });
        await holdUntil(31);
        await verifyButton().click();
        await waitChecks();
        await page.locator(`.guided-spatial-app[data-target-key="building:${metadata.featured_building.id}"]`).waitFor();
        await recordScene("Same selected building with its unconfirmed checks", { start_seconds: (monotonicMilliseconds() - start) / 1000 });
      }
      await page.mouse.move(8, viewport.height - 8);
      await holdUntil(duration);
    } finally {
      clearInterval(visibilityTimer);
      if (samplePending) await samplePending;
      await sampleVisibility();
      const capture = await recorder.stop();
      process.stdout.write(`[capture] acquired ${capture.frame_count} native frames in ${capture.duration_seconds.toFixed(3)}s\n`);
      const visibleSeconds = visibilitySamples.reduce((sum, sample, index) => sample.real_3d_visible
        ? sum + Math.max(0, (visibilitySamples[index + 1]?.at_seconds ?? capture.duration_seconds) - sample.at_seconds)
        : sum, 0);
      evidence.recording = { ...capture, frames: undefined, real_3d_visible_fraction: visibleSeconds / capture.duration_seconds,
        visibility_measurement: "250ms observations of visible Cesium viewport, selected building features, selected real DEM tile, ready roads and no error; last observation held until next. This is sampled renderer evidence, not continuous pixel classification.",
        measured_real_3d_seconds: visibleSeconds, visibility_samples: visibilitySamples,
      };
      const motionFrames = capture.frames.filter((frame) => frame.offset_seconds >= evidence.camera_motion?.start_seconds && frame.offset_seconds <= evidence.camera_motion?.end_seconds);
      const gaps = motionFrames.slice(1).map((frame, index) => frame.offset_seconds - motionFrames[index].offset_seconds);
      if (motionFrames.length) gaps.push(motionFrames[0].offset_seconds - evidence.camera_motion.start_seconds, evidence.camera_motion.end_seconds - motionFrames.at(-1).offset_seconds);
      evidence.motion_frame_cadence = { captured_frames: motionFrames.length, interval_seconds: gaps, maximum_gap_seconds: Math.max(0, ...gaps), observation_window_seconds: evidence.camera_motion.end_seconds - evidence.camera_motion.start_seconds, mean_acquired_fps: motionFrames.length / (evidence.camera_motion.end_seconds - evidence.camera_motion.start_seconds) };
    }
    if (sampleError) throw sampleError;
    if (evidence.recording.real_3d_visible_fraction < 0.6) throw new Error("Measured real 3D share is below 60%");
    if (evidence.recording.duration_seconds > duration + 1) throw new Error("Choreography exceeded its bounded duration");
    // Cadence is acquisition evidence, not proof of smoothness; review motion frames/video too.
    if (evidence.motion_frame_cadence.captured_frames < 24 || evidence.motion_frame_cadence.maximum_gap_seconds > 0.5) throw new Error("Camera motion acquisition cadence is too sparse for this route");
  } finally {
    await writeFile(path.join(directory, "production-capture.json"), `${JSON.stringify(evidence, null, 2)}\n`, { flag: "wx" });
  }
}

export async function readProductionCapture(directory) {
  return JSON.parse(await readFile(path.join(directory, "production-capture.json"), "utf8"));
}

export async function packageJudgingAssets({ directory, imagesDirectory, areaImageDirectory, masterDirectory, captionDirectory, trialDirectory }) {
  const json = async (root, filename) => JSON.parse(await readFile(path.join(root, filename), "utf8"));
  const [images, master, trial, clean, captioned, renderer, imageErrors, masterErrors, areaImage, areaImageErrors, trialEncode] = await Promise.all([
    readProductionCapture(imagesDirectory), readProductionCapture(masterDirectory), readProductionCapture(trialDirectory),
    json(masterDirectory, "encode.json"), json(captionDirectory, "captioned.json"), json(masterDirectory, "renderer.json"),
    json(imagesDirectory, "diagnostics.json"), json(masterDirectory, "diagnostics.json"),
    readProductionCapture(areaImageDirectory), json(areaImageDirectory, "diagnostics.json"),
    json(trialDirectory, "encode.json"),
  ]);
  if ([images, areaImage, trial].some((capture) => capture.ui_source_commit !== master.ui_source_commit || capture.pages_run !== master.pages_run
      || capture.live_build.index_sha256 !== master.live_build.index_sha256 || !capture.live_build.assets.every((asset) => asset.matches_local_build))
      || captioned.derived_from.sha256 !== clean.sha256 || master.recording.real_3d_visible_fraction < 0.6) throw new Error("Package provenance differs between image set and master");
  if (areaImage.files.length !== 1 || areaImage.files[0].filename !== "02-area-to-3d.png") throw new Error("Expected only replacement Area image 02");
  const finalImageFiles = images.files.map((file) => file.filename === "02-area-to-3d.png"
    ? { ...areaImage.files[0], sourceDirectory: areaImageDirectory } : { ...file, sourceDirectory: imagesDirectory });
  const finalImageScenes = images.scenes.slice(1).map((scene) => scene.label === areaImage.scenes.at(-1).label ? areaImage.scenes.at(-1) : scene);
  const selectedBuildingId = master.picked_building.id;
  const selectedScenes = [...finalImageScenes, ...master.scenes].filter((scene) => scene.evidence.root.objectKind === "building");
  if (selectedBuildingId !== images.picked_building.id || selectedBuildingId !== master.metadata_featured_building.id
      || selectedScenes.some((scene) => scene.evidence.root.objectId !== selectedBuildingId || scene.evidence.root.targetKey !== `building:${selectedBuildingId}`)) {
    throw new Error("Selected building identity is inconsistent across image, Section and field-check scenes");
  }
  const sourceBuildingTileset = master.scenes[0].evidence.tilesets.find((tileset) => tileset.url?.includes("/plateau/tileset.json"));
  if (!sourceBuildingTileset) throw new Error("Verified source-building tileset evidence is absent");
  const scopeCounts = { verified_3d_subset_buildings: master.scope.building_subset_records,
    selected_source_tile_catalog_features: sourceBuildingTileset.loaded_features, source_building_tiles: sourceBuildingTileset.content_ready,
    area_context_building_intersections: Number(master.scenes[0].evidence.root.contextBuildings),
    area_context_road_intersections: Number(master.scenes[0].evidence.root.contextRoads) };
  if (Object.values(scopeCounts).some((count) => !Number.isFinite(count) || count <= 0)) throw new Error("Scope evidence must contain finite positive counts");
  const trialVideo = trialEncode.probe.streams.find((stream) => stream.codec_type === "video");
  if (hash(await readFile(path.join(trialDirectory, trialEncode.filename))) !== trialEncode.sha256) throw new Error("Trial proof changed after encoding");
  const payload = [...finalImageFiles,
    { ...clean, sourceDirectory: masterDirectory }, { ...captioned, sourceDirectory: captionDirectory },
    { ...captioned.captions, sourceDirectory: captionDirectory }];
  if (payload.length !== 7 || new Set(payload.map((file) => file.filename)).size !== 7) throw new Error("Expected seven unique payload files plus manifest");
  const files = [];
  for (const file of payload) {
    const bytes = await readFile(path.join(file.sourceDirectory, file.filename));
    if (hash(bytes) !== file.sha256) throw new Error(`Payload changed after verification: ${file.filename}`);
    await writeFile(path.join(directory, file.filename), bytes, { flag: "wx" });
    const stream = file.probe?.streams.find((item) => item.codec_type === "video");
    files.push({ filename: file.filename, bytes: bytes.length, sha256: hash(bytes),
      ...(stream ? { width: stream.width, height: stream.height, codec: stream.codec_name, pixel_format: stream.pix_fmt,
        output_fps: stream.avg_frame_rate, output_frames: Number(stream.nb_frames), duration_seconds: Number(file.probe.format.duration), audio_streams: 0 }
        : file.width ? { width: file.width, height: file.height } : { cues: file.cues }),
    });
  }
  const renderEvidence = (scene) => ({ label: scene.label, start_seconds: scene.start_seconds,
    selected_area: scene.evidence.root.areaId, selected_object: { kind: scene.evidence.root.objectKind, id: scene.evidence.root.objectId },
    selected_target: { kind: scene.evidence.root.targetKind, key: scene.evidence.root.targetKey, resolution: scene.evidence.root.targetResolution },
    strict_ready: scene.evidence.readiness.captureStrictReady === "true", required_building_content_ready: scene.evidence.readiness.buildingContentReady === "true",
    local_dem_ready: scene.evidence.readiness.localDemReady === "true", roads_ready: scene.evidence.readiness.roadsReady === "true",
    globe_visible: scene.evidence.globe_visible, section_transect: scene.evidence.readiness.sectionTransectId,
    tilesets: scene.evidence.tilesets, checks: scene.evidence.checks,
  });
  const cadence = (capture) => ({ acquired_frames: capture.recording.frame_count, monotonic_duration_seconds: capture.recording.duration_seconds,
    motion_frames: capture.motion_frame_cadence.captured_frames, motion_observation_seconds: capture.motion_frame_cadence.observation_window_seconds,
    motion_mean_acquired_fps: capture.motion_frame_cadence.mean_acquired_fps, motion_maximum_gap_seconds: capture.motion_frame_cadence.maximum_gap_seconds,
    sampled_real_3d_fraction: capture.recording.real_3d_visible_fraction, sampled_real_3d_seconds: capture.recording.measured_real_3d_seconds,
    sample_count: capture.recording.visibility_samples.length, sampling_method: capture.recording.visibility_measurement,
  });
  const manifest = {
    schema_version: "citygap.judging-3d@1", generated_at: new Date().toISOString(),
    production_url: master.production_url, ui_source_commit: master.ui_source_commit, pages_run: master.pages_run,
    source_branch: "feat/guided-spatial-storytelling-v1", selected_area: master.selected_area,
    dataset: { title: master.source, url: master.dataset_url, year: Number(master.source.match(/20\d{2}/)?.[0]), lod: master.scope.geometry_lod },
    selected_building: master.picked_building,
    scope: { ...scopeCounts,
      note: "The verified 3D subset catalog, loaded content across source tiles, and separate 2D Area-intersection scope differ. None is a claim that every record is simultaneously visible. Per-scene selected tile/feature statistics are recorded separately.",
      population: "2020 Census 500m mesh aggregate; not PLATEAU data or a count of inhabitants of the selected building",
    },
    capture: { viewport: master.viewport, actual_acquired_pixels: master.recording.actual_capture_pixels, output_pixels: master.recording.output_pixels,
      device_pixel_ratio: 1, native_1080p: master.recording.actual_capture_pixels.width === 1920 && master.recording.actual_capture_pixels.height === 1080, spatial_upscale: false, method: master.recording.method,
      raw_frame_cadence: master.recording.frame_cadence, prewarmed: true, cold_load_performance_evidence: false,
      output_fps: 30, temporal_normalization: clean.temporal_processing,
      static_hold_frame_duplication: clean.static_hold_frame_duplication,
      acquired_intervals_longer_than_two_output_frames: clean.acquired_intervals_longer_than_two_output_frames,
      browser_chrome: false, audio: false, renderer, master: cadence(master), trial: { ...cadence(trial),
        encoded_proof: { filename: trialEncode.filename, sha256: trialEncode.sha256, width: trialVideo.width, height: trialVideo.height,
          duration_seconds: Number(trialEncode.probe.format.duration), output_frames: Number(trialVideo.nb_frames), output_fps: trialVideo.avg_frame_rate,
          codec: trialVideo.codec_name, pixel_format: trialVideo.pix_fmt, decode: "PASS", decode_method: "Full FFmpeg decode to null completed successfully before encode.json was written",
          included_in_delivery_payload: false } },
      clocks: { choreography: "process.hrtime.bigint() monotonic clock", wall_clock: "Windows Date.now(); elapsed wall value includes stop/final-frame work", master_wall_elapsed_seconds: master.recording.wall_clock_elapsed_seconds, settings_modified: false },
    },
    production_build_verification: master.live_build,
    image_composition: images.composition,
    readiness: { images: finalImageScenes.map(renderEvidence), master: master.scenes.map(renderEvidence),
      area_image_optional_background: { ...areaImage.current_camera_background, all_selected_gsi_tiles_ready_at_final_snapshot: false,
        observation: "A bounded current-camera imagery wait passed at an earlier LOD. After the stable hold, refinement selected 54 globe tiles with zero direct-ready imagery records in the final snapshot. GSI fallback contours and streets were visibly drawn. This does not claim full optional GSI readiness." } },
    caption_derivation: { clean_master_sha256: clean.sha256, timing: captioned.captions.timing, placement: captioned.captions.placement, separately_recorded: false },
    diagnostics: { image_records: imageErrors, area_image_records: areaImageErrors, master_records: masterErrors,
      tooling_history: ["One pre-capture dynamic-import deadlock; zero frames produced, preserved, fixed once before the successful same-route trial.",
        "Windows-to-WSL path escaping failed before encoding; existing acquired frames were encoded through WSL without re-recording.",
        "Caption contrast corrected once offline into a new directory from the unchanged clean master; previous caption output retained.",
        "Only image 02 was retaken once after a bounded current-camera background wait and stable hold; its original screenshot remains preserved. The one clean master was not re-recorded."],
      recording_routes_used: 1, successful_trial_recordings: 1, clean_master_recordings: 1,
    },
    files,
    review: { self_visual_review: "REVIEWED_BY_AGENTS", reviewed_artifacts: "All four native images, trial motion frames, decoded clean master scenes at 12s and 36s, and final captioned Section frame at 26s", user_approval: "AWAITING_USER_REVIEW", municipal_workflow_effectiveness: "UNVERIFIED" },
    limitations: ["LOD1 shapes and attributes do not verify entrances, steps, current use or passability; three selected-building checks remain unconfirmed.",
      "Real local PLATEAU DEM and the flat GSI background are distinct. Local capture readiness does not wait for all global background tiles.",
      "Rendered content readiness, acquired frame cadence, output frame rate, and human approval are separate claims."],
  };
  await writeFile(path.join(directory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, { flag: "wx" });
  return { directory, payload_files: files.length, manifest_sha256: hash(await readFile(path.join(directory, "manifest.json"))), files };
}
