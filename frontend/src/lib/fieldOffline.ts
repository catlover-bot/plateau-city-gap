export type FieldQueueStatus = "pending" | "applied" | "conflict" | "rejected";

export interface SelectedFieldPackage {
  offline_package_id: string;
  package_version: number;
  organization_id: string;
  city_key: string;
  content: Record<string, unknown>;
}

export interface QueuedFieldOperation {
  client_operation_id: string;
  offline_package_id: string;
  organization_id: string;
  city_key: string;
  scenario_run_id: string;
  site_order: number;
  base_record_version: number;
  client_updated_at: string;
  payload: Record<string, unknown>;
  status: FieldQueueStatus;
  conflict_id?: string;
}

export interface LocalInvestigationSheet {
  sheet_id: string;
  candidate_id: string;
  updated_at: string;
  classification: "internal";
  content: Record<string, unknown>;
}

const DB_NAME = "citygap-selected-field";
const DB_VERSION = 2;

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("packages"))
        db.createObjectStore("packages", { keyPath: "offline_package_id" });
      if (!db.objectStoreNames.contains("operations"))
        db.createObjectStore("operations", { keyPath: "client_operation_id" });
      if (!db.objectStoreNames.contains("investigationSheets"))
        db.createObjectStore("investigationSheets", { keyPath: "sheet_id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function put(
  storeName: "packages" | "operations" | "investigationSheets",
  value: object,
): Promise<void> {
  const db = await database();
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put(value);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

async function getAll<T>(
  storeName: "packages" | "operations" | "investigationSheets",
): Promise<T[]> {
  const db = await database();
  const values = await new Promise<T[]>((resolve, reject) => {
    const transaction = db.transaction(storeName, "readonly");
    const request = transaction.objectStore(storeName).getAll();
    request.onsuccess = () => resolve(request.result as T[]);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return values;
}

export async function cacheSelectedFieldPackage(
  value: SelectedFieldPackage,
): Promise<void> {
  await put("packages", value);
  navigator.serviceWorker.controller?.postMessage({
    type: "CACHE_SELECTED_FIELD_PACKAGE",
    packageId: value.offline_package_id,
    payload: value,
  });
}

export async function saveLocalInvestigationSheet(
  value: LocalInvestigationSheet,
): Promise<void> {
  if (value.classification !== "internal") {
    throw new Error("現地メモをpublic分類では保存できません");
  }
  await put("investigationSheets", value);
}

export async function loadLocalInvestigationSheet(
  candidateId: string,
): Promise<LocalInvestigationSheet | null> {
  const values = await getAll<LocalInvestigationSheet>("investigationSheets");
  return (
    values
      .filter((value) => value.candidate_id === candidateId)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0] ?? null
  );
}

export async function queueFieldOperation(
  value: QueuedFieldOperation,
): Promise<void> {
  if (value.status !== "pending")
    throw new Error("新しいoffline操作はpendingで保存します");
  await put("operations", value);
}

export async function saveFieldOperation(
  value: QueuedFieldOperation,
): Promise<void> {
  await put("operations", value);
}

export async function queuedFieldOperations(
  organizationId: string,
  cityKey: string,
): Promise<QueuedFieldOperation[]> {
  const values = await getAll<QueuedFieldOperation>("operations");
  return values.filter(
    (value) =>
      value.organization_id === organizationId &&
      value.city_key === cityKey &&
      (value.status === "pending" || value.status === "conflict"),
  );
}

export function applySyncResponse(
  operation: QueuedFieldOperation,
  httpStatus: number,
  response: Record<string, unknown>,
): QueuedFieldOperation {
  if (httpStatus === 409) {
    const conflictId = response.conflict_id;
    if (
      typeof conflictId !== "string" ||
      response.silent_last_write_wins !== false
    ) {
      throw new Error("明示的なconflict応答が必要です");
    }
    return { ...operation, status: "conflict", conflict_id: conflictId };
  }
  if (httpStatus >= 200 && httpStatus < 300 && response.status === "applied") {
    return { ...operation, status: "applied" };
  }
  return { ...operation, status: "rejected" };
}
