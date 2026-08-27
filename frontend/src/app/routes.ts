import type { ProductTask } from "../state/spatial/types";

export interface ProductRoute {
  id: ProductTask;
  label: string;
  shortLabel: string;
  description: string;
}

export const PRODUCT_ROUTES: ProductRoute[] = [
  { id: "discover", label: "課題を探す", shortLabel: "探す", description: "CITY GAP screening" },
  { id: "detail", label: "詳しく見る", shortLabel: "詳しく", description: "PLATEAU building / road / terrain" },
  { id: "try", label: "施策を試す", shortLabel: "試す", description: "Scenario / Futures / Stress Test" },
  { id: "validate", label: "結果を検証する", shortLabel: "検証", description: "Reference / Sensitivity / Temporal" },
  { id: "operate", label: "業務で運用する", shortLabel: "運用", description: "Field / Evidence / Admin" }
];

export const routeById = (id: ProductTask): ProductRoute => PRODUCT_ROUTES.find((route) => route.id === id) ?? PRODUCT_ROUTES[0];
