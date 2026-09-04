import { useEffect, useRef, useState } from "react";
import { loadGuidedReferenceData, type GuidedReferenceData } from "../../lib/data";
import type { GuidedStory } from "../../state/spatial/types";
import type { AppData } from "../../types";
import type { SectionData } from "../urban-section/sectionTypes";
import {
  loadGuidedAreaCatalog,
  loadGuidedAreaContext,
  loadGuidedSectionData,
} from "./guidedData";
import type { GuidedAreaContext, GuidedAreaContextCatalog } from "./guidedTypes";

export type GuidedContextStatus = "idle" | "loading" | "ready" | "error";

export function useGuidedAreaContext(data: AppData, story: GuidedStory, selectedAreaId: string) {
  const [catalog, setCatalog] = useState<GuidedAreaContextCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [context, setContext] = useState<GuidedAreaContext | null>(null);
  const [contextStatus, setContextStatus] = useState<GuidedContextStatus>("idle");
  const [contextError, setContextError] = useState<string | null>(null);
  const [sectionData, setSectionData] = useState<SectionData | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [referenceData, setReferenceData] = useState<GuidedReferenceData | null>(() => (
    data.stations || data.busStops || data.medicalFacilities
      ? { stations: data.stations, busStops: data.busStops, medicalFacilities: data.medicalFacilities, warnings: [] }
      : null
  ));
  const requestSequence = useRef(0);
  const contextCache = useRef(new Map<string, GuidedAreaContext>());
  const activeContextRef = useRef<GuidedAreaContext | null>(null);
  const sectionDataRef = useRef<SectionData | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadGuidedAreaCatalog(controller.signal)
      .then(setCatalog)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setCatalogError(reason instanceof Error ? reason.message : "Area catalogを読み込めません");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (story === "intro" || story === "find" || referenceData) return;
    let cancelled = false;
    loadGuidedReferenceData(fetch, import.meta.env.BASE_URL)
      .then((value) => { if (!cancelled) setReferenceData(value); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [referenceData, story]);

  useEffect(() => {
    const item = catalog?.items.find((candidate) => candidate.mesh_code === selectedAreaId);
    const sequence = ++requestSequence.current;
    setContextError(null);
    if (activeContextRef.current?.mesh_code !== selectedAreaId) {
      activeContextRef.current = null;
      sectionDataRef.current = null;
      setContext(null);
      setSectionData(null);
      setSectionError(null);
    }
    if (story === "intro" || story === "find") {
      setContextStatus("idle");
      return;
    }
    if (activeContextRef.current?.mesh_code === selectedAreaId) {
      setContextStatus("ready");
      return;
    }
    if (!item) {
      setContextStatus(catalog ? "error" : "idle");
      if (catalog) setContextError("選択した範囲のPLATEAUデータを確認できません");
      return;
    }
    const cached = contextCache.current.get(selectedAreaId);
    if (cached) {
      activeContextRef.current = cached;
      setContext(cached);
      setContextStatus("ready");
      return;
    }

    const controller = new AbortController();
    setContextStatus("loading");
    loadGuidedAreaContext(item, controller.signal)
      .then((value) => {
        if (requestSequence.current !== sequence) return;
        contextCache.current.set(selectedAreaId, value);
        activeContextRef.current = value;
        setContext(value);
        setContextStatus("ready");
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted || requestSequence.current !== sequence) return;
        setContextStatus("error");
        setContextError(reason instanceof Error ? reason.message : "範囲のPLATEAUデータを読み込めません");
      });
    return () => controller.abort();
  }, [catalog, selectedAreaId, story]);

  const activeContext = context?.mesh_code === selectedAreaId ? context : null;

  useEffect(() => {
    setSectionError(null);
    if (story !== "understand" || activeContext?.section.status !== "available") return;
    if (sectionDataRef.current?.pack_id === activeContext.section.pack_id) {
      setSectionData(sectionDataRef.current);
      return;
    }
    setSectionData(null);
    const controller = new AbortController();
    loadGuidedSectionData(activeContext.section, controller.signal)
      .then((value) => {
        sectionDataRef.current = value;
        setSectionData(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setSectionError(reason instanceof Error ? reason.message : "断面を読み込めません");
        }
      });
    return () => controller.abort();
  }, [activeContext, story]);

  return {
    catalog,
    catalogError,
    context,
    activeContext,
    contextStatus,
    contextError,
    sectionData,
    sectionError,
    referenceData,
  };
}
