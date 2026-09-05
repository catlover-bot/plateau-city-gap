# CITY GAP: PLATEAUを現地確認につなぐ3Dデモ

## Advanced 3Dの追加改善（UI公開済み・追加素材完成）

拡張依頼の起点は `fcbd45151dbba65d0bc2682ddf096d39472deaa5`。以下の既存納品記録・素材は保全し、Advanced用の画像4枚と40秒の新しいclean/captioned動画を別セットで追加しました。撮影時の公開元SHA、CI、Pages、個別hashは新セットのmanifestに記録しています。最終素材commitのCI・Pages・raw URL照合結果は納品報告で特定します。

公開入口：[Advanced PLATEAU 3D](https://catlover-bot.github.io/plateau-city-gap/?experience=advanced&task=detail&scene=plateau_detail&mapMode=plateau3d&selectionType=mesh&selection=533513314)。UI sourceは `49a8d02a308908d9bd3950e5d7429d051a67a678`、[CI 33946246589](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33946246589) は9/9、[Pages 33946478209](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33946478209) はbuild/deployとも成功。公開entryと全10 JS/CSSのSHA-256はローカルproduction buildと一致しています。

ローカル検証はESLint、TypeScript、36 test files / 183 tests、production build、既存Guided 6 Area・29 snapshot、Guided→Advanced 6 flow、Public first-run、PLATEAU-native 19/19、5 viewport表示、従来Spatial Pack/X-Ray strict captureを通過しました。Guided実3Dの建物選択・断面/focus・対象別項目・2D往復・非対応/古いArea拒否・390px失敗/再試行も通過しています。新Advancedでは実建物の選択、同じA–B、exact target、親メッシュ付きURL再読込、390px表示を確認済みです。デスクトップ/390px・断面開閉4状態でaxeのserious/criticalと検出されたcontrast違反は0。ただしcanvas/SVG等のcontrast判定にはincompleteが残り、全画素の自動アクセシビリティ保証ではありません。視覚確認はagentによるもので、人間の利用テストではありません。

Advancedの常団地前周辺では、地域の集計 → 3D → 同じA–B断面 → 選んだ対象の公式属性・未確認項目を一画面で対応させます。「分析ツール」から従来の操作へ戻れ、明示的なSpatial Pack/X-Ray直リンクや別地域・別sceneは従来の表示を保ちます。Guided→Advancedのfull-data single-flight loaderは変更していません。新画面の地域・断面の取得と3D readinessにも有限の待ち時間、再試行、地図への戻り口があります。

ここでPLATEAUを使う理由は、500mの人口・距離集計にはない、公式の建物立体形状・高さ・用途と道路・地形の位置関係を読むためです。色付きの集計図だけでは建物の高さや断面の高低差を示せません。ただし、PLATEAUだけが唯一の方法という主張や、LOD1で入口・通行可否が分かるという主張はしません。

| 審査軸 | 新しいAdvancedで提示する事実 | 未検証・主張しないこと |
| --- | --- | --- |
| 3D都市モデルの活用度 | 実3D Tilesの選択IDと公式属性、実DEM・道路、同一packのA–B断面を対応させる | LOD2表示、未収録属性の補完、歩行可能性の判定 |
| アイデア・独創性 | Guidedの同じ地域からAdvancedへ進み、集計・立体・個別対象・未確認項目をつなぐ実装 | 世界初、独創性の外部評価、利用者理解度の検証 |
| 地域課題への貢献度 | 地域を探す材料と、入口・利用状況・通行条件を現地で確認する具体的対象を提示する | 自治体採用、時間削減、課題解決効果、人間テスト結果 |

exact targetは、選択地物IDが同じ地域のhash照合済みgeometryに一致した場合だけ表示します。道路面の配布表記差（末尾 `-0` / `:0`）は実ID対応として扱い、描画側IDと対象IDを分けて保持します。共有URLは既存の親メッシュを明示的に保持し、未登録・別地域のIDをexactと推定しません。URLだけで復元した建物は、Area contextに高さ・階数がない場合「データなし」と表示し、モデルを再選択すると実属性を読みます。

### 新しいAdvanced発表素材

保存先は `docs/assets/judging-advanced-3d/`。前の2セットは上書きしていません。次の4枚は公開UIのnative 1920×1080の実画面で、合成・切り抜き・拡大はありません。

| 画像 | 発表で伝えること |
| --- | --- |
| [01 · Advanced 3D Hero](assets/judging-advanced-3d/01-advanced-3d-hero.png) | 立体を読む目的、同じ地域の集計、建物・地形の位置関係 |
| [02 · Advanced 3D + Urban Section](assets/judging-advanced-3d/02-advanced-3d-section.png) | 3D上のA–Bと同じ断面、建物・道路名・標高・距離の対応 |
| [03 · Advanced 3D + Exact Target](assets/judging-advanced-3d/03-advanced-3d-exact-target.png) | 実際に選んだ建物の公式属性と、その建物の未確認3項目 |
| [04 · Guided → Advanced](assets/judging-advanced-3d/04-guided-to-advanced.png) | 実際のGuidedからの移動後、同じ常団地前周辺を深掘りする画面 |

[40秒・字幕なし原本](assets/judging-advanced-3d/city-gap-advanced-3d-clean.mp4) / [同じ原本からの字幕付き版](assets/judging-advanced-3d/city-gap-advanced-3d-captioned.mp4) / [字幕VTT](assets/judging-advanced-3d/captions.vtt) / [個別hash・出典・描画証拠manifest](assets/judging-advanced-3d/manifest.json)

動画は1回収録した原本です。二尾周辺から常団地前周辺への実選択が1.093秒、Guided 3Dが3.444秒、Guided断面が6.365秒、詳細分析への実クリックが9.279秒、Advanced 3Dが11.267秒、実建物選択が19.993秒、Advanced断面が26.036秒、同じexact targetの確認が35.533秒。途中の画面遷移や読み込みを削除していません。収録は単調増加時計で40.0008365秒、全1,435取得フレームがnative 1920×1080。原本・字幕版の出力はいずれも40.000秒、1,200フレーム、H.264 / yuv420p / 30fps / 音声なしです。可変間隔の取得を30fpsへ正規化しており、静止holdの複製と余剰フレームのdropがあります。AI補間や拡大はありません。250ms間隔の実レンダラー/canvas観測で3D表示を確認できた割合は約89.65%で、連続全画素判定やcold-load性能を意味しません。

1回目の収録と画像04は完了しましたが、その後の画像用ズームでstrict撮影条件の待機が完了しませんでした。原本・元の報告・画像04を保全し、別の新しい実ブラウザcontextで画像01〜03と親メッシュURL/390px確認だけを取得しました。再録画や条件フラグの書き換えはしていません。字幕調整前の版、取得フレーム、失敗時の一時記録も削除していません。

既存のnative capture helperを使う追加driverは `frontend/scripts/capture-advanced-3d.mjs` です。収録時driverと、収録後に実測時刻に合わせた8字幕cue・以後の静止画操作を調整した納品driverは別のhashとしてmanifestへ記録しています。納品driverを使って過去の原本を収録したとは扱いません。素材commit自身のSHAは循環参照を避けてmanifestへ埋め込まず、immutableなraw URLを含む最終報告で確定します。

公開版でも既存Guided spatial、Guided→Advanced、Public first-run、PLATEAU-native、5 viewport表示を通過し、予期しないconsole/page/request/HTTP診断は0でした。追加のAdvanced実建物選択、A–B、exact target、URL再読込、390px確認も通過しました。道路135面のID対応は実データを使うunit testで確認済みですが、この追加確認では3D画面上の道路直接クリックを成立させられず、手動ピック成功は主張しません。公開サービス・原本・字幕版・静止画はagentが確認したもので、利用者理解度や自治体受入れの検証ではありません。

以下は変更せず保持する、以前のGuided 3Dと13秒補足素材の納品記録です。

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

## 追加素材：Guidedから詳細分析へ

追加作業の起点はfeature branchの `4d724f32e7c286ae8e8335d7c1b3d54ab5682ef2`。上記3D本編・既存画像・manifestを変更せず、別セット `docs/assets/judging-advanced/` を追加します。アプリ本体や分析値の変更はありません。この追加依頼では、素材commitのCI 9/9成功後に同じfeature branchからPagesを再deployし、公開runtimeと素材hashを確認します。最終commit/runは納品時の確認結果を参照してください。

| 追加ファイル | 発表で伝える内容 |
| --- | --- |
| [01-advanced-area-analysis.png](assets/judging-advanced/01-advanced-area-analysis.png) | 同じ常団地前周辺の500mメッシュについて、高齢者人口・公共交通距離・医療距離を詳細分析画面で確認 |
| [02-advanced-object-lens.png](assets/judging-advanced/02-advanced-object-lens.png) | 同じメッシュの出典・年度・人口・探索指標と、Finding / PLATEAU建物群・道路・DEMの関係を確認 |
| [city-gap-guided-to-advanced.mp4](assets/judging-advanced/city-gap-guided-to-advanced.mp4) | Guided 3D → 実際の「詳細分析」クリック → 同じ地域の指標 → Object Lensへのスクロールを13秒で示す |
| [manifest.json](assets/judging-advanced/manifest.json) | 個別SHA-256、production / UI / Pagesの撮影元、同一地域・実データとの対応、readinessと取得品質 |

確認入口：[Guided 3Dから詳細分析へ](https://catlover-bot.github.io/plateau-city-gap/?experience=guided&story=understand&mapMode=plateau3d)。常団地前周辺が表示されたことを確認し、右上の「詳細分析」を押します。詳細分析の右側Inspectorを下へスクロールすると、同じ地域のObject Lensに出典と関係情報が表示されます。撮影で実際に生成されたAdvanced URLもmanifestへ記録しています。

表示値は公開 `mesh_metrics.geojson` の実レコード `533513314` と照合しました。人口471、65歳以上人口200、公共交通563m、医療1,451m、探索指標 `0.2796852274821857`。距離の未丸め値は562.5974946252306m / 1450.5478993305774mです。国勢調査2020の500m集計と既存CITY GAP分析であり、PLATEAU建物別の実居住者数ではありません。距離はメッシュ中心からの直線距離で、歩行距離・所要時間ではありません。探索指標は危険度や政策順位を断定するものではありません。

公開データSHA-256は `1de17511f925dcb1e633096fc5ad417e61a4b5b1fc8daf0d6e1e4c7b782dc044` でローカルと一致。UIのentryと全10 JS/CSSも撮影前に公開版と照合しました。別地域 `533512753` を参照する既存の一般「根拠を見る」ダイアログや、市全体の仮想施策値は、この地域の分析として素材に使用していません。

動画は1回収録、native 1920×1080、13.000秒、H.264 / yuv420p / 音声なし。実取得160フレームを静止holdの複製等で出力390フレーム・30fpsに正規化しています。拡大、AI補間、値の注入、loading画面の削除、別録画のつなぎ合わせはありません。1.800秒で実際に「詳細分析」をクリックし、2.598秒でfull-data / map-style準備が完了しました。静止画には別途strict / visual readinessを確認しています。動画1秒・6秒・11秒のデコード画像と全体のデコード完了を確認済みです。

残る制約：素材はInspectorの実指標・出典・関係情報が中心で、地図上の選択メッシュ境界や分析色面は表示されていません。既存のズーム操作による静止画1枚の構図確認でも色面は現れず、その試行は保全し、元の画像を採用しました。架空の境界や色面は追加していません。HTTP cacheをprewarmし、既存の初期Area選択で実属性を取得してから撮影したため、cold-load速度の証拠ではありません。IDだけを指定したAdvanced直リンクでは、既存仕様により上部の指標が未入力になる場合があります。その場合はこのGuided入口経由、または実際の同じ地域の再選択を使ってください。Object Lensは元データから地域を照合します。文字は実UIのままで、閲覧時の縮小率に依存します。利用者の理解度、自治体での業務効果・受入れは未検証です。撮影時の一時ファイルと以前の素材は保全しています。
