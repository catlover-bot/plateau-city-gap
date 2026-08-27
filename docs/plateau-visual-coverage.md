# PLATEAU visual coverage and contribution matrix

基準日: 2026-08-28。`分析で利用` は再現可能なPython成果物へ接続済みであること、`画面で可視` は公開Workspaceに表示経路があることを意味する。分析済みという理由だけで3D表示済みとは数えない。

| PLATEAUテーマ | 分析で利用 | 画面で可視 | 初期表示 | 3D | 選択/比較 | provenance | 公開上の境界 |
|---|---|---|---|---|---|---|---|
| 建物 `bldg` | YES | YES | Scene依存 | YES | 建物click | 2025 CityGML / 3D Tiles | 全市44,640棟をcamera配信。Top 10は公式整備範囲と非重複 |
| 道路 `tran` | YES | YES | Scene依存 | YES | route/scene比較 | 2025 CityGML LOD1 | 道路面隣接graphは歩行者networkではない |
| 地形 `dem` | YES | YES | Scene依存 | YES | camera/scene | 2025 `dem:TINRelief` | 実TIN可視化はDeep Dive範囲のみ。広域はPLATEAU-Terrain |
| 土地利用 `luse` | YES | YES | NO | context overlay | 施策文脈比較 | 2025 CityGML | 公開3Dは集約済みscenario文脈。全地物streamではない |
| 都市計画 `urf` | YES | YES | NO | context overlay | 施策文脈比較 | 2025 CityGML | 計画との重なりは可否判定ではない |
| 洪水 `fld` | YES | YES | NO | stress/context | stress比較 | 2025 CityGML | 重なりを通行不能予測と扱わない |
| 土砂 `lsld` | YES | YES | NO | stress/context | stress比較 | 2025 CityGML | 道路利用不可は明示的counterfactual仮定 |
| 津波 `tnm` | YES | YES | NO | stress/context | stress比較 | 2025 CityGML | 被害・避難の予測ではない |

施設はPLATEAUテーマではないが、国土数値情報の駅・バス停・医療と、resilience成果物の影響施設を同じsceneへ接続する。建物別人口推計はprivacy-safeな公開境界を守り、個別値をWebへ出さない。

## Contribution Inspector

Inspectorの8タイルは `建物用途 / 高さ・階数 / 形状 / 道路LOD1 / DEM / 土地利用 / 都市計画 / 洪水` を表示する。各タイルは次のいずれかを明記する。

- `分析に使用`: スコア、配賦、経路、重なり、候補生成へ直接接続。
- `画面で確認`: 3D形状、属性、context、Evidenceの確認経路がある。
- `利用可能`: 公式sourceにはあるが、現在の選択や公開境界では結果へ未使用。

クリックは該当Scene、Layer、Evidenceへ移動する。存在しない属性は推定表示せず、`未収録` として保持する。
