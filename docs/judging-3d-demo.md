# CITY GAP: PLATEAUを現地確認につなぐ3Dデモ

Goal: `plateau-3d-value-fast-delivery-v1`

Status: implementation, local production build, and required local browser regressions pass. Production verification and the new media package are not yet complete.

## 実装メモ

Starting branch `feat/guided-spatial-storytelling-v1`, HEAD `704a9b237a96aee4b71b01e9f0cd0090100764dc`. GitHub matched this commit. Existing presentation image name changes and all previous media/backups are preserved.

The existing lazy Cesium renderer, verified-local bundled building tiles, local PLATEAU DEM, official attribute picker, road selection, Spatial Evidence Pack verification, and verified Urban Section are reused. Guided retains its canonical Area and persistent MapLibre instance; an object selection is subordinate to that Area. The new Public link explicitly opens the 常団地前 example. Unsupported Areas keep their own 2D context and never borrow this 3D model. The full Advanced loader remains separate.

Readiness distinguishes SHA-256 verification, complete building tile content, and actual camera-dependent rendering. Local 3D does not wait for a citywide stream or broad terrain. Metadata and rendering have bounded waits, retry, and a 2D return path. No coordinate conversion, terrain, heights, attributes, analysis, or field answers are newly fabricated.

## 審査基準と見せる証拠

| 審査基準 | このデモで確認する事実 | 主な画面 |
| --- | --- | --- |
| 3D都市モデルの活用度 | 実PLATEAUの立体形状を選び、同じ建物の収録属性と、同じA–Bの地形・建物・道路の断面を対応させる | 01、03 |
| アイデア、独創性 | 地域データ → 実都市モデル → 未確認事項 → 現地確認対象を、同一Areaと対象選択でたどる | 02、04 |
| 地域課題への貢献度 | 公開データだけでは判断できない出入口・利用状況・道路の通行条件を、対象に合う既存確認項目へ接続する | 04 |

独創性の証明、受賞可能性、自治体導入、時間削減、課題解決効果を検証済みとはしません。

## 約40秒の口述原稿

> CITY GAPは、地域のデータを、実際の街と現地確認につなぎます。常団地前周辺の同じ500メートル範囲を、PLATEAUの建物・道路・地形で立体的に見ます。建物を選ぶと、モデルに収録された用途、高さ、階数が対応します。人口は別の国勢調査の集計で、建物の居住者数ではありません。次に、同じAからBの断面で地形と建物の関係を見ます。ただし、入口や実際の通行条件まではモデルだけで分かりません。そこで、この建物や道路を対象に、現地で確かめる項目へ進みます。回答はまだなく、状態は未確認です。

## 操作と画像4枚の用途

Public rootの「PLATEAUで街を3Dで見る」から「常団地前周辺の実例」を開きます。3Dの建物をクリックして属性を確認し、「街の断面」で同じA–Bを展開します。「確認場所を見る」で、その対象に合う既存の確認項目へ進みます。「2D地図」に戻っても対象を保持し、「範囲選択へ戻る」で別地域を選べます。

Direct-route candidate (production operation verification pending): `https://catlover-bot.github.io/plateau-city-gap/?experience=guided&story=understand&mapMode=plateau3d&selectionType=mesh&selection=533513314`.

The four additional images will be stored in `docs/assets/judging-3d/`; existing eight presentation images will not be replaced.

| File | 推奨用途 |
| --- | --- |
| `01-plateau-3d-hero.png` | 冒頭。実建物の立体形状、選択属性、出典・年度を示す |
| `02-area-to-3d.png` | 国勢調査の500m集計と、同じ地域の実都市モデルの役割を分ける |
| `03-3d-and-section.png` | 同一A–Bの3Dと断面で位置・標高と建物高さの関係を示す |
| `04-3d-field-target.png` | 実対象、既存3〜5項目、未確認という到達点を示す |

## データ・coverage・未検証事項

- PLATEAU舞鶴市2025年度の既存3D Tiles。実形状はLOD1。配布側のファイル名・選択手順にLOD2という表記があっても、この表示をLOD2とは呼びません。
- 既存の3タイル全体は856建物レコード、検証済み500m subsetは296棟。Areaに交差するCityGML由来2D contextの303棟とは抽出scopeが異なります。これらは画面内に実際に描画された棟数ではありません。
- 道路面135件と局所PLATEAU DEMを再利用。広域背景地形とは別物です。道路面を歩行者ネットワークや通行可能性の証明として扱いません。
- 断面は `maizuru-533513314-plateau-2025-v1` の同じA–B、94地形サンプル、直接交差17建物・14道路。付近の建物数とは区別します。地形の標高と建物自体の高さも別の量です。
- 人口・年齢は国勢調査2020の500m集計。PLATEAU属性や個別建物居住者数ではありません。用途・高さ・階数の未収録値は「データなし」とします。
- 入口、歩道、段差、現在の利用や通行条件、現地回答、自治体業務適合性は未検証。LOD1表示から推定しません。
- 3Dはこの検証済みAreaのみ。495のArea選択は維持し、非対応Areaには別地域のモデルを流用しません。
- 撮影は最終公開版の準備完了後に行います。prewarm、実取得画素、可変フレーム間隔、複製、出力寸法と30fps化はmanifestで開示し、cold-load性能や取得30fpsの証拠とはしません。

## 検証・納品状況

Local validation: ESLint, TypeScript/production build, 33 frontend test files / 145 tests, and diff whitespace check pass. The existing six-Area Guided spatial and Guided→Advanced scripts pass unchanged with no unexpected diagnostics. The new hardware-Chrome browser path passes Public lazy entry, real building pick/official attributes, 2D retention, A–B/focus, kind-specific checks, unsupported/stale-Area rejection, Advanced completion, and 390px injected failure/retry. The first development-server 3D entry took 5.65 seconds; injected mobile tile failure settled in 46.04 seconds and retry succeeded. These are environment-specific development measurements, not production cold-load benchmarks.

The local docs checker reports only two pre-existing missing image paths (`01-city-gap-overview-16x9.png`, `02-area-selection-16x9.png`); their untracked `copy.png` counterparts are byte-identical by SHA-256 and are preserved without staging. The committed tree retains the original paths, so exact-commit CI will validate the deliverable independently of these user worktree changes.

Pending: exact-commit nine-job CI, Pages deployment, live asset and interaction verification, four production images, 8–10 second recording trial, one 35–45 second clean master and its captioned derivative, media manifest, final asset-commit CI. No final media or live-operation success is claimed yet.
