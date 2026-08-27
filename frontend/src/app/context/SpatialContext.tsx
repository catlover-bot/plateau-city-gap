import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import { spatialReducer } from "../../state/spatial/reducer";
import { parseSpatialUrl, spatialStateToSearch } from "../../state/spatial/urlState";
import type { SpatialAction, SpatialState } from "../../state/spatial/types";

interface SpatialContextValue {
  state: SpatialState;
  dispatch: Dispatch<SpatialAction>;
  shareUrl: string;
}

const SpatialContext = createContext<SpatialContextValue | null>(null);

export function SpatialProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(spatialReducer, window.location.search, parseSpatialUrl);

  useEffect(() => {
    const search = spatialStateToSearch(state);
    const timer = window.setTimeout(() => {
      window.history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
    }, 160);
    return () => window.clearTimeout(timer);
  }, [state]);

  useEffect(() => {
    const onPopState = () => dispatch({ type: "hydrate", state: parseSpatialUrl(window.location.search) });
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const value = useMemo(() => ({
    state,
    dispatch,
    shareUrl: `${window.location.origin}${window.location.pathname}${spatialStateToSearch(state)}`
  }), [state]);
  return <SpatialContext.Provider value={value}>{children}</SpatialContext.Provider>;
}

export function useSpatialContext(): SpatialContextValue {
  const context = useContext(SpatialContext);
  if (!context) throw new Error("useSpatialContext must be used inside SpatialProvider");
  return context;
}
