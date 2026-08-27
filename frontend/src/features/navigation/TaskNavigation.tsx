import { PRODUCT_ROUTES } from "../../app/routes";
import type { ProductTask } from "../../state/spatial/types";

interface Props {
  value: ProductTask;
  onChange(task: ProductTask): void;
}

export function TaskNavigation({ value, onChange }: Props) {
  return (
    <nav className="task-navigation" aria-label="目的を選ぶ">
      {PRODUCT_ROUTES.map((route, index) => (
        <button
          key={route.id}
          type="button"
          className={value === route.id ? "active" : ""}
          aria-current={value === route.id ? "page" : undefined}
          onClick={() => onChange(route.id)}
        >
          <span aria-hidden="true">{index + 1}</span>
          <strong>{route.shortLabel}</strong>
          <small>{route.description}</small>
        </button>
      ))}
    </nav>
  );
}
