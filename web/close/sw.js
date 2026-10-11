/* Omni-One · Daily Close PWA · Service Worker */
/* File: web/close/sw.js */
/* Strategy: cache-first offline shell, versioned CLOSE_V1. */
/* Caches: index.html + app.js + manifest.webmanifest + icon.svg */
/* No CDN, no network dependency. $0. cite: [sw.js:CLOSE_V1] */
"use strict";

var CACHE_NAME = "CLOSE_V1";
var SHELL = [
  "./",
  "./index.html",
  "./app.js",
  "./manifest.webmanifest",
  "./icon.svg",
];

self.addEventListener("install", function (event) {
  // Pre-cache shell so file opens offline after first visit.
  // cite: [sw.js:CLOSE_V1]
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL).catch(function () {
        // Best-effort: file:// or partial hosts may fail; ignore.
        return undefined;
      });
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  // Drop old CLOSE_* caches (versioned).
  // cite: [sw.js:CLOSE_V1]
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.map(function (k) {
          if (k !== CACHE_NAME && k.indexOf("CLOSE_") === 0) {
            return caches.delete(k);
          }
          return undefined;
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  // Only handle same-origin GET (API POSTs pass through).
  // cite: [sw.js:cache-first]
  if (req.method !== "GET") {
    return;
  }
  var url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) {
    return; // never cache cross-origin (offline rule: no CDN)
  }
  // API calls: network-first with cache fallback? Keep simple: pass through,
  // but fall back to cache on failure for GET shell assets.
  if (url.pathname.indexOf("/api/") >= 0) {
    return; // let browser handle API (app.js shows cache fallback UI)
  }
  event.respondWith(
    caches.match(req, { ignoreSearch: false }).then(function (hit) {
      if (hit) {
        return hit; // cache-first [sw.js:cache-first]
      }
      return fetch(req).then(function (res) {
        // Cache good shell responses for next offline visit.
        try {
          if (res && res.ok) {
            var copy = res.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(req, copy).catch(function () {});
            });
          }
        } catch (e) {
          /* ignore */
        }
        return res;
      }).catch(function () {
        // Offline fallback: serve cached index.html for navigations.
        if (req.mode === "navigate") {
          return caches.match("./index.html").then(function (idx) {
            return idx || Response.error();
          });
        }
        throw new Error("offline [sw.js:CLOSE_V1]");
      });
    })
  );
});
