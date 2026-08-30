import { chromium } from "playwright-core";

const parameters = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (!argument.startsWith("--")) continue;
  const value = process.argv[index + 1];
  parameters.set(argument, value && !value.startsWith("--") ? value : "true");
  if (value && !value.startsWith("--")) index += 1;
}

const baseUrl = parameters.get("--url") ?? "http://127.0.0.1:4173/plateau-city-gap/";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? chromium.executablePath();
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl", "--ignore-gpu-blocklist", "--use-gl=swiftshader"],
});
const startedAt = Date.now();

async function waitForStep(page, step) {
  await page.locator(`.investigation-journey[data-investigation-step="${step}"]`).waitFor({
    state: "visible",
    timeout: 120_000,
  });
}

async function next(page, label, expectedStep) {
  const button = page.getByRole("button", { name: label, exact: true });
  const box = await button.boundingBox();
  if (!box || box.height < 44) throw new Error(`primary action is not touch sized: ${label}`);
  await button.click();
  await waitForStep(page, expectedStep);
}

try {
  const desktop = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await desktop.newPage();
  page.setDefaultTimeout(120_000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.getByRole("heading", { name: /どこから現地確認するかを/ }).waitFor();
  if (await page.locator(".value-actions .investigation-primary").count() !== 1) {
    throw new Error("landing must have exactly one primary action");
  }
  await page.getByRole("button", { name: "舞鶴の現地調査候補を見る", exact: true }).click();
  await waitForStep(page, 1);

  const candidates = page.locator('.candidate-list [role="radio"]');
  if (await candidates.count() !== 3) throw new Error("shortlist must contain exactly three candidates");
  await page.getByRole("radio", { name: /二尾/ }).click();
  await next(page, "候補理由を見る", 2);
  await next(page, "街の構造を見る", 3);
  await page.locator(".plateau-field-context.unavailable").waitFor({ state: "visible" });
  if (await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').count() !== 0) {
    throw new Error("a candidate without PLATEAU coverage must not mount invented 3D detail");
  }
  await page.getByRole("button", { name: "戻る", exact: true }).click();
  await waitForStep(page, 2);
  await page.getByRole("button", { name: "戻る", exact: true }).click();
  await waitForStep(page, 1);
  await page.getByRole("radio", { name: /常団地前周辺/ }).click();

  await next(page, "候補理由を見る", 2);
  const brief = await page.locator(".candidate-brief").textContent();
  for (const token of ["200人", "563m", "1.45km", "495件", "286件", "218件", "23位"]) {
    if (!brief?.includes(token)) throw new Error(`candidate brief is missing ${token}`);
  }
  const triage = page.getByLabel("候補の仕分け状態");
  if (await triage.inputValue() !== "unreviewed") {
    throw new Error("candidate triage must start unreviewed");
  }
  await triage.selectOption("additional_investigation");

  await next(page, "街の構造を見る", 3);
  await page.getByText("296棟", { exact: true }).waitFor();
  await page.getByText("135面", { exact: true }).waitFor();
  await page.locator('.plateau-3d-shell[data-ui-mode="guided"]').waitFor({ state: "visible" });
  await page.locator(".plateau-3d-shell .map-engine-loading").last().waitFor({
    state: "hidden",
    timeout: 180_000,
  });
  await page.locator(".plateau-3d-shell canvas").first().waitFor({ state: "visible" });
  await page.waitForTimeout(1_000);

  await next(page, "確認項目を見る", 4);
  if (await page.locator(".check-category-list li").count() !== 28) {
    throw new Error("the deterministic field checklist must contain 28 items");
  }
  await page.getByText("確認する理由", { exact: true }).first().waitFor();

  await next(page, "現地確認を開始", 5);
  const firstCheck = page.locator(".editable-checks > li").first();
  await firstCheck.getByLabel("担当").fill("交通政策課");
  await firstCheck.getByLabel("メモ").fill("内部確認メモ");
  await page.getByLabel("地域事情に合わせて確認項目を追加").fill("自治会の送迎を確認");
  await page.getByRole("button", { name: "追加", exact: true }).click();
  await page.getByText("自治会の送迎を確認", { exact: true }).waitFor();
  await page.getByLabel(/^写真参照/).fill("site-photo-001.jpg");
  await page.getByRole("button", { name: "現在地を記録", exact: true }).click();
  await page.getByRole("button", { name: "この端末に保存", exact: true }).click();
  await page.getByText("この端末に保存しました。通信がなくても再表示できます", { exact: true }).waitFor();

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForStep(page, 5);
  await page.getByText("この端末の保存内容を復元しました", { exact: true }).waitFor();
  const restoredCheck = page.locator(".editable-checks > li").first();
  await restoredCheck.getByLabel("担当").waitFor();
  if (
    await restoredCheck.getByLabel("担当").inputValue() !== "交通政策課" ||
    await restoredCheck.getByLabel("メモ").inputValue() !== "内部確認メモ"
  ) throw new Error("the internal field sheet was not restored from IndexedDB");
  if (await page.getByLabel(/^写真参照/).inputValue() !== "site-photo-001.jpg") {
    throw new Error("the internal photo reference was not restored from IndexedDB");
  }
  await page.getByText("自治会の送迎を確認", { exact: true }).waitFor();

  await next(page, "調査サマリーを見る", 6);
  await page.locator(".review-status strong").getByText("追加調査", { exact: true }).waitFor();
  await page.getByText("AWAITING_MUNICIPAL_REVIEW", { exact: true }).waitFor();
  await page.getByText("BASELINE_NOT_COLLECTED", { exact: true }).waitFor();
  await page.getByText("実自治体からの回答はまだありません。候補を「確認済み」や価値仮説を「SUPPORTED」にはしていません。", { exact: true }).waitFor();
  const reviewOutcome = page.getByLabel("自治体レビュー結果");
  if (await reviewOutcome.inputValue() !== "unreviewed") {
    throw new Error("municipal review must start unreviewed");
  }
  await reviewOutcome.selectOption("existing_measures");
  await page.getByLabel("自治体・関係者の原文メモ").fill("既存施策で対応済みとの回答");
  await page.getByText("レビュー入力を保存しています", { exact: true }).waitFor();
  await page.getByText("レビュー入力をこの端末に自動保存しました", { exact: true }).waitFor();
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForStep(page, 6);
  await page.getByText("この端末の保存内容を復元しました", { exact: true }).waitFor();
  if (
    await page.getByLabel("自治体レビュー結果").inputValue() !== "existing_measures" ||
    await page.getByLabel("自治体・関係者の原文メモ").inputValue() !== "既存施策で対応済みとの回答"
  ) {
    throw new Error("municipal review response was not restored from IndexedDB");
  }
  if (await page.getByRole("button", { name: "印刷", exact: true }).count() !== 1) {
    throw new Error("final output must expose a print action");
  }
  await page.getByRole("button", { name: "詳細分析を開く", exact: true }).click();
  await page.locator('.product-app[data-experience="advanced"]').waitFor({ state: "visible" });

  if (pageErrors.length) throw new Error("desktop page errors: " + JSON.stringify(pageErrors));
  await desktop.close();

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(120_000);
  await mobilePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 90_000 });
  const landingAction = mobilePage.getByRole("button", { name: "舞鶴の現地調査候補を見る", exact: true });
  const landingBox = await landingAction.boundingBox();
  if (!landingBox || landingBox.height < 44 || landingBox.y + landingBox.height > 844) {
    throw new Error("mobile landing action is not visible and touch sized");
  }
  await landingAction.click();
  await waitForStep(mobilePage, 1);
  await next(mobilePage, "候補理由を見る", 2);
  await next(mobilePage, "街の構造を見る", 3);
  await next(mobilePage, "確認項目を見る", 4);

  const mapBox = await mobilePage.locator(".investigation-map-stage").boundingBox();
  const sheetBox = await mobilePage.locator(".investigation-step-sheet").boundingBox();
  const fieldAction = mobilePage.getByRole("button", { name: "現地確認を開始", exact: true });
  const actionBox = await fieldAction.boundingBox();
  if (
    !mapBox ||
    !sheetBox ||
    !actionBox ||
    mapBox.y >= sheetBox.y ||
    actionBox.height < 44 ||
    actionBox.y + actionBox.height > 844
  ) {
    throw new Error("390x844 field flow must keep map above sheet and primary action visible");
  }
  await fieldAction.click();
  await waitForStep(mobilePage, 5);
  if (await mobilePage.getByRole("button", { name: "現在地を記録", exact: true }).count() !== 1) {
    throw new Error("mobile field sheet must expose GPS capture");
  }
  if (await mobilePage.getByLabel("現地メモ").count() !== 1) {
    throw new Error("mobile field sheet must retain the field note input");
  }
  await mobile.close();

  process.stdout.write(JSON.stringify({
    result: "passed",
    desktop: "landing -> shortlist -> brief -> PLATEAU -> checks -> offline sheet -> review -> advanced",
    mobile: "390x844 landing -> checks -> field sheet",
    runtime_ms: Date.now() - startedAt,
  }) + "\n");
} finally {
  await browser.close();
}
