# 建物起点アクセシビリティ（Priority 2）

## 起点と距離

人口配賦対象となるPLATEAU建物polygonから、polygon内に保証されるShapely
`representative_point()`を作る。名称は`building_origin_representative_point`であり、入口、玄関、
居住者入口ではない。EPSG:6674上のユークリッド直線距離を空間index付きnearest-neighborで求める。
これは歩行距離、道路経路、所要時間ではない。

対象は既存監査と同じ舞鶴市内駅7地点、バス停151地点、病院・一般診療所の医療施設71地点。
baselineは市内収録施設と一般利用不明医療を含み、感度では市境外2kmまで探索し、名称監査で
`uncertain_access`の医療を除く。建物recordには利用した`facility_policy`、施設名・種別、起点定義を残す。
実計算ではbaselineの交通点158・医療71に対し、conservativeは交通187・医療66だった。
`GET /cities/{city_id}/buildings/{gml_id}/accessibility`はこの2 policyを単一建物に限定して返す。

## 加重統計と500m中心との比較

各詳細meshで、建物の推計65歳以上人口を重みとして交通・医療距離の加重平均、加重中央値、加重p90を
計算する。加重分位は距離昇順の累積weightが`q × total_weight`以上となる最初の距離である。人口重みの
同等統計も保存する。

既存Screeningの`500m mesh centroid → facility`は変更しない。Priority 2は第二段階として
`PLATEAU住宅建物の実分布 → facility`を併記する。したがって新しいmagic scoreを作らず、
中心距離、建物加重平均、中央値、p90、差をcomponentとして示す。

深掘りmesh `533513314`では交通中心距離562.597mに対し住宅建物加重平均446.881m、中央値
439.296m、p90 597.506mだった。中心だけでは住宅の偏りとmesh内の距離分布を再現できない。
医療は中心1,450.548m、加重平均1,444.717m、中央値1,457.586m、p90 1,586.613mで、平均差は
小さい一方、遠い側の分布をp90が示す。
この深掘りmeshでは2km越境conservativeでも同じ施設が最寄りとなり、各加重統計は変わらなかった。

## 施設境界と次段階

行政界は生活圏の障壁ではないため、baselineと2km cross-border conservative sensitivityを分離して
保存する。医療区分は施設種別が一般利用可能性を保証しないので、名称規則は削除ではなく不確実flagに使う。

Priority 3では道路network、接続、横断、勾配、通行条件を監査し、建物起点をnetworkへsnapして経路距離へ
移行する。それまでは画面・API・文書の全てで「直線分析距離」と明記し、walking routeとは呼ばない。
