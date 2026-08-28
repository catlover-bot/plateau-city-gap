import { lazy, Suspense } from "react";
import { SpatialProvider } from "./app/context/SpatialContext";

const ProductApp = lazy(async () => ({
  default: (await import("./app/ProductApp")).ProductApp
}));
const MunicipalServiceApp = lazy(async () => ({
  default: (await import("./service/ServiceApp")).ServiceApp
}));

export default function App() {
  if (import.meta.env.VITE_CITYGAP_SURFACE === "municipal") {
    return <Suspense fallback={<main className="service-state">CITY GAPを読み込んでいます</main>}><MunicipalServiceApp /></Suspense>;
  }
  return <SpatialProvider><Suspense fallback={null}><ProductApp /></Suspense></SpatialProvider>;
}
