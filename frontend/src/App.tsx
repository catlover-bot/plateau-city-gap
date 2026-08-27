import { ProductApp } from "./app/ProductApp";
import { SpatialProvider } from "./app/context/SpatialContext";

export default function App() {
  return <SpatialProvider><ProductApp /></SpatialProvider>;
}
