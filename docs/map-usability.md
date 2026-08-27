# Map usability audit

## Before implementation

基準commit `551570c83ab320517ecbca94aa421f5b3180e121` のGitHub Pagesを、1440×900、1280×800、1024×768、768×1024、390×844で撮影した。原画像は `docs/assets/product-v2/baseline/` に保存している。

主要所見は次の通りだった。

1. 500m比較の初期画面がpitch付きCesiumで、地理的文脈より3D rendererが先に立つ。
2. mesh、候補、施設、PLATEAU、story overlayが一つの表示規則で競合する。
3. 「PLATEAU 3D・道路」が建物と道路を一括化し、DEM・計画・災害を独立管理できない。
4. 5 workspace、2都市、方法論がbutton wallになり、mobileで最初の選択肢が製品構造になっている。
5. city/state/selection/map modeをworkflow間で共有・URL復元する契約がない。
6. Validationの主地図はbasemapを持たないSVGで、市内の場所を読めない。
7. 内部status名が平易な意味より先に出る。
8. legend、layer、metric、story、右panelの操作モデルが統一されていない。
9. tablet/mobileがdesktop UIの折返しで、map-firstのbottom sheetになっていない。
10. routing/state/render/styleの責務が巨大componentへ集中している。

完全なbefore判定は [Product System baseline audit](product-v2-baseline-audit.md) を参照。

## After implementation

- MapLibre + 地理院淡色地図を発見・比較のprimary 2D engineとし、Cesiumは明示的PLATEAU detailへlazy loadする。
- 26 layerの中央Registry、8 ScenePreset、5 resolution、typed selectionを一つのstate machineへ統合した。
- 1440pxでは地図stageを主幅とし、Context Inspectorを右側へ固定する。tabletはInspector overlay、mobileはbottom sheetへ変える。
- mesh fill opacityを抑え、selection outline、semantic zoom、POI clusteringで背景図を残す。
- 3Dでは建物、道路、実DEM、scenario、hazard stressを同じsceneで比較する。
- URL deep link、5段Presentation Guide、Contribution Inspectorで発見→根拠→施策→reviewを再現する。

## Production audit result

`docs/assets/spatial-v1/audit.json` はmockではなくproduction buildをheadless Chromiumで操作して生成した。

| viewport | map stage | viewport幅比 | Inspector | 横overflow |
|---|---:|---:|---|---|
| 1440×900 | 1070×784 | 74.3% | 右column | なし |
| 1280×800 | 910×684 | 71.1% | 右column | なし |
| 1024×768 | 694×662 | 67.8% | 右column | なし |
| 768×1024 | 768×918 | 100% | overlay | なし |
| 390×844 | 390×746 | 100% | bottom sheet | なし |

1440px baselineは右detail境界がx=1050で、mapの名目幅は72.9%だった。afterは74.3%である。差の中心は面積だけではなく、baselineの地理背景が描画されず点群だけだった状態から、地理院淡色地図、市境、semantic zoom、選択outlineが読める状態へ変わった点にある。

5実操作workflowはすべてdead end 0。発見→PLATEAU detailは2 click / 11.779秒、A/B/C切替4.212秒、通常→洪水stress 0.628秒、参照→年次差分0.509秒、ガイド01→02→03は3 click / 10.674秒だった。console error、local HTTP failure、external HTTP failureはいずれも0。

Accessibilityの構造監査はmain 1、nav 2、polite live region 1、map名 `共通Spatial Map`、focusable 47、無名button 0、alt欠落0、重複ID 0。最初の20 focus targetはDOM順で到達可能だった。これは専門家による支援技術テストや全状態の色コントラスト監査を置き換えない。
