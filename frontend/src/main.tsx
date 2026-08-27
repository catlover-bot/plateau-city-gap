import React from "react";
import ReactDOM from "react-dom/client";
import "maplibre-gl/dist/maplibre-gl.css";
import App from "./App";
import "./styles.css";
import "./design-system/tokens.css";
import "./app/product-shell.css";
import "./map/map.css";
import "./features/inspector/inspector.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`, {
      scope: import.meta.env.BASE_URL
    });
  });
}
