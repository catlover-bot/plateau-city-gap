# CITY GAP design system

## Design intent

CITY GAPはSaaS管理画面ではなく、自治体職員・都市計画実務者・審査員が、根拠を追いながら地域候補を読むための空間情報プロダクトです。基調は「静かな公共性」「地図が主役」「編集された情報階層」です。

## Typography

- UI: `Yu Gothic UI`, `Hiragino Kaku Gothic ProN`, `BIZ UDPGothic`, Meiryo, system-ui
- 大きな実数: Georgia / `Yu Mincho` fallback。数値だけに限定し、装飾的な見出し乱用はしない
- Product name: 19px / 800 / letter-spacing 0.14em
- Region title: 20px、本文: 10px / line-height 1.75、metadata: 7–8px
- mesh codeとscoreは主見出しにせず、折りたたみ内の二次情報に置く

## Spacing

4pxを最小単位に、8 / 12 / 16 / 18 / 24 / 28pxを使用します。主要panelの内側は18px、要素間は14–18px、表のrowは8–12pxです。情報密度は保ちつつ、同じ意味の値を複数カードへ分割しません。

## Color roles

| Role | Color | Use |
|---|---|---|
| Paper | `#fafaf7` | header、map overlay |
| Panel | `#f7f7f3` | detail panel |
| Canvas | `#eceee9` | app background |
| Ink | `#202521` | primary text |
| Muted | `#687069` | explanation、metadata |
| Boundary / primary accent | `#2c716a` | active state、focus、city boundary |
| Decision accent | `#b37a18` | candidate rank、attention |
| Medical | `#a64f3f` | facility marker |
| Line | `#d4d6cf` | separators |

色は意味を補助するだけで、順位・選択・状態は線、label、数値も併用します。WCAG AAを目標に、本文を淡色の上へ薄く置きません。

## Border radius

基本は2pxです。mobile bottom sheetのみ8px、円形point markerのみ50%を許可します。情報カードのすべてを大きな角丸にしません。

## Shadows

通常panelはshadowなし。map上で地図と重なるpopover、dialog、bottom sheetだけに低い単一shadowを使います。発光、neon、内外の多重shadowは使いません。

## Panels

- Desktop: header 64px、右context panel 390px、残りを地図に割り当てる
- Detail initial view: 地域名 → 65歳以上/人口/率 → 交通・医療距離 → WHY → 最寄り施設 → raw計算値
- Ranking: 連続したrow。Top 10を10枚の独立した大カードにしない
- What-if: 候補地 → 理由 → Before/After距離 → 影響範囲 → 注意事項
- Fujisawa: Ranking / Detailのみ。3D・What-ifの完成度を装わない

## Map overlay rules

- 地図はdesktop表示面積の約70%、mobileではheader下の全画面背景
- overlayは不透明に近いpaper色と1px border。glass blurを使わない
- 初期説明は350px以内、地図の主要範囲を隠さない
- metric switch、layer、legend、sourceは別々の責務を持ち、同じ情報を重複表示しない
- map色は中彩度。選択meshは色だけでなく輪郭を太くする

## Interaction rules

- 初期表示は舞鶴市Rank 1のDetail。10秒で価値と根拠が読める
- 主導線: 探す → 理由を読む → 3Dで確認 → 施策を試す
- Storyのlayer transitionは短く、`prefers-reduced-motion`では実質停止
- focus ringは3px。dialogは初期focus、focus trap、Escape、元要素への復帰を実装
- touch targetは原則36px以上、mobileの主要操作は43px以上
- mobileはmapを背景にしたbottom sheetとし、document横overflowを許さない

## Prohibited visual patterns

- 紫〜青のgradient、gradient text、neon、glassmorphism、背景blur
- AI sparkle、robot、emojiを主要iconとして使うこと
- giant hero、stock photo、blob、floating decorative object
- 3枚同格feature card、全情報のcard化、16px以上の角丸乱用
- generic SaaS sidebar、KPI dashboard、dark modeをPrimary identityにすること
- 「AIが課題を発見」「最適解」「96%改善」のように根拠以上の確度を示す文言

## Review checklist

1. CITY GAPの価値が10秒で分かるか
2. 地図が最も大きい面積を占めるか
3. Rank 1の実数がscoreより先に読めるか
4. 市内相対値と絶対距離を混同していないか
5. 舞鶴Primaryと藤沢Validationの役割が明示されるか
6. 3DとWhat-ifの範囲を誇張していないか
7. desktop 1440×900 / 1280×800で衝突しないか
8. mobile 390×844で横overflowしないか
9. keyboard、focus、reduced-motionで操作できるか
10. 一見してAI生成templateやSaaS dashboardに見えないか
