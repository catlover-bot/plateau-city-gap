import type { ProductRole } from "./types";

export const SERVICE_NAVIGATION = [
  { id: "home", label: "Home", description: "担当と都市状況" },
  { id: "cities", label: "Cities", description: "都市ワークスペース" },
  { id: "data", label: "Data", description: "登録・品質・年度" },
  { id: "analysis", label: "Analysis", description: "Findingと分析" },
  { id: "measures", label: "Measures", description: "Scenario比較" },
  { id: "review", label: "Review", description: "調査・現地・判断" },
  { id: "evidence", label: "Evidence", description: "根拠とReport" },
  { id: "operations", label: "Operations", description: "Job・更新・Release" },
] as const;

export const ROLE_LABELS: Record<ProductRole, string> = {
  viewer: "閲覧者",
  analyst: "分析担当",
  planner: "企画・計画担当",
  field_staff: "現地確認担当",
  data_manager: "データ管理担当",
  administrator: "管理者",
};

export const ROLE_HOME_LEAD: Record<ProductRole, string> = {
  viewer: "都市の更新状況とレビュー済み記録を確認できます。",
  analyst: "未整理のFindingから調査を開始し、再現可能な分析を実行します。",
  planner:
    "レビュー待ちの調査を確認し、人の判断をDecision Recordへ記録します。",
  field_staff: "割り当てられた現地確認をオフライン対応の記録へ残します。",
  data_manager: "データの品質検証、受入、分析可能化、昇格を管理します。",
  administrator:
    "テナント、利用者、ジョブ、データ更新とサービス状態を管理します。",
};
