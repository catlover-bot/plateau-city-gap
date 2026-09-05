# CITY GAP: PLATEAUを現地確認につなぐ3Dデモ

Goal: `plateau-3d-value-fast-delivery-v1`

Status: the 3D service is deployed, its required production interaction paths pass, and the additional four-image / single-master-video package is complete. Final delivery-commit CI is reported with its exact SHA/run in the hand-off. Visual review here is agent review, not user acceptance or municipal validation.

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

動作確認済みの公開3D直リンク: [常団地前周辺のPLATEAU 3D](https://catlover-bot.github.io/plateau-city-gap/?experience=guided&story=understand&mapMode=plateau3d&selectionType=mesh&selection=533513314)。入口は [Public root](https://catlover-bot.github.io/plateau-city-gap/) です。

今回の4枚は `docs/assets/judging-3d/` の追加セットです。既存8画像と旧動画は変更していません。全画像は公開サービスの1920×1080実画面で、合成・crop・拡大はありません。

| File | 推奨用途 |
| --- | --- |
| [01: 3D hero](assets/judging-3d/01-plateau-3d-hero.png) | 冒頭。実建物の立体形状、選択属性、出典・年度を示す |
| [02: Area → 3D](assets/judging-3d/02-area-to-3d.png) | 国勢調査の500m集計と、同じ地域の実都市モデルの役割を分ける |
| [03: 3Dと断面](assets/judging-3d/03-3d-and-section.png) | 同一A–Bの3Dと断面で位置・標高と建物高さの関係を示す |
| [04: 現地確認対象](assets/judging-3d/04-3d-field-target.png) | 同じ実建物、既存3項目、未確認という到達点を示す |

## 動画と取得品質

[字幕なし原本](assets/judging-3d/city-gap-3d-demo-clean.mp4) / [同じ原本から生成した字幕付き版](assets/judging-3d/city-gap-3d-demo-captioned.mp4) / [字幕VTT](assets/judging-3d/captions.vtt) / [出典・hash・描画証拠のmanifest](assets/judging-3d/manifest.json)

原本は公開UIを1回だけ収録した42.033秒。全取得フレームを検査したnative 1920×1080で、出力も同じ寸法、H.264 / yuv420p / 30fps / 音声なしです。字幕付き版はこの原本への後処理であり、別収録ではありません。試し録画は9.033秒、389取得フレームから271出力フレームで、カメラ移動・実建物選択・文字・エンコード完了を本編前に確認しました。

本編はDevToolsの可変間隔1,769フレームを1,261出力フレームへ正規化しています。静止holdの複製と余剰フレームのdropがあり、取得30fpsやAI補間を意味しません。実カメラ移動の観測区間3.700秒で165フレームを取得（平均44.60fps、最大間隔0.0586秒）。prewarm済みで、cold-load性能の証拠にはしません。単調増加時計で収録・holdを管理し、OS/WSL時刻設定は変更していません。

250ms間隔の描画観測では、実建物・局所DEM・道路を伴う3D表示が41.973秒、全体の99.86%でした。これは連続した全画素判定ではなく、表示canvasと実レンダラーのサンプリングです。収録中の実建物選択は10.516秒、同じA–Bとfocus付き断面は24.059秒、同じ建物の未確認3項目は31.367秒からで、字幕もこの実測遷移に合わせています。

選択した実モデルは `bldg_a490fb5b-d668-441e-b9af-5b35c4629006`、住宅・高さ8.5m・地上2階・LOD1。実scene picking、metadata、Inspectorの一致を確認しました。この値をアプリへ固定転記していません。画像02だけ、任意の背景図が薄い最初の撮影から1回追加取得しました。実PLATEAUの必須contentは準備済みで、GSI背景は表示された既存の低い詳細度の画像を含み、最終詳細度の全背景タイル完了とは主張しません。最初の画像、試し録画、raw frames、旧字幕版、失敗時の一時出力は削除せず保持しています。

## データ・coverage・未検証事項

- PLATEAU舞鶴市2025年度の既存3D Tiles。実形状はLOD1。配布側のファイル名・選択手順にLOD2という表記があっても、この表示をLOD2とは呼びません。
- 既存の3タイル全体は856建物レコード、検証済み500m subsetは296棟。Areaに交差するCityGML由来2D contextの303棟とは抽出scopeが異なります。これらは画面内に実際に描画された棟数ではありません。
- 道路面135件と局所PLATEAU DEMを再利用。広域背景地形とは別物です。道路面を歩行者ネットワークや通行可能性の証明として扱いません。
- 断面は `maizuru-533513314-plateau-2025-v1` の同じA–B、94地形サンプル、直接交差17建物・14道路。付近の建物数とは区別します。地形の標高と建物自体の高さも別の量です。
- 人口・年齢は国勢調査2020の500m集計。PLATEAU属性や個別建物居住者数ではありません。用途・高さ・階数の未収録値は「データなし」とします。
- 入口、歩道、段差、現在の利用や通行条件、現地回答、自治体業務適合性は未検証。LOD1表示から推定しません。
- 3Dはこの検証済みAreaのみ。495のArea選択は維持し、非対応Areaには別地域のモデルを流用しません。
- 撮影は最終公開版の準備完了後に実施しました。prewarm、実取得画素、可変フレーム間隔、複製、出力寸法と30fps化はmanifestで開示し、cold-load性能や取得30fpsの証拠とはしません。

## 検証・納品状況

Local validation: ESLint, TypeScript/production build, 33 frontend test files / 145 tests, and diff whitespace check pass. The existing six-Area Guided spatial and Guided→Advanced scripts pass unchanged with no unexpected diagnostics. The new hardware-Chrome browser path passes Public lazy entry, real building pick/official attributes, 2D retention, A–B/focus, kind-specific checks, unsupported/stale-Area rejection, Advanced completion, and 390px injected failure/retry. The first development-server 3D entry took 5.65 seconds; injected mobile tile failure settled in 46.04 seconds and retry succeeded. These are environment-specific development measurements, not production cold-load benchmarks.

The local docs checker reports only two pre-existing missing image paths (`01-city-gap-overview-16x9.png`, `02-area-selection-16x9.png`); their untracked `copy.png` counterparts are byte-identical by SHA-256 and are preserved without staging. The committed tree retains the original paths, so exact-commit CI will validate the deliverable independently of these user worktree changes.

UI source `5d59de0852066d96d9a228c205812fe97f006dab` passed all nine jobs in [CI 33939420182](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33939420182), then build and deploy in [Pages 33939684419](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33939684419). Live entry SHA-256 `41431989c51c1002cad91a73416afe0a36a1ab1233d16fe469a0e2ca9829fc31` equals the local production build.

The full targeted browser path also passed on production: Public→3D actual pick/official attributes, A–B/focus, building-three/road-four matching checks, 2D retention, Area/stale/unsupported rejection, Advanced single-flight success, and 390px finite failure/retry. Production used one persistent MapLibre initialization with zero unexpected page/request/local-HTTP diagnostics. Observed hardware-browser 3D entry was 2.364 seconds; injected mobile failure settled in 45.649 seconds then recovered. These are test observations, not a claim of universal or cold-load performance.

The four production images, successful native trial, single clean master, captioned derivative, VTT, and seven-payload-hash manifest are complete. Both MP4s pass full decode and format checks; image and master capture diagnostics contain no unexpected errors. The live index and all ten JS/CSS assets, including lazy Cesium chunks, matched the declared production build before capture. Final asset-commit CI must be nine of nine green before closing the goal; the final hand-off identifies that exact commit/run. No additional Pages deployment is needed for these docs/media/capture-tooling-only changes. Main remains untouched, and the two pre-existing image-name worktree changes remain unstaged.
