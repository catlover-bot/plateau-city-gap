export type FieldQueueStatus = "pending" | "applied" | "conflict" | "rejected";

export interface SelectedFieldPackage {
  offline_package_id: string;
  package_version: number;
  content: Record<string, unknown>;
}

export interface QueuedFieldOperation {
  client_operation_id: string;
  offline_package_id: string;
  base_record_version: number;
  payload: Record<string, unknown>;
  status: FieldQueueStatus;
  conflict_id?: string;
}

const DB_NAME = "citygap-selected-field";
const DB_VERSION = 1;

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("packages")) db.createObjectStore("packages", { keyPath: "offline_package_id" });
      if (!db.objectStoreNames.contains("operations")) db.createObjectStore("operations", { keyPath: "client_operation_id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function put(storeName: "packages" | "operations", value: object): Promise<void> {
  const db = await database();
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put(value);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

export async function cacheSelectedFieldPackage(value: SelectedFieldPackage): Promise<void> {
  await put("packages", value);
  navigator.serviceWorker.controller?.postMessage({
    type: "CACHE_SELECTED_FIELD_PACKAGE",
    packageId: value.offline_package_id,
    payload: value
  });
}

export async function queueFieldOperation(value: QueuedFieldOperation): Promise<void> {
  if (value.status !== "pending") throw new Error("新しいoffline操作はpendingで保存します");
  await put("operations", value);
}

export function applySyncResponse(
  operation: QueuedFieldOperation,
  httpStatus: number,
  response: Record<string, unknown>
): QueuedFieldOperation {
  if (httpStatus === 409) {
    const conflictId = response.conflict_id;
    if (typeof conflictId !== "string" || response.silent_last_write_wins !== false) {
      throw new Error("明示的なconflict応答が必要です");
    }
    return { ...operation, status: "conflict", conflict_id: conflictId };
  }
  if (httpStatus >= 200 && httpStatus < 300 && response.status === "applied") {
    return { ...operation, status: "applied" };
  }
  return { ...operation, status: "rejected" };
}
