# Visual system

CITY GAPの視覚言語は「日本の行政調査図面」である。一般的なSaaS dashboardやカード一覧ではなく、地図、縮尺、凡例、注記、object関係を一枚のworkbenchとして読めることを優先する。

## Principles

1. 地図を主役にする。desktopでは調査面の大半をmap canvasへ割り当てる。
2. 境界と階層を線で示す。浮いたcard、pill、過剰なshadowでgroupingしない。
3. 色は意味に限定する。tealは選択・根拠、amberは分析・注意、赤は検証済みの警告だけに使う。
4. 数値にはsource、year、method、limitationへの到達経路を持たせる。
5. Scene、Resolution、Lens、Selectionを視覚的にも混同しない。

## Palette and material

| Token | Role |
|---|---|
| paper | 調査票、inspector、注記面 |
| stone | 背景、非選択地物、区画 |
| graphite | 文字、境界、操作rail |
| teal | 選択、PLATEAU object、trace |
| amber | X-Ray、差分、条件付き注意 |

gradientは使わない。角丸は原則0–3px、shadowはmap上の判読性に必要な最小限だけとする。可読性のための半透明面は、装飾ではなくmap overlayとして扱う。

## Workbench anatomy

```text
Header: city / urban state / purpose / evidence
┌──────┬───────────────────────────────┬─────────────┐
│Task  │ Scene tabs + Map canvas       │ Inspector   │
│rail  │ Resolution breadcrumb         │ Finding     │
│      │                               │ PLATEAU     │
│      │                               │ Object Lens │
│      │ Lens / legend / source        │ Relations   │
└──────┴───────────────────────────────┴─────────────┘
```

- Task rail: 探す、詳しく、試す、検証、運用。業務段階でありSceneではない。
- Scene tabs: 調査テーマを切り替える。
- Resolution breadcrumb: cityからsiteまでの粒度を示す。
- Analysis Lens rail: X-Ray、Pulse、Twin、Ghostを明示的に重ねる。
- Context Inspector: 選択Findingの集計とclaim boundary。
- Object Lens: PLATEAU objectの属性、関係、Findingへの逆引き。

## Cartography

- meshは発見単位、building/roadは検証単位として線幅とz-orderを分ける。
- 選択objectだけを高彩度にし、周辺contextはstone/graphiteへ落とす。
- X-Ray surface、実terrain、道路、建物はlegendで別物と示す。
- labelはsource objectと分析注記を区別する。
- 3D cameraはcity / mesh / building / route / hazard / scenario intentから決定し、正規画像で手動位置を使わない。

## Typography and density

日本語本文は読みやすいsystem sans、識別子・mesh code・source IDはmonospaceを使う。見出しは小さなuppercase kickerと日本語headlineの組合せにする。余白をカードの装飾へ使わず、地図、table、relation rowの判読性へ使う。

## Responsive behavior

desktopはmapとinspectorを同時表示する。mobileではmapを維持し、railを圧縮、inspectorを縦方向へ流す。機能を別の簡易画面へ置換せず、同じselectionとclaim boundaryを保持する。touch targetは44pxを下回らない。

## Motion

motionは状態変化の説明に限る。Service Pulseはprecomputed route位置を使い、`prefers-reduced-motion` ではanimationを停止してstatic distance bandsだけを残す。camera移動も同設定では即時遷移し、readiness判定を妨げない。

## Screenshot acceptance

Public comprehensionの正規画像は `docs/assets/current/` の8枚だけをcanonicalとする。Landingから同じGuided Investigationを完走し、各画像で現在の問い、実データ値、主操作、固定viewportを検証する。Step 3・4は実PLATEAU都市断面が非空であることを必須とし、3D準備中なら未完了を明示した静的断面として記録する。8枚すべてとmanifestをstageで検証できた場合だけcurrentを入れ替え、console errorまたはcritical request failure時は既存currentを保持する。完全なterrain/building/camera readinessが必要な高度分析captureは `capture:advanced` で別に検証する。
