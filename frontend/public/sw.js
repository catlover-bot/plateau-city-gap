/* global self, caches, URL, Response, fetch */
const SHELL_CACHE = "citygap-shell-v5";
const FIELD_CACHE = "citygap-selected-field-v1";
const PACK_CACHE = "citygap-selected-spatial-pack-v1";
const shellUrls = [
  "./",
  "./data/mesh_metrics.geojson",
  "./data/summary.json",
  "./data/plateau_metadata.json",
  "./data/evidence.json",
  "./data/spatial-packs/maizuru-533513314-plateau-2025-v1/manifest.json",
  "./data/spatial-packs/maizuru-533513314-plateau-2025-v1/sections.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(shellUrls)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key.startsWith("citygap-") && ![SHELL_CACHE, FIELD_CACHE, PACK_CACHE].includes(key))
        .map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  const message = event.data;
  if (message?.type === "CACHE_SELECTED_SPATIAL_PACK") {
    const packPrefix = new URL(`./data/spatial-packs/${message.packId}/`, self.registration.scope).href;
    const urls = Array.isArray(message.artifactUrls)
      ? message.artifactUrls.map((value) => new URL(value, self.registration.scope).href)
      : [];
    if (!urls.length || urls.some((url) => !url.startsWith(packPrefix))) return;
    event.waitUntil(caches.open(PACK_CACHE).then((cache) => cache.addAll(urls)));
    return;
  }
  if (!message || message.type !== "CACHE_SELECTED_FIELD_PACKAGE") return;
  const virtualUrl = new URL(`./offline-field/${message.packageId}.json`, self.registration.scope);
  const response = new Response(JSON.stringify(message.payload), {
    headers: { "Content-Type": "application/json", "X-CITYGAP-Scope": "single-selected-site" }
  });
  event.waitUntil(caches.open(FIELD_CACHE).then((cache) => cache.put(virtualUrl, response)));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => response)
      .catch(async () => {
        const selected = await caches.open(FIELD_CACHE).then((cache) => cache.match(event.request));
        const selectedPack = await caches.open(PACK_CACHE).then((cache) => cache.match(event.request));
        return selected || selectedPack || caches.match(event.request) || Response.error();
      })
  );
});
