# Municipal Open Data Platform final audit

`python -m analysis.scripts.audit_open_data_platform`は、要求されたGoal 1〜120を、
registry、migration、実データ成果物、製品UI、security、性能証跡へ対応付けて再検証する。
成果物は
`analysis/outputs/real/open_data/open_data_platform_final_audit.json`である。

2026-08-29監査は42 checkすべてに合格し、120 Goalを欠番なく記録した。107件は実装・実データ証跡を
`verified`、13件は`verified_boundary`とした。後者は未実装を隠す状態ではなく、公式公開状況を確認した上で
`outside_coverage`、`requires_review`、`not_verified`またはBASE降格を製品へ実装した状態を意味する。
通いの場、WAM NET、GSI、公式歩行network、xROAD、駅利用、GTFS、Person Tripをanalysis-readyとは主張しない。

実データ成果は、舞鶴catalog 30 dataset、藤沢公式linked catalog 9 dataset、4系列合計18,203 canonical
record、822 audited mesh、50 review candidate Findingである。MHLW 43 resource、人口・経済4 resource、
地盤・事故3 primary resourceはcontent hashとsource reportへ追跡できる。Public Showcaseへraw bytesは配布しない。

性能証跡はGitHub Actions run `33185736512`の100k building / 100k road PostGIS fixtureを使用する。
これは`SYNTHETIC_SCALE`で、実都市offline pipelineは`REAL_MUNICIPAL_DATA`として分離する。cold/warm、
concurrency 1/10/25/50の結果はいずれもproduction SLAではない。

同runではfrontend、security、validation-gates、python-unit、api-integration、postgis-integration、migration、
public-assets、buildの9 gateが成功した。最終commitのCIは別途GitHub Actionsで再検証する。

残る外部作業は、WAM resource条件、GSI credential・測量法review、公式歩行network/GTFSの未確認、
xROAD安定snapshot、駅/PTのcanonical未昇格、自治体production OIDC・法務・公開承認である。
