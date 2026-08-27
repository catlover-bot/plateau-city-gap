/* global self, caches, URL, Response, fetch */
const SHELL_CACHE = "citygap-shell-v3";
const FIELD_CACHE = "citygap-selected-field-v1";
const shellUrls = ["./", "./data/urban_futures_resilience.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(shellUrls)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key.startsWith("citygap-") && ![SHELL_CACHE, FIELD_CACHE].includes(key))
        .map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  const message = event.data;
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
        return selected || caches.match(event.request) || Response.error();
      })
  );
});
