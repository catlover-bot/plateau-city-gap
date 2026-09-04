import { useEffect, useState } from "react";
import type { SectionData } from "./sectionTypes";

const DEFAULT_PACK_ID = "maizuru-533513314-plateau-2025-v1";

function publicUrl(path: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
  return `${base}${path}`;
}

interface Options {
  dataOverride?: SectionData | null;
  sourcePath?: string | null;
  expectedPackId?: string;
}

export function useSectionData({ dataOverride, sourcePath, expectedPackId }: Options) {
  const [loadedData, setLoadedData] = useState<SectionData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (dataOverride !== undefined) return;
    const resolvedPath = sourcePath === undefined
      ? `data/spatial-packs/${DEFAULT_PACK_ID}/sections.json`
      : sourcePath;
    if (!resolvedPath) return;
    const controller = new AbortController();
    setLoadedData(null);
    setError(null);
    fetch(publicUrl(resolvedPath), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<SectionData>;
      })
      .then((value) => {
        if (expectedPackId && value.pack_id !== expectedPackId) {
          throw new Error("断面とAreaのpackが一致しません");
        }
        setLoadedData(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "断面を読み込めません");
        }
      });
    return () => controller.abort();
  }, [dataOverride, expectedPackId, sourcePath]);

  return {
    data: dataOverride !== undefined ? dataOverride : loadedData,
    error,
  };
}
