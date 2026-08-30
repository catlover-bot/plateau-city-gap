import type { DataGap, InvestigationWorkspace } from "./investigationTypes";

export const VALUE_HYPOTHESES: InvestigationWorkspace["valueHypotheses"] = [
  {
    id: "H1",
    statement: "交通・医療アクセスを追加確認すべき地域の選定には、複数データの収集・加工が必要である。",
    status: "AWAITING_MUNICIPAL_REVIEW",
  },
  {
    id: "H2",
    statement: "候補を500mだけでなく建物・道路・地形まで確認できることに価値がある。",
    status: "AWAITING_MUNICIPAL_REVIEW",
  },
  {
    id: "H3",
    statement: "順位や地図だけでなく、現地確認項目がまとまった資料が必要である。",
    status: "AWAITING_MUNICIPAL_REVIEW",
  },
  {
    id: "H4",
    statement: "出典付き調査サマリーを庁内・交通事業者・コンサルとの協議に使える。",
    status: "AWAITING_MUNICIPAL_REVIEW",
  },
];

export const MUNICIPAL_REVIEW_QUESTIONS = [
  "現在、交通や医療へのアクセスを確認すべき地域はどのように選んでいますか？",
  "常団地前周辺・二尾周辺等は、実際に追加確認する価値がある候補に見えますか？",
  "候補地区一覧・地図・候補理由・PLATEAU詳細・不足データ・現地確認票・庁内共有資料のうち、業務に必要なのはどれですか？",
  "この作業に現在どの程度の期間・担当者・外部委託が必要ですか？",
  "この出力を誰との協議に使いますか？",
] as const;

export const ADOPTION_QUESTIONS = [
  "この候補一覧を使いますか？",
  "この現地調査票を使いますか？",
  "どの会議・協議で使いますか？",
  "何が足りませんか？",
  "既存資料より便利ですか？",
] as const;

export const PIVOT_CONDITIONS = [
  "地域候補選定業務が存在しない",
  "候補地域が実務上無意味",
  "現地調査票が使われない",
  "既存ツールで十分",
  "必要な判断単位が異なる",
  "交通・医療の組合せが業務に合わない",
] as const;

export const BASE_DATA_GAPS: DataGap[] = [
  {
    id: "gtfs",
    title: "運行頻度・曜日・時間",
    known: "収録された駅・バス停の位置と直線距離",
    unknown: "現在の運行本数、曜日、時間、デマンド交通、施設送迎",
    sourceBoundary: "国土数値情報P11 2022には停留所位置はあるが運行情報は含まれない。",
  },
  {
    id: "walking_network",
    title: "実際の歩行経路",
    known: "PLATEAU道路面の形状",
    unknown: "歩行可否、歩道、横断、段差、建物入口から道路への接続",
    sourceBoundary: "公式歩行ネットワークを収録していない。道路形状は歩行可能性を保証しない。",
  },
  {
    id: "facility_availability",
    title: "医療・介護施設の現在の利用条件",
    known: "収録施設の位置と種別、メッシュ中心からの直線距離",
    unknown: "現在の営業、診療科、受入・予約条件、送迎、利用資格",
    sourceBoundary: "国土数値情報P04 2020は現在の利用可能性を保証しない。",
  },
  {
    id: "local_services",
    title: "地域内の既存サービスと移動実態",
    known: "公開データに収録された交通・施設",
    unknown: "自治会交通、地域送迎、住民の実際の移動先、季節・時間帯の変化",
    sourceBoundary: "地域内運用や住民行動は現在の公開データだけでは把握できない。",
  },
];

export function plateauCoverageGap(): DataGap {
  return {
    id: "plateau_coverage",
    title: "PLATEAU建物・道路の詳細",
    known: "500m単位の人口・交通・医療分析",
    unknown: "関係する個別建物、道路面、詳細な地形との関係",
    sourceBoundary: "公式PLATEAU舞鶴市2025を検査したが、この候補500mには建物モデルが収録されていない。",
  };
}

export const CANDIDATE_TYPE_COPY = {
  screening: [
    "分析上の候補",
    "人口・交通・医療の条件から、追加確認する価値があるかを人が仕分ける候補です。",
  ],
  detailed_investigation: [
    "詳細調査例",
    "PLATEAU建物・道路・地形まで確認できるため、現地調査票まで具体化できる候補です。",
  ],
  data_gap: [
    "データ確認候補",
    "分析上は気になりますが、詳細データが不足しているため、先に不足情報を確認する候補です。",
  ],
} as const;
