# Public copy deck

Goal: `public-product-language-and-section-v1`

The proposed column is the H1 implementation deck. Exact source identity and dates remain available in `出典・データの注意点`; the initial reading path uses ordinary Japanese.

| Surface | Current | Problem | Proposed | Rationale |
|---|---|---|---|---|
| Header brand | `CITY GAP` | none | unchanged | Stable product identity. |
| Header context | `舞鶴市` | none | unchanged | Short and concrete. |
| Header utility | `詳細分析` | none | unchanged | Keeps Advanced visibly secondary. |
| Landing eyebrow | `舞鶴市の公開データを使った確認` | Repeats header/context and uses an abstract noun. | remove | One heading is enough. |
| Landing heading | `気になる場所を、地図とデータで確かめる。` | none material | unchanged | Concrete place, map, data, and verb. |
| Landing support | `場所と範囲を選ぶと、人口・年齢、建物の使われ方、事業所、都市計画、交通をまとめて確認できます。データだけでは判断できない点も整理します。` | Long and mechanically repeats `確認／整理`. | `場所と範囲を選ぶと、人口や建物、事業所、都市計画、交通をまとめて見られます。データだけでは分からないことも示します。` | Same contract in two shorter sentences. |
| Landing CTA | `地図で場所を調べる` | none | unchanged | One concrete action. |
| Landing disclaimer | `公開データの出典・時点・限界を表示します。政策判断や危険判定は行いません。` | A disclaimer wall before the user acts. | remove from Landing; retain claim boundaries in result details | Progressive disclosure without weakening the contract. |
| Progress | four circles and labels | Looks like a tutorial; duplicates headings. | `1 / 4　場所` (stage changes per screen) | Shows position without a mini navigation. |
| Place kicker | `場所を選ぶ` | duplicates heading | remove | Heading carries the job. |
| Place heading | `どこを調べますか？` | Conversational but a little vague. | `調べる場所を選ぶ` | Direct job label. |
| Station group | `駅から選ぶ` | okay | `駅を選ぶ` | Shorter. |
| Station CTA | `選んだ駅を起点にする` | Domain word `起点` is avoidable. | `この駅を選ぶ` | Ordinary action. |
| Map-point group | `地図上の任意地点` | GIS-like. | `地図から選ぶ` | Plain label. |
| Map-point help | `地図を動かし、現在の中心を起点にします。` | `現在` and `起点`; overexplains. | `地図を動かして、中心を調べたい場所に合わせます。` | Describes the physical action. |
| Map-point CTA | `地図中心を起点にする` | System/GIS language. | `この場所を選ぶ` | Ordinary action. |
| Census disclosure | `2020年国勢調査小地域（町丁・字等）について` | Accurate but dense. | `国勢調査の地域区分について` | Detail text retains the exact official name and warning. |
| Radius kicker | `範囲を選ぶ` | duplicates heading | remove | Heading carries the job. |
| Radius heading | `どの範囲を見ますか？` | okay but question pattern repeats. | `範囲を選ぶ` | Short job label. |
| Radius options | `500m / 800m / 1km / その他` | none | unchanged | Contract requires these exact labels. |
| Custom label | `半径（100〜3000m）` | none | unchanged | Necessary validation boundary. |
| Custom apply | `この半径を使う` | none | unchanged | Concrete. |
| Radius CTA | `この範囲を調べる` | Repeats `調べる`. | `この範囲を見る` | Short and consistent with result. |
| Radius disclosure | `800mの分析範囲について` | `分析範囲` is internal. | `半径800mについて` | Keeps methodology meaning without jargon. |
| 800m note | current MLIT/walking boundary sentence | Claim-safe | Meaning unchanged; punctuation only if needed | Walking-time boundary must remain exact. |
| Result kicker | `選んだ範囲の結果` | meta label | remove | Result heading is enough. |
| Result heading | `分かっていることと、まだ分からないこと` | Long and competes with both sections. | `この範囲で分かること` | Leads with the evidence users asked for. |
| Area/status pill | `西舞鶴駅周辺800m · 未確認` | Pill and repeated status. | `西舞鶴駅から半径800m` as plain text | Location context without status duplication. |
| Known heading | `この範囲で、データから確認できたこと` | Repeats page heading and sounds generated. | omit in Public; five story rows follow page heading | Less explanation, same reading order. |
| Story labels | `人口・年齢 / 建物の使われ方 / 事業所 / 都市計画 / 交通` | none | unchanged | Municipal-priority labels. |
| Metric status | `確認できた / 一部確認 / 未取得` on every metric | Badge repetition. | no badge for `known`; short text only for partial/unavailable | State remains without visual noise. |
| Story action | `地図で見る / 地図に表示中` | `表示中` sounds system-like. | `地図で見る / 地図に表示` | Secondary action remains legible. |
| Secondary data | `医療・介護・公共施設などの詳細データ` | slightly long | `その他のデータ` | Contents provide the detail. |
| Unknown heading | `ただし、まだデータだけでは分からないことがあります` | Sentence-like, overexplained. | `まだ現地で確かめたいこと` | Natural next job, no danger implication. |
| Unknown importance | fixture sentences | generally concrete | shorten only where the same reason repeats | Keep decision relevance from the contract. |
| Partial warning | `この情報は一部の範囲のみ確認できています。` | formal. | `確認できた範囲が限られています。` | Short, same boundary. |
| Result primary CTA | `確認場所を見る` | Slightly nominal. | `確認する場所を見る` | Natural phrase. |
| Target legend | `PLATEAU上の確認対象` | Internal/system wording. | `現地で確認する場所` | User job rather than implementation. |
| Exact map note | `PLATEAUの実形状` | accurate | `PLATEAUの建物・道路形状` when applicable | Makes the source tangible. |
| Position map note | `登録された位置情報のみ` | formal | `登録位置を表示` | Short. |
| Target map label | `実データ上の確認対象` | system wording. | `確認する場所` | One phrase across panel/map. |
| Target kicker | `確認場所と未確認項目` | Repeats next content. | remove | One target heading. |
| Target heading | `データだけでは分からないことを、場所で確かめる` | Slogan-like repetition. | `現地で確認する場所` | Direct job label. |
| Target section title | `{Area}の確認場所` | Duplicates page heading. | selected location name | The concrete place is primary. |
| Target lead | `データの限界から、現地で確かめる場所と3〜5件の確認項目を示します。` | Explains visible UI. | remove | Checklist is self-explanatory. |
| Target kind | `確認場所 / 範囲単位の確認` | okay, but fallback needs clarity | `確認する場所 / この範囲を確認` | Distinguishes object from honest fallback. |
| Task status | `未確認` on each card | repeated | one `未確認` near selected question | State remains clear once. |
| Check list | no heading; shown as list | purpose is implicit | add `現地で見るポイント` | Plain label for the 3–5 checks. |
| Target source | `対象データの出典` | system-like | `場所データの出典` | Plain and accurate. |
| Privacy boundary | `写真・GPS・回答・担当者・自治体の確認結果は作成も表示もしていません。` | Long list and implementation tone. | `この公開画面には、写真やGPSなどの現地記録はありません。` | Shorter; fake/restricted boundary remains. |
| Source disclosure | `出典・データの注意点` | none | unchanged | Accurate progressive disclosure. |
| Source intro | meta sentence about separating content | Explains UI architecture. | remove | The disclosure title is enough. |
| `coverage` | English internal term | Public terminology leak. | `データを確認できた範囲` | Japanese label. |
| `Area / version / content` | internal metadata line | Not meaningful to first-run user. | remove from visible prose; preserve machine provenance and source rows | Integrity without interface leakage. |
| Source object ID | raw code in details | Needs context | label `データ上の識別子` inside details only | Exact provenance remains available. |
| Cartography loading | `PLATEAU表示用データを準備中です` | Implementation-led. | `地図のデータを読み込んでいます` | User-facing state. |
| Degraded basemap | long generated CSS sentence | Slightly technical. | `背景地図を読み込めません。範囲とデータは表示しています。` | Short, honest degraded state. |
| Station error | `駅の位置を確認できませんでした。` | Could mean observation rather than load. | `駅の位置を読み込めませんでした。` | Describes failure. |
| Radius error | `その他の半径は100〜3000mの整数で入力してください。` | none | unchanged | Exact correction. |
| No target/fallback | existing honest mesh fallback | preserve semantics | `この範囲を確認` plus reason in details | No invented object. |
| 3D withheld | technical/UX reason stored in data attributes only | not first-view copy | keep hidden unless an actionable 3D control exists | Zero-button 3D remains valid. |

## Claim-safe phrases that remain

- the 800 m methodology continues to say it is a radius used as a general walking-area reference and **not** an actual ten-minute walking reach;
- the census boundary warning continues to distinguish statistical areas from current administrative, address, neighborhood, and municipal work areas;
- partial/missing sources are not filled with invented values;
- Public does not imply recommendation, safety, current/latest data, real-time state, or AI judgment.

