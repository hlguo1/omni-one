/* ===================================================================== */
/* Omni-One · WORKSTREAM B · web PWA Close dashboard                   */
/* File: web/close/app.js                                              */
/*                                                                     */
/* Dependency-free PWA logic (no npm, no framework, no CDN).            */
/* Vanilla JS only. Works from file:// (shell) + http(s) (API).        */
/*                                                                     */
/* API contract (same-origin by default):                               */
/*   POST /api/v1/seller/close      {demo, seed, shop, folder, locale} */
/*   GET  /api/v1/seller/close.csv  ?demo=1&seed=42&shop=...            */
/*                                                                     */
/* Features:                                                           */
/*   - api client (base URL editable, localStorage close_api_base)      */
/*   - state store (single `state` object, idempotent re-render)        */
/*   - renderers per tab (Today/Reorder+PO/Replies/Leaks/Listings/Files)*/
/*   - CSV download (Blob + fallback), copy-to-clipboard + fallback    */
/*   - demo seed control, shop name input                               */
/*   - filters (urgency/severity/priority/channel), search, sort        */
/*   - localStorage cache of last close (24h, key close_last)           */
/*   - graceful offline/error states, file:line citations everywhere    */
/*   - keyboard shortcuts: 1..6 tabs, d demo, c csv, p print, / search  */
/*                                                                     */
/* Citations: every rendered number carries file:line, e.g.            */
/*   [shopify_orders.csv:5] [inventory.csv:2] [reviews.csv:3]           */
/*   [instagram_dm.txt:1] [seller_close.py:build_daily_close]           */
/* ===================================================================== */
"use strict";

/* --------------------------------------------------------------------- */
/* 0. Small helpers                                                      */
/* --------------------------------------------------------------------- */

/**
 * Query one element.
 * @param {string} sel CSS selector.
 * @param {ParentNode} [root] Optional root.
 * @returns {Element|null}
 * cite: [app.js:helpers]
 */
function $(sel, root) {
  try {
    return (root || document).querySelector(sel);
  } catch (e) {
    return null;
  }
}

/**
 * Query all elements as array.
 * @param {string} sel CSS selector.
 * @param {ParentNode} [root] Optional root.
 * @returns {Element[]}
 * cite: [app.js:helpers]
 */
function $all(sel, root) {
  try {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  } catch (e) {
    return [];
  }
}

/**
 * Get element by id (null-safe).
 * @param {string} id Element id.
 * @returns {HTMLElement|null}
 * cite: [app.js:helpers]
 */
function byId(id) {
  return document.getElementById(id);
}

/**
 * Escape HTML to avoid injection from server data.
 * @param {unknown} s Value to escape.
 * @returns {string}
 * cite: [app.js:escape]
 */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Format USD, tolerant of nulls.
 * @param {unknown} n Number-ish.
 * @returns {string}
 * cite: [app.js:fmt]
 */
function fmtUSD(n) {
  var v = Number(n);
  if (!isFinite(v)) {
    return "—";
  }
  try {
    return "$" + v.toFixed(2);
  } catch (e) {
    return "$" + String(v);
  }
}

/**
 * Format generic number.
 * @param {unknown} n Number-ish.
 * @param {number} digits Decimals.
 * @returns {string}
 * cite: [app.js:fmt]
 */
function fmtNum(n, digits) {
  var v = Number(n);
  if (!isFinite(v)) {
    return "—";
  }
  return v.toFixed(digits == null ? 1 : digits);
}

/**
 * Clamp text length with ellipsis.
 * @param {unknown} s Text.
 * @param {number} n Max chars.
 * @returns {string}
 * cite: [app.js:fmt]
 */
function trunc(s, n) {
  var t = String(s == null ? "" : s);
  if (t.length <= n) {
    return t;
  }
  return t.slice(0, Math.max(0, n - 1)) + "…";
}

/**
 * Debounce helper for search inputs.
 * @param {Function} fn Function.
 * @param {number} ms Wait.
 * @returns {Function}
 * cite: [app.js:helpers]
 */
function debounce(fn, ms) {
  var t = null;
  return function () {
    var args = arguments;
    var ctx = this;
    if (t) {
      clearTimeout(t);
    }
    t = setTimeout(function () {
      t = null;
      fn.apply(ctx, args);
    }, ms || 160);
  };
}

/**
 * Safe JSON stringify (never throws).
 * @param {unknown} v Value.
 * @returns {string}
 * cite: [app.js:helpers]
 */
function safeStringify(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch (e) {
    try {
      return String(v);
    } catch (e2) {
      return "{}";
    }
  }
}

/**
 * Check online status (tolerant).
 * @returns {boolean}
 * cite: [app.js:offline]
 */
function isOnline() {
  try {
    return navigator.onLine !== false;
  } catch (e) {
    return true;
  }
}

/* --------------------------------------------------------------------- */
/* 1. Constants + storage keys                                           */
/* --------------------------------------------------------------------- */

/** LocalStorage keys (all under `close_*`). cite: [app.js:storage] */
var LS = {
  api: "close_api_base",
  shop: "close_shop",
  seed: "close_seed",
  last: "close_last",
  theme: "close_theme",
  tab: "close_tab",
};

/** Cache TTL: 24h. cite: [app.js:cache] */
var CACHE_TTL_MS = 24 * 60 * 60 * 1000;

/** API paths. cite: [app.js:api-paths] */
var API_CLOSE = "/api/v1/seller/close";
var API_CLOSE_CSV = "/api/v1/seller/close.csv";

/** Tab ids in order (keyboard 1..6). cite: [app.js:tabs] */
var TAB_ORDER = ["today", "reorder", "replies", "leaks", "listings", "files"];

/* --------------------------------------------------------------------- */
/* 2. API client (base URL editable, localStorage)                       */
/*                                                                     */
/* Resolution order:                                                   */
/*   1) ?api= query param (session override, also persisted)           */
/*   2) #api= hash param (some static hosts strip query)              */
/*   3) localStorage close_api_base                                    */
/*   4) #apiInput value (settings box)                                 */
/*   5) location.origin (same-origin) — unless file:// (null origin)   */
/*                                                                     */
/* file:// shells cannot call APIs; demo + cache still work.           */
/* cite: [app.js:api-client]                                           */
/* --------------------------------------------------------------------- */

/**
 * Read ?api= / #api= override.
 * @returns {string}
 * cite: [app.js:api-client]
 */
function apiOverrideFromURL() {
  try {
    var q = new URLSearchParams(window.location.search).get("api");
    if (q && q.trim()) {
      return q.trim().replace(/\/+$/, "");
    }
  } catch (e) {
    /* ignore [app.js:api-client] */
  }
  try {
    var h = String(window.location.hash || "");
    var m = h.match(/api=([^&]+)/);
    if (m && m[1]) {
      return decodeURIComponent(m[1]).trim().replace(/\/+$/, "");
    }
  } catch (e2) {
    /* ignore */
  }
  return "";
}

/**
 * Resolve API base URL.
 * @returns {string} "" means same-origin (use relative fetch).
 * cite: [app.js:api-client]
 */
function getApiBase() {
  var ov = apiOverrideFromURL();
  if (ov) {
    try {
      localStorage.setItem(LS.api, ov);
    } catch (e) {
      /* private mode */
    }
    return ov;
  }
  try {
    var box = byId("apiInput");
    if (box && box.value && box.value.trim()) {
      return box.value.trim().replace(/\/+$/, "");
    }
  } catch (e) {
    /* ignore */
  }
  try {
    var saved = localStorage.getItem(LS.api);
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, "");
    }
  } catch (e2) {
    /* ignore */
  }
  try {
    if (window.location.protocol === "file:") {
      return "";
    }
    if (window.location.origin && window.location.origin !== "null") {
      return window.location.origin.replace(/\/+$/, "");
    }
  } catch (e3) {
    /* ignore */
  }
  return "";
}

/**
 * Persist API base to localStorage + input box.
 * @param {string} base Base URL ("" = same-origin).
 * cite: [app.js:api-client]
 */
function setApiBase(base) {
  var b = String(base || "").trim().replace(/\/+$/, "");
  try {
    if (b) {
      localStorage.setItem(LS.api, b);
    } else {
      localStorage.removeItem(LS.api);
    }
  } catch (e) {
    /* ignore */
  }
  try {
    var box = byId("apiInput");
    if (box && document.activeElement !== box) {
      box.value = b;
    }
  } catch (e2) {
    /* ignore */
  }
  return b;
}

/**
 * Build full API URL from base + path + query.
 * @param {string} path e.g. /api/v1/seller/close
 * @param {Object} [query] Query params.
 * @returns {string}
 * cite: [app.js:api-client]
 */
function apiURL(path, query) {
  var base = getApiBase();
  var qs = "";
  try {
    if (query) {
      var parts = [];
      for (var k in query) {
        if (Object.prototype.hasOwnProperty.call(query, k)) {
          var v = query[k];
          if (v !== undefined && v !== null && v !== "") {
            parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
          }
        }
      }
      if (parts.length) {
        qs = "?" + parts.join("&");
      }
    }
  } catch (e) {
    qs = "";
  }
  // Same-origin: relative URL keeps file:// safe (fetch will fail gracefully).
  if (!base) {
    return path + qs;
  }
  return base + path + qs;
}

/**
 * POST JSON to API with timeout + clean errors.
 * @param {string} path API path.
 * @param {Object} payload JSON body.
 * @param {number} [timeoutMs] Timeout (default 30000).
 * @returns {Promise<Object>}
 * cite: [app.js:api-client]
 */
function apiPostJSON(path, payload, timeoutMs) {
  var url = apiURL(path);
  var ms = timeoutMs || 30000;
  return new Promise(function (resolve, reject) {
    var done = false;
    var timer = setTimeout(function () {
      if (!done) {
        done = true;
        reject(new Error("timeout after " + ms + "ms POST " + path + " [app.js:api-client]"));
      }
    }, ms);
    var opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: safeStringify(payload),
    };
    fetch(url, opts).then(function (r) {
      if (done) {
        return;
      }
      done = true;
      clearTimeout(timer);
      if (!r.ok) {
        r.text().then(function (t) {
          reject(new Error("HTTP " + r.status + " POST " + path + ": " + trunc(t, 220)));
        }).catch(function () {
          reject(new Error("HTTP " + r.status + " POST " + path));
        });
        return;
      }
      r.json().then(function (j) {
        resolve(j);
      }).catch(function (e) {
        reject(new Error("bad JSON from POST " + path + ": " + e));
      });
    }).catch(function (e) {
      if (done) {
        return;
      }
      done = true;
      clearTimeout(timer);
      reject(e);
    });
  });
}

/**
 * GET CSV text from API.
 * @param {Object} params Query {demo, seed, shop}.
 * @returns {Promise<string>}
 * cite: [app.js:api-client]
 */
function apiGetCSV(params) {
  var url = apiURL(API_CLOSE_CSV, params);
  return fetch(url, { method: "GET" }).then(function (r) {
    if (!r.ok) {
      throw new Error("HTTP " + r.status + " GET " + API_CLOSE_CSV);
    }
    return r.text();
  });
}

/* --------------------------------------------------------------------- */
/* 3. State store (single object, idempotent re-render)                  */
/*                                                                     */
/* state = {                                                           */
/*   close: Object|null, source: live|cache|demo|empty,                 */
/*   loading: bool, error: string,                                     */
/*   tab: today|reorder|replies|leaks|listings|files,                  */
/*   filters: {qToday,qReorder,urgency,sortReorder,qReplies,priority,   */
/*             channel,qLeaks,leak,qListings},                          */
/*   files: [{name,size,ts}],                                          */
/*   lastFetchAt: ms                                                   */
/* }                                                                   */
/* cite: [app.js:store]                                                */
/* --------------------------------------------------------------------- */

var state = {
  close: null,
  source: "empty",
  loading: false,
  error: "",
  tab: "today",
  filters: {
    qToday: "",
    qReorder: "",
    urgency: "all",
    sortReorder: "days_left",
    qReplies: "",
    priority: "all",
    channel: "all",
    qLeaks: "",
    leak: "all",
    qListings: "",
  },
  files: [],
  lastFetchAt: 0,
};

/**
 * Get current shop name (input → localStorage → default).
 * @returns {string}
 * cite: [app.js:shop]
 */
function getShop() {
  try {
    var box = byId("shopInput");
    if (box && box.value && box.value.trim()) {
      return box.value.trim().slice(0, 60);
    }
    var saved = localStorage.getItem(LS.shop);
    if (saved && saved.trim()) {
      return saved.trim().slice(0, 60);
    }
  } catch (e) {
    /* ignore */
  }
  return "our shop";
}

/**
 * Persist shop name.
 * @param {string} s Shop name.
 * cite: [app.js:shop]
 */
function setShop(s) {
  var v = String(s || "").trim().slice(0, 60) || "our shop";
  try {
    localStorage.setItem(LS.shop, v);
  } catch (e) {
    /* ignore */
  }
  try {
    var box = byId("shopInput");
    if (box && document.activeElement !== box) {
      box.value = v;
    }
  } catch (e2) {
    /* ignore */
  }
  return v;
}

/**
 * Get draft locale (select → localStorage → en).
 * Numbers never change with locale — drafts only.
 * @returns {string}
 * cite: [app.js:locale]
 */
function getLocale() {
  var ok = { en: 1, es: 1, zh: 1, fr: 1, de: 1 };
  try {
    var sel = byId("localeInput");
    if (sel && sel.value && ok[sel.value]) {
      return sel.value;
    }
    var saved = localStorage.getItem(LS.locale || "close_locale");
    if (saved && ok[saved]) {
      return saved;
    }
  } catch (e) {
    /* ignore */
  }
  return "en";
}

/**
 * Persist draft locale.
 * @param {string} l Locale.
 * cite: [app.js:locale]
 */
function setLocale(l) {
  var ok = { en: 1, es: 1, zh: 1, fr: 1, de: 1 };
  var v = ok[l] ? l : "en";
  try {
    localStorage.setItem(LS.locale || "close_locale", v);
  } catch (e) {
    /* ignore */
  }
  try {
    var sel = byId("localeInput");
    if (sel && document.activeElement !== sel) {
      sel.value = v;
    }
  } catch (e2) {
    /* ignore */
  }
  return v;
}

/**
 * Get demo seed (input → localStorage → 42).
 * @returns {number}
 * cite: [app.js:seed]
 */
function getSeed() {
  try {
    var box = byId("seedInput");
    if (box && box.value !== "" && box.value != null) {
      var n = parseInt(String(box.value), 10);
      if (isFinite(n) && n >= 0) {
        return n;
      }
    }
    var saved = localStorage.getItem(LS.seed);
    if (saved != null && saved !== "") {
      var n2 = parseInt(String(saved), 10);
      if (isFinite(n2) && n2 >= 0) {
        return n2;
      }
    }
  } catch (e) {
    /* ignore */
  }
  return 42;
}

/**
 * Persist demo seed.
 * @param {number} n Seed.
 * cite: [app.js:seed]
 */
function setSeed(n) {
  var v = parseInt(String(n), 10);
  if (!isFinite(v) || v < 0) {
    v = 42;
  }
  try {
    localStorage.setItem(LS.seed, String(v));
  } catch (e) {
    /* ignore */
  }
  return v;
}

/* --------------------------------------------------------------------- */
/* 4. Cache: localStorage last close (24h)                               */
/*                                                                     */
/* Key: close_last → {savedAt, shop, seed, close}.                      */
/* Stale after 24h. Corrupt entries are dropped silently.               */
/* cite: [app.js:cache]                                                */
/* --------------------------------------------------------------------- */

/**
 * Save close to cache.
 * @param {Object} close Close bundle.
 * @param {string} shop Shop.
 * @param {number} seed Seed.
 * cite: [app.js:cache]
 */
function saveCache(close, shop, seed) {
  try {
    var payload = {
      savedAt: Date.now(),
      shop: shop || getShop(),
      seed: seed == null ? getSeed() : seed,
      close: close,
    };
    localStorage.setItem(LS.last, JSON.stringify(payload));
  } catch (e) {
    /* quota / private mode — ignore */
  }
  updateCacheLine();
}

/**
 * Load close from cache (null if missing/stale/corrupt).
 * @returns {{savedAt:number,shop:string,seed:number,close:Object}|null}
 * cite: [app.js:cache]
 */
function loadCache() {
  try {
    var raw = localStorage.getItem(LS.last);
    if (!raw) {
      return null;
    }
    var p = JSON.parse(raw);
    if (!p || !p.close || !p.savedAt) {
      return null;
    }
    if (Date.now() - Number(p.savedAt) > CACHE_TTL_MS) {
      return null;
    }
    return p;
  } catch (e) {
    return null;
  }
}

/**
 * Clear cached close.
 * cite: [app.js:cache]
 */
function clearCache() {
  try {
    localStorage.removeItem(LS.last);
  } catch (e) {
    /* ignore */
  }
  updateCacheLine();
  toast("Cache cleared. [app.js:cache]");
}

/**
 * Update cache status line.
 * cite: [app.js:cache]
 */
function updateCacheLine() {
  var el = byId("cacheLine");
  if (!el) {
    return;
  }
  var c = loadCache();
  if (!c) {
    el.textContent = "cache: empty (24h TTL) [app.js:cache]";
    return;
  }
  try {
    var ageMin = Math.max(0, Math.round((Date.now() - c.savedAt) / 60000));
    el.textContent = "cache: saved " + ageMin + "m ago · shop " + (c.shop || "?") + " [app.js:cache]";
  } catch (e) {
    el.textContent = "cache: saved [app.js:cache]";
  }
}

/* --------------------------------------------------------------------- */
/* 5. Status / banners / toast (graceful offline/error states)           */
/* cite: [app.js:status]                                               */
/* --------------------------------------------------------------------- */

/**
 * Set status line.
 * @param {string} msg Message.
 * @param {string} kind "" | "ok" | "error".
 * cite: [app.js:status]
 */
function setStatus(msg, kind) {
  var el = byId("loadStatus");
  if (!el) {
    return;
  }
  el.textContent = String(msg || "");
  el.classList.remove("ok", "error");
  if (kind) {
    el.classList.add(kind);
  }
}

/**
 * Show error banner.
 * @param {string} msg Error text.
 * cite: [app.js:status]
 */
function showError(msg) {
  state.error = String(msg || "unknown error");
  var b = byId("errorBanner");
  var t = byId("errorText");
  if (t) {
    t.textContent = state.error + " ";
  }
  if (b) {
    b.classList.remove("hidden");
  }
  setStatus("Error: " + state.error + " [app.js:api-client]", "error");
}

/**
 * Hide error banner.
 * cite: [app.js:status]
 */
function hideError() {
  state.error = "";
  var b = byId("errorBanner");
  if (b) {
    b.classList.add("hidden");
  }
}

/**
 * Update offline banner from navigator.onLine.
 * cite: [app.js:offline]
 */
function updateOfflineBanner() {
  var b = byId("offlineBanner");
  if (!b) {
    return;
  }
  if (isOnline()) {
    b.classList.add("hidden");
  } else {
    b.classList.remove("hidden");
  }
}

/**
 * Toast (auto-hide, offline-safe).
 * @param {string} msg Message.
 * cite: [app.js:toast]
 */
function toast(msg) {
  var el = byId("toast");
  if (!el) {
    return;
  }
  el.textContent = String(msg || "");
  el.classList.remove("hidden");
  try {
    if (toast._t) {
      clearTimeout(toast._t);
    }
    toast._t = setTimeout(function () {
      el.classList.add("hidden");
    }, 2600);
  } catch (e) {
    /* ignore */
  }
}

/**
 * Set loading state (spinner in status + disable buttons).
 * @param {boolean} on Loading?
 * @param {string} label What is loading.
 * cite: [app.js:status]
 */
function setLoading(on, label) {
  state.loading = !!on;
  var ids = ["btnDemo", "btnFetch", "btnCSV", "btnDemoTop", "btnCSVTop", "btnTodayDemo", "btnTodayCSV"];
  for (var i = 0; i < ids.length; i++) {
    var b = byId(ids[i]);
    if (b) {
      try {
        b.disabled = !!on;
      } catch (e) {
        /* ignore */
      }
    }
  }
  if (on) {
    setStatus("⏳ " + (label || "Loading…") + " [app.js:api-client]");
    var st = byId("loadStatus");
    if (st) {
      st.innerHTML = "";
      var sp = document.createElement("span");
      sp.className = "spinner";
      sp.setAttribute("aria-hidden", "true");
      st.appendChild(sp);
      st.appendChild(document.createTextNode(" " + (label || "Loading…") + " [app.js:api-client]"));
    }
  }
}

/* --------------------------------------------------------------------- */
/* 6. Fetchers: demo / live / CSV                                       */
/*                                                                     */
/*   loadDemo()      → POST demo:true (seed+shop), render + cache       */
/*   fetchClose()    → POST folder-or-demo, render + cache              */
/*   downloadCSV()   → GET close.csv → Blob download (fallback window)  */
/*                                                                     */
/* All graceful: file://, offline, timeout → banner + cache fallback.  */
/* cite: [app.js:fetchers]                                             */
/* --------------------------------------------------------------------- */

/**
 * POST a close (demo or folder) and render it.
 * @param {Object} opts {demo:boolean, folder:string, seed:number, shop:string}
 * @returns {Promise<Object|null>}
 * cite: [app.js:fetchers]
 */
function postClose(opts) {
  opts = opts || {};
  var shop = (opts.shop != null ? String(opts.shop) : getShop()).slice(0, 60) || "our shop";
  var seed = opts.seed != null ? setSeed(opts.seed) : getSeed();
  var payload = { demo: opts.demo !== false, seed: seed, shop: shop };
  if (opts.folder) {
    payload.folder = String(opts.folder);
    payload.demo = false;
  }
  hideError();
  updateOfflineBanner();
  setLoading(true, "Closing " + shop + " (POST " + API_CLOSE + ")…");
  return apiPostJSON(API_CLOSE, payload, 30000).then(function (close) {
    setLoading(false);
    state.close = close || null;
    state.source = payload.demo ? "demo" : "live";
    state.lastFetchAt = Date.now();
    try {
      saveCache(state.close, shop, seed);
    } catch (e) {
      /* ignore */
    }
    renderClose(state.close);
    setStatus(
      "Closed " + shop + " · " + ((close && close.date) || "today") +
      " · source=" + state.source + " · POST " + API_CLOSE + " [app.js:fetchers]",
      "ok"
    );
    hideError();
    return state.close;
  }).catch(function (e) {
    setLoading(false);
    var msg = (e && e.message) ? e.message : String(e);
    // Graceful fallback: stale cache (even >24h) is better than blank.
    var stale = null;
    try {
      var raw = localStorage.getItem(LS.last);
      if (raw) {
        stale = JSON.parse(raw);
      }
    } catch (e2) {
      stale = null;
    }
    if (stale && stale.close) {
      state.close = stale.close;
      state.source = "cache";
      renderClose(state.close);
      showError(msg + " — showing cached close instead. [app.js:cache]");
      updateCacheLine();
      return state.close;
    }
    showError(msg + " — is the server running at " + (getApiBase() || location.origin) + "? [app.js:api-client]");
    updateOfflineBanner();
    return null;
  });
}

/**
 * Load demo close (1 click). Required by smoke test.
 * Reads seed + shop inputs, POSTs {demo:true}.
 * @returns {Promise<Object|null>}
 * cite: [app.js:loadDemo]
 */
async function loadDemo() {
  var shop = setShop(getShop());
  var seed = setSeed(getSeed());
  var locale = setLocale(getLocale());
  setApiBase(getApiBase());
  return postClose({ demo: true, seed: seed, shop: shop, locale: locale });
}

/**
 * Fetch close for folder-or-demo (Fetch button).
 * If a folder path was hinted, tries it; else demo.
 * @returns {Promise<Object|null>}
 * cite: [app.js:fetchers]
 */
async function fetchClose() {
  var shop = setShop(getShop());
  var seed = setSeed(getSeed());
  var locale = setLocale(getLocale());
  // Folder mode only works when the API host HAS that path.
  // We keep a hinted folder in state (from drop) and try it first.
  var hinted = "";
  try {
    hinted = sessionStorage.getItem("close_folder_hint") || "";
  } catch (e) {
    hinted = "";
  }
  if (hinted) {
    var r = await postClose({ demo: false, folder: hinted, seed: seed, shop: shop, locale: locale });
    if (r) {
      return r;
    }
    // fall through to demo
  }
  return postClose({ demo: true, seed: seed, shop: shop, locale: locale });
}

/**
 * Explain folder mode (browsers cannot POST a local path directly).
 * Shows hint + curl + CLI, logs dropped file names.
 * Required by smoke test.
 * @param {FileList|File[]|string} [filesOrMsg] Dropped files or message.
 * cite: [app.js:loadFolderHint]
 */
function loadFolderHint(filesOrMsg) {
  var names = [];
  try {
    if (filesOrMsg && typeof filesOrMsg.length === "number" && typeof filesOrMsg !== "string") {
      for (var i = 0; i < filesOrMsg.length; i++) {
        var f = filesOrMsg[i];
        if (f && f.name) {
          names.push(f.name + (f.size != null ? " (" + f.size + "B)" : ""));
          state.files.unshift({ name: f.name, size: f.size || 0, ts: Date.now() });
        }
      }
      state.files = state.files.slice(0, 20);
    } else if (typeof filesOrMsg === "string" && filesOrMsg) {
      names.push(filesOrMsg);
    }
  } catch (e) {
    /* ignore */
  }
  renderFileList();
  var shop = getShop();
  var hint =
    "📁 Folder mode: browsers can't send a server `folder` path, so run this where the files live:\n\n" +
    "  curl -X POST " + (getApiBase() || location.origin) + API_CLOSE + " \\\n" +
    "    -H 'Content-Type: application/json' \\\n" +
    "    -d '{\"folder\": \"/tmp/my_shop\", \"shop\": \"" + shop.replace(/"/g, "") + "\"}'\n\n" +
    "Or CLI: omni-one close --folder /tmp/my_shop --out ./close_$(date +%F)\n\n" +
    (names.length ? "You dropped: " + names.slice(0, 8).join(", ") + "\n(cannot upload server paths — names logged only)\n\n" : "") +
    "Quickest now: press Demo close (POST demo:true). Citations: [app.js:loadFolderHint]";
  var el = byId("folderHint");
  if (el) {
    el.textContent = hint.split("\n")[0] + " — see Files tab for curl. [app.js:loadFolderHint]";
  }
  toast("Folder hint shown — see Files tab. [app.js:loadFolderHint]");
  // Also surface in Files tab curl hint area (keep original + dropped names).
  try {
    var curl = byId("curlHint");
    if (curl && names.length) {
      curl.textContent += "\n# dropped (browser-side only, not uploaded):\n# - " + names.slice(0, 10).join("\n# - ");
    }
  } catch (e) {
    /* ignore */
  }
  return hint;
}

/**
 * Download accountant CSV (GET close.csv → Blob).
 * Required by smoke test. Falls back to navigation when Blob fails.
 * @returns {Promise<void>}
 * cite: [app.js:downloadCSV]
 */
function downloadCSV() {
  var shop = getShop();
  var seed = getSeed();
  setStatus("Downloading close.csv (GET " + API_CLOSE_CSV + ")… [app.js:downloadCSV]");
  return apiGetCSV({ demo: true, seed: seed, shop: shop }).then(function (text) {
    saveTextFile("close.csv", text, "text/csv");
    setStatus("Downloaded close.csv (" + (text ? text.length : 0) + " chars) [app.js:downloadCSV]", "ok");
    toast("CSV downloaded. [app.js:downloadCSV]");
  }).catch(function (e) {
    // Fallback 1: build CSV client-side from cached close.
    try {
      if (state.close) {
        var built = closeToCSVText(state.close);
        saveTextFile("close.csv", built, "text/csv");
        setStatus("Built close.csv locally from cache [app.js:downloadCSV]", "ok");
        return;
      }
    } catch (e2) {
      /* ignore */
    }
    // Fallback 2: navigate (lets browser show server error).
    try {
      window.location.href = apiURL(API_CLOSE_CSV, { demo: true, seed: seed, shop: shop });
    } catch (e3) {
      /* ignore */
    }
    showError("CSV failed: " + ((e && e.message) || e) + " [app.js:downloadCSV]");
  });
}

/**
 * Build minimal close.csv client-side (fallback when API unreachable).
 * Mirrors seller_close.close_to_csv columns.
 * @param {Object} close Close bundle.
 * @returns {string}
 * cite: [app.js:downloadCSV]
 */
function closeToCSVText(close) {
  var rows = [];
  function q(v) {
    var s = String(v == null ? "" : v);
    if (/[",\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }
  rows.push(["DAILY CLOSE", (close && close.date) || "", (close && close.headline) || ""].map(q).join(","));
  rows.push("");
  rows.push(["metric", "value"].map(q).join(","));
  var kpis = (close && close.kpis) || {};
  for (var k in kpis) {
    if (Object.prototype.hasOwnProperty.call(kpis, k)) {
      var v = kpis[k];
      if (v && typeof v === "object") {
        v = safeStringify(v);
      }
      rows.push([k, v].map(q).join(","));
    }
  }
  rows.push("");
  rows.push(["do_today_n", "do_today"].map(q).join(","));
  var todo = (close && close.do_today) || [];
  for (var i = 0; i < todo.length; i++) {
    rows.push([(i + 1), todo[i]].map(q).join(","));
  }
  rows.push("");
  rows.push(["product", "on_hand", "sold_7d", "days_left", "reorder_qty_14d", "supplier", "urgency", "citation"].map(q).join(","));
  var rs = (close && close.reorder_sheet) || [];
  for (var j = 0; j < rs.length; j++) {
    var r = rs[j] || {};
    rows.push([r.product, r.on_hand, r.sold_7d, r.days_left, r.reorder_qty, r.supplier, r.urgency, r.citation].map(q).join(","));
  }
  rows.push("");
  rows.push(["leak", "amount_usd", "note", "evidence"].map(q).join(","));
  var lk = (close && close.money_leaks) || [];
  for (var m = 0; m < lk.length; m++) {
    var l = lk[m] || {};
    rows.push([l.leak, l.amount_usd, trunc(l.note, 160), l.evidence].map(q).join(","));
  }
  return rows.join("\n") + "\n";
}

/**
 * Save text file (Blob + a[download]; fallback clipboard/new-tab).
 * @param {string} filename Name.
 * @param {string} text Content.
 * @param {string} mime MIME.
 * cite: [app.js:download]
 */
function saveTextFile(filename, text, mime) {
  try {
    var blob = new Blob([String(text)], { type: mime || "text/plain" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      try {
        document.body.removeChild(a);
      } catch (e) {
        /* ignore */
      }
      try {
        URL.revokeObjectURL(url);
      } catch (e2) {
        /* ignore */
      }
    }, 800);
    return true;
  } catch (e) {
    // Fallback: open in new tab so user can Save As.
    try {
      var w = window.open("", "_blank");
      if (w) {
        w.document.write("<pre>" + esc(text).slice(0, 200000) + "</pre>");
        w.document.title = filename;
      }
    } catch (e2) {
      /* ignore */
    }
    return false;
  }
}

/* --------------------------------------------------------------------- */
/* 7. Copy-to-clipboard with fallback                                    */
/*                                                                     */
/* copyText() tries navigator.clipboard, then textarea+execCommand,     */
/* then prompt(). Always resolves true/false, never rejects.            */
/* Required by smoke test. cite: [app.js:copy]                          */
/* --------------------------------------------------------------------- */

/**
 * Copy text to clipboard (async, with fallbacks).
 * @param {string} text Text to copy.
 * @returns {Promise<boolean>} true if copied.
 * cite: [app.js:copy]
 */
async function copyText(text) {
  var s = String(text == null ? "" : text);
  if (!s) {
    toast("Nothing to copy. [app.js:copy]");
    return false;
  }
  // 1) Modern async clipboard (needs https/localhost + permission).
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(s);
      toast("Copied ✓ [app.js:copy]");
      return true;
    }
  } catch (e) {
    /* fall through [app.js:copy] */
  }
  // 2) Legacy execCommand fallback (works on file:// + older browsers).
  try {
    var ta = document.createElement("textarea");
    ta.value = s;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      ta.setSelectionRange(0, ta.value.length);
    } catch (e) {
      /* ignore */
    }
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e2) {
      ok = false;
    }
    try {
      document.body.removeChild(ta);
    } catch (e3) {
      /* ignore */
    }
    if (ok) {
      toast("Copied ✓ [app.js:copy]");
      return true;
    }
  } catch (e) {
    /* fall through */
  }
  // 3) Last resort: prompt() so user can Ctrl+C manually.
  try {
    window.prompt("Copy (Ctrl+C, Enter): [app.js:copy]", s.slice(0, 4000));
    return false;
  } catch (e) {
    toast("Copy failed — select text manually. [app.js:copy]");
    return false;
  }
}

/**
 * Copy element text by id.
 * @param {string} id Element id.
 * @returns {Promise<boolean>}
 * cite: [app.js:copy]
 */
function copyEl(id) {
  var el = byId(id);
  if (!el) {
    return Promise.resolve(false);
  }
  var t = el.textContent || el.value || "";
  return copyText(t);
}

/* --------------------------------------------------------------------- */
/* 8. Badges (urgency / priority / severity)                             */
/* cite: [app.js:badges]                                               */
/* --------------------------------------------------------------------- */

/**
 * Urgency badge HTML.
 * @param {string} u urgency (ORDER TODAY|this week|watch).
 * @returns {string} HTML span.
 * cite: [app.js:badges]
 */
function urgencyBadge(u) {
  var s = String(u || "watch");
  if (s === "ORDER TODAY") {
    return '<span class="badge badge-urgent">ORDER TODAY</span>';
  }
  if (s === "this week") {
    return '<span class="badge badge-week">this week</span>';
  }
  return '<span class="badge badge-watch">watch</span>';
}

/**
 * Priority badge HTML.
 * @param {string} p priority.
 * @returns {string} HTML span.
 * cite: [app.js:badges]
 */
function priorityBadge(p) {
  var s = String(p || "");
  if (s.indexOf("P0") === 0) {
    return '<span class="badge badge-p0">' + esc(s) + "</span>";
  }
  return '<span class="badge badge-p1">' + esc(s || "P1-today") + "</span>";
}

/**
 * Channel badge (text only, no extra CSS needed).
 * @param {string} c channel.
 * @returns {string}
 * cite: [app.js:badges]
 */
function channelLabel(c) {
  var s = String(c || "dm");
  if (s === "review") {
    return "⭐ review";
  }
  if (s === "scenario") {
    return "⚠ scenario";
  }
  return "💬 dm";
}

/* --------------------------------------------------------------------- */
/* 9. renderClose + per-tab renderers (idempotent)                       */
/*                                                                     */
/* renderClose(close) is the single entry: clears every container       */
/* first (idempotent re-render), then fills headline/KPIs + all tabs.   */
/* Safe to call twice with same data → same DOM (minus timestamps).     */
/* Required by smoke test. cite: [app.js:renderClose]                   */
/* --------------------------------------------------------------------- */

/**
 * Master renderer. Idempotent: wipes containers before filling.
 * @param {Object|null} close Close bundle (or null → empty state).
 * cite: [app.js:renderClose]
 */
function renderClose(close) {
  // Normalize: null → empty shell (keeps banners + help visible).
  state.close = close || null;
  // 1) Headline + KPIs (always, even when empty).
  renderHeadline(state.close);
  // 2) Per-tab renderers (each clears its own container first).
  renderToday(state.close);
  renderReorder(state.close);
  renderReplies(state.close);
  renderLeaks(state.close);
  renderListings(state.close);
  renderFiles(state.close);
  // 3) Tab counts + cache line + offline banner.
  renderCounts(state.close);
  updateCacheLine();
  updateOfflineBanner();
}

/**
 * Render headline + KPI cards + do_today.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderClose]
 */
function renderHeadline(close) {
  var h = byId("headlineTitle");
  var d = byId("closeDate");
  var s = byId("closeShop");
  var ing = byId("ingestLine");
  if (!close) {
    if (h) {
      h.textContent = "Run a close to see profit, risk & reorders.";
    }
    if (d) {
      d.textContent = "—";
    }
    if (s) {
      s.textContent = getShop();
    }
    if (ing) {
      ing.textContent = "ingest: — [ingest_report]";
    }
    setKPI("kpiGmv", "—");
    setKPI("kpiProfit", "—");
    setKPI("kpiMargin", "—");
    setKPI("kpiRisk", "—");
    setKPI("kpiReorder", "—");
    setKPI("kpiLeaks", "—");
    setKPI("kpiOrders", "—");
    setKPI("kpiBest", "—");
    setKPI("kpiCosts", "—");
    setKPI("kpiReplies", "—");
    setKPI("kpiNet", "—");
    setKPI("kpiSource", "empty");
    renderDoToday(null);
    return;
  }
  if (h) {
    h.textContent = String(close.headline || "Daily close ready.");
  }
  if (d) {
    d.textContent = String(close.date || "today");
  }
  if (s) {
    s.textContent = String(close.shop || getShop());
  }
  var k = close.kpis || {};
  var reorder = close.reorder_sheet || [];
  var must = 0;
  for (var i = 0; i < reorder.length; i++) {
    if (reorder[i] && reorder[i].urgency === "ORDER TODAY") {
      must++;
    }
  }
  var leaks = close.money_leaks || [];
  var replies = close.reply_queue || [];
  setKPI("kpiGmv", fmtUSD(k.gmv));
  setKPI("kpiProfit", fmtUSD(k.true_profit));
  setKPI("kpiMargin", k.margin_pct == null ? "—" : fmtNum(k.margin_pct, 1) + "%");
  setKPI("kpiRisk", fmtUSD(k.money_at_risk_usd));
  setKPI("kpiReorder", must + " today");
  setKPI("kpiLeaks", leaks.length + " leak(s)");
  var ordersTxt = (k.orders == null ? "—" : k.orders) + " · " + fmtUSD(k.aov);
  setKPI("kpiOrders", ordersTxt);
  var best = k.best_seller || {};
  setKPI("kpiBest", best.product ? trunc(best.product, 22) + " ×" + (best.qty || "?") : "—");
  setKPI("kpiCosts", fmtUSD(k.fees) + " · " + fmtUSD(k.shipping) + " · " + fmtUSD(k.cogs));
  setKPI("kpiReplies", replies.length + " msg(s)");
  setKPI("kpiNet", fmtUSD(k.net));
  setKPI("kpiSource", state.source || "live");
  renderDoToday(close.do_today || []);
  if (ing) {
    try {
      var rep = close.ingest_report || {};
      var ev = rep.events != null ? rep.events : "?";
      var fi = rep.files_ingested != null ? rep.files_ingested : "?";
      ing.textContent = "ingest: " + ev + " events · " + fi + " files [ingest_report]";
    } catch (e) {
      ing.textContent = "ingest: ok [ingest_report]";
    }
  }
}

/**
 * Set KPI value by id.
 * @param {string} id Element id.
 * @param {string} val Text.
 * cite: [app.js:renderClose]
 */
function setKPI(id, val) {
  var el = byId(id);
  if (el) {
    el.textContent = String(val);
  }
}

/**
 * Render do_today ordered list (idempotent: innerHTML rebuilt).
 * @param {string[]|null} items Bullets.
 * cite: [app.js:renderClose]
 */
function renderDoToday(items) {
  var ol = byId("doToday");
  if (!ol) {
    return;
  }
  ol.innerHTML = "";
  if (!items || !items.length) {
    var li = document.createElement("li");
    li.innerHTML = "Run demo or drop a folder to generate today's close. " +
      '<span class="cite">[index.html:do-today]</span>';
    ol.appendChild(li);
    return;
  }
  for (var i = 0; i < items.length; i++) {
    var li2 = document.createElement("li");
    li2.textContent = String(items[i]);
    var cite = document.createElement("span");
    cite.className = "cite";
    cite.style.marginLeft = "0.4rem";
    cite.textContent = "[close.do_today:" + (i + 1) + "]";
    li2.appendChild(cite);
    ol.appendChild(li2);
  }
}

/**
 * Render tab count badges.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderClose]
 */
function renderCounts(close) {
  function set(id, v) {
    var el = byId(id);
    if (el) {
      el.textContent = String(v);
    }
  }
  if (!close) {
    set("countToday", 3);
    set("countReorder", "—");
    set("countReplies", "—");
    set("countLeaks", "—");
    set("countListings", "—");
    set("countFiles", "—");
    return;
  }
  set("countToday", (close.do_today || []).length || 3);
  set("countReorder", (close.reorder_sheet || []).length);
  set("countReplies", (close.reply_queue || []).length);
  set("countLeaks", (close.money_leaks || []).length);
  set("countListings", (close.listing_fixes || []).length);
  var rep = close.ingest_report || {};
  set("countFiles", rep.files_ingested != null ? rep.files_ingested : (rep.events != null ? rep.events : "✓"));
}

/**
 * Render Today tab (top replies + reorders + leak).
 * Idempotent: containers cleared first.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderToday]
 */
function renderToday(close) {
  var meta = byId("todayMeta");
  var rBox = byId("todayReplies");
  var oBox = byId("todayReorders");
  var lBox = byId("todayLeak");
  if (!close) {
    if (meta) {
      meta.textContent = "No close yet. [index.html:today-meta]";
    }
    return;
  }
  var q = (state.filters.qToday || "").toLowerCase();
  function hit(t) {
    if (!q) {
      return true;
    }
    return String(t || "").toLowerCase().indexOf(q) >= 0;
  }
  var replies = (close.reply_queue || []).filter(function (x) {
    return hit((x.customer || "") + " " + (x.summary || "") + " " + (x.draft || ""));
  });
  var reorders = (close.reorder_sheet || []).filter(function (x) {
    return hit((x.product || "") + " " + (x.supplier || ""));
  });
  var leaks = (close.money_leaks || []).filter(function (x) {
    return hit((x.leak || "") + " " + (x.note || ""));
  });
  if (meta) {
    meta.textContent = close.date + " · " + replies.length + " replies · " +
      reorders.length + " reorders · " + leaks.length + " leaks · " +
      "source=" + state.source + " [app.js:renderToday]";
  }
  if (rBox) {
    rBox.innerHTML = "";
    if (!replies.length) {
      rBox.textContent = "No replies match. [instagram_dm.txt]";
    } else {
      var ul = document.createElement("ul");
      ul.style.margin = "0";
      ul.style.paddingLeft = "1.1rem";
      replies.slice(0, 3).forEach(function (x, idx) {
        var li = document.createElement("li");
        li.style.marginBottom = "0.3rem";
        var b = document.createElement("b");
        b.textContent = (x.priority || "") + " · " + (x.customer || "customer");
        li.appendChild(b);
        li.appendChild(document.createTextNode(" — " + trunc(x.summary || "", 90) + " "));
        var c = document.createElement("span");
        c.className = "cite";
        c.textContent = String(x.citation || "[reply:" + idx + "]");
        li.appendChild(c);
        ul.appendChild(li);
      });
      rBox.innerHTML = "";
      rBox.appendChild(ul);
    }
  }
  if (oBox) {
    oBox.innerHTML = "";
    if (!reorders.length) {
      oBox.textContent = "Stock healthy. [inventory.csv]";
    } else {
      var ul2 = document.createElement("ul");
      ul2.style.margin = "0";
      ul2.style.paddingLeft = "1.1rem";
      reorders.slice(0, 3).forEach(function (x) {
        var li = document.createElement("li");
        li.style.marginBottom = "0.3rem";
        li.innerHTML = "<b>" + esc(x.product || "?") + "</b> ×" + esc(x.reorder_qty) +
          " (" + esc(x.days_left) + "d left) ";
        var tmp = document.createElement("span");
        tmp.innerHTML = urgencyBadge(x.urgency);
        li.appendChild(tmp);
        li.appendChild(document.createTextNode(" "));
        var c2 = document.createElement("span");
        c2.className = "cite";
        c2.textContent = String(x.citation || "[inventory.csv]");
        li.appendChild(c2);
        ul2.appendChild(li);
      });
      oBox.appendChild(ul2);
    }
  }
  if (lBox) {
    lBox.innerHTML = "";
    if (!leaks.length) {
      lBox.textContent = "No leaks — push best seller. [seller_close.py:money_leaks]";
    } else {
      var l = leaks[0];
      lBox.innerHTML = "<b>" + esc(l.leak || "leak") + "</b> — " +
        esc(trunc(l.note || "", 160)) + " ";
      var ce = document.createElement("span");
      ce.className = "cite";
      ce.textContent = String(l.evidence || "[orders]");
      lBox.appendChild(ce);
      if (l.amount_usd != null) {
        lBox.appendChild(document.createTextNode(" · " + fmtUSD(l.amount_usd)));
      }
    }
  }
}

/**
 * Filter + sort reorder rows per toolbar state.
 * @param {Object[]} rows Raw rows.
 * @returns {Object[]} Filtered/sorted copy.
 * cite: [app.js:filters]
 */
function filteredReorder(rows) {
  var q = (state.filters.qReorder || "").toLowerCase();
  var urg = state.filters.urgency || "all";
  var sort = state.filters.sortReorder || "days_left";
  var out = (rows || []).filter(function (r) {
    if (urg !== "all" && String(r.urgency) !== urg) {
      return false;
    }
    if (q) {
      var hay = String(r.product || "") + " " + String(r.supplier || "") + " " + String(r.citation || "");
      if (hay.toLowerCase().indexOf(q) < 0) {
        return false;
      }
    }
    return true;
  });
  out.sort(function (a, b) {
    if (sort === "product") {
      return String(a.product || "").localeCompare(String(b.product || ""));
    }
    if (sort === "reorder_qty") {
      return Number(b.reorder_qty || 0) - Number(a.reorder_qty || 0);
    }
    if (sort === "sold_7d") {
      return Number(b.sold_7d || 0) - Number(a.sold_7d || 0);
    }
    if (sort === "on_hand") {
      return Number(a.on_hand || 0) - Number(b.on_hand || 0);
    }
    // default: days_left ascending (most urgent first)
    var da = Number(a.days_left);
    var db = Number(b.days_left);
    if (!isFinite(da)) {
      da = 9999;
    }
    if (!isFinite(db)) {
      db = 9999;
    }
    return da - db;
  });
  return out;
}

/**
 * Render Reorder+PO tab (table + PO pre + dead stock).
 * Idempotent: tbody + PO rebuilt from scratch.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderReorder]
 */
function renderReorder(close) {
  var body = byId("reorderBody");
  var meta = byId("reorderMeta");
  var po = byId("poPre");
  var dead = byId("deadStock");
  if (!close) {
    if (meta) {
      meta.textContent = "No rows yet. [index.html:reorder-meta]";
    }
    return;
  }
  var rows = filteredReorder(close.reorder_sheet || []);
  var total = (close.reorder_sheet || []).length;
  if (meta) {
    meta.textContent = rows.length + " of " + total + " rows · " +
      "filter=" + (state.filters.urgency || "all") + " · sort=" +
      (state.filters.sortReorder || "days_left") + " [app.js:renderReorder]";
  }
  if (body) {
    body.innerHTML = "";
    if (!rows.length) {
      var tr0 = document.createElement("tr");
      var td0 = document.createElement("td");
      td0.colSpan = 8;
      td0.className = "muted";
      td0.textContent = "No rows match filter. Clear search/urgency. [app.js:renderReorder]";
      tr0.appendChild(td0);
      body.appendChild(tr0);
    } else {
      rows.forEach(function (r) {
        var tr = document.createElement("tr");
        function td(html, text) {
          var c = document.createElement("td");
          if (html) {
            c.innerHTML = html;
          } else {
            c.textContent = String(text == null ? "—" : text);
          }
          tr.appendChild(c);
          return c;
        }
        td(null, r.product || "—");
        td(null, r.on_hand);
        td(null, r.sold_7d);
        td(null, r.days_left);
        td("<b>" + esc(r.reorder_qty) + "</b>");
        td(null, trunc(r.supplier || "—", 26));
        var u = document.createElement("td");
        u.innerHTML = urgencyBadge(r.urgency);
        tr.appendChild(u);
        var c = document.createElement("td");
        var s = document.createElement("span");
        s.className = "cite";
        s.textContent = String(r.citation || "[inventory.csv]");
        c.appendChild(s);
        tr.appendChild(c);
        body.appendChild(tr);
      });
    }
  }
  if (po) {
    po.textContent = String(close.po_draft || "Stock healthy — no PO needed today. [index.html:po-pre]");
  }
  if (dead) {
    dead.innerHTML = "";
    var dn = close.dead_stock_note || [];
    if (!dn.length) {
      dead.textContent = "Dead-stock note: none — cash is moving. [seller_close.py:dead_stock]";
    } else {
      var b = document.createElement("b");
      b.textContent = "Dead stock (" + dn.length + "): ";
      dead.appendChild(b);
      dn.slice(0, 3).forEach(function (x, i) {
        if (i) {
          dead.appendChild(document.createTextNode(" · "));
        }
        dead.appendChild(document.createTextNode(trunc(x.title || "dead stock", 80) + " "));
        var cc = document.createElement("span");
        cc.className = "cite";
        cc.textContent = String(x.evidence || "[dead_stock]");
        dead.appendChild(cc);
      });
    }
  }
}

/**
 * Filter reply queue per toolbar state.
 * @param {Object[]} rows Raw queue.
 * @returns {Object[]}
 * cite: [app.js:filters]
 */
function filteredReplies(rows) {
  var q = (state.filters.qReplies || "").toLowerCase();
  var pr = state.filters.priority || "all";
  var ch = state.filters.channel || "all";
  return (rows || []).filter(function (r) {
    if (pr !== "all" && String(r.priority) !== pr) {
      return false;
    }
    if (ch !== "all" && String(r.channel) !== ch) {
      return false;
    }
    if (q) {
      var hay = String(r.customer || "") + " " + String(r.summary || "") +
        " " + String(r.draft || "") + " " + String(r.citation || "");
      if (hay.toLowerCase().indexOf(q) < 0) {
        return false;
      }
    }
    return true;
  });
}

/**
 * Render Replies tab (cards with copy buttons + citations).
 * Idempotent: cards container rebuilt.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderReplies]
 */
function renderReplies(close) {
  var box = byId("replyCards");
  var meta = byId("repliesMeta");
  if (!box) {
    return;
  }
  box.innerHTML = "";
  if (!close || !(close.reply_queue || []).length) {
    if (meta) {
      meta.textContent = "No replies yet. [index.html:replies-meta]";
    }
    var art = document.createElement("article");
    art.className = "reply-card";
    art.innerHTML = "<b>No close yet</b> — press Demo close. " +
      'Example cites <span class="cite">[instagram_dm.txt:3]</span>. [index.html:reply-empty]';
    box.appendChild(art);
    return;
  }
  var rows = filteredReplies(close.reply_queue || []);
  if (meta) {
    var k = (close.kpis || {});
    meta.textContent = rows.length + " of " + (close.reply_queue || []).length +
      " drafts · " + fmtUSD(k.money_at_risk_usd) + " at risk · " +
      "P0 first [app.js:renderReplies]";
  }
  if (!rows.length) {
    var p = document.createElement("p");
    p.className = "muted small";
    p.textContent = "No drafts match filter. [app.js:renderReplies]";
    box.appendChild(p);
    return;
  }
  rows.forEach(function (r, idx) {
    var card = document.createElement("article");
    card.className = "reply-card";
    var top = document.createElement("div");
    top.className = "reply-top";
    var who = document.createElement("span");
    who.className = "reply-who";
    who.textContent = channelLabel(r.channel) + " · " + (r.customer || "customer");
    top.appendChild(who);
    var pr = document.createElement("span");
    pr.innerHTML = priorityBadge(r.priority);
    top.appendChild(pr);
    card.appendChild(top);
    var sum = document.createElement("p");
    sum.className = "reply-summary";
    sum.textContent = "“" + trunc(r.summary || "", 140) + "”";
    card.appendChild(sum);
    var draft = document.createElement("p");
    draft.className = "reply-draft";
    draft.textContent = String(r.draft || "(see scenario action)");
    card.appendChild(draft);
    var mrow = document.createElement("div");
    mrow.className = "reply-meta";
    var cite = document.createElement("span");
    cite.className = "cite";
    cite.textContent = String(r.citation || ("[reply:" + idx + "]"));
    mrow.appendChild(cite);
    var btn = document.createElement("button");
    btn.className = "btn";
    btn.type = "button";
    btn.textContent = "⧉ Copy draft";
    btn.setAttribute("aria-label", "Copy reply draft " + (idx + 1));
    btn.addEventListener("click", function () {
      copyText(String(r.draft || "") + " " + String(r.citation || ""));
    });
    mrow.appendChild(btn);
    card.appendChild(mrow);
    box.appendChild(card);
  });
}

/**
 * Render Leaks tab.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderLeaks]
 */
function renderLeaks(close) {
  var box = byId("leaksList");
  var meta = byId("leaksMeta");
  if (!box) {
    return;
  }
  box.innerHTML = "";
  if (!close || !(close.money_leaks || []).length) {
    if (meta) {
      meta.textContent = "No leaks yet. [index.html:leaks-meta]";
    }
    var d = document.createElement("div");
    d.className = "leak";
    d.innerHTML = "<b>No leaks found</b> — run demo. " +
      'Example cites <span class="cite">[orders] fees $.. / GMV $..</span>. [index.html:leak-empty]';
    box.appendChild(d);
    return;
  }
  var q = (state.filters.qLeaks || "").toLowerCase();
  var kind = state.filters.leak || "all";
  var rows = (close.money_leaks || []).filter(function (l) {
    if (kind !== "all" && String(l.leak) !== kind) {
      return false;
    }
    if (q && (String(l.leak || "") + " " + String(l.note || "")).toLowerCase().indexOf(q) < 0) {
      return false;
    }
    return true;
  });
  if (meta) {
    meta.textContent = rows.length + " of " + (close.money_leaks || []).length +
      " leak(s) · fix one per day [app.js:renderLeaks]";
  }
  if (!rows.length) {
    var p = document.createElement("p");
    p.className = "muted small";
    p.textContent = "No leaks match filter. [app.js:renderLeaks]";
    box.appendChild(p);
    return;
  }
  rows.forEach(function (l) {
    var div = document.createElement("div");
    div.className = "leak";
    var t = document.createElement("p");
    t.className = "leak-title";
    t.textContent = (l.leak || "leak") + (l.amount_usd != null ? " · " + fmtUSD(l.amount_usd) : "");
    div.appendChild(t);
    var n = document.createElement("p");
    n.className = "leak-note";
    n.textContent = String(l.note || "");
    div.appendChild(n);
    var mrow = document.createElement("div");
    mrow.className = "reply-meta";
    var c = document.createElement("span");
    c.className = "cite";
    c.textContent = String(l.evidence || "[money_leaks]");
    mrow.appendChild(c);
    var b = document.createElement("button");
    b.className = "btn";
    b.type = "button";
    b.textContent = "⧉ Copy fix";
    b.addEventListener("click", function () {
      copyText("Fix " + (l.leak || "") + ": " + (l.note || "") + " " + (l.evidence || ""));
    });
    mrow.appendChild(b);
    div.appendChild(mrow);
    box.appendChild(div);
  });
}

/**
 * Render Listings tab.
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderListings]
 */
function renderListings(close) {
  var box = byId("listingFixes");
  var meta = byId("listingsMeta");
  if (!box) {
    return;
  }
  box.innerHTML = "";
  if (!close || !(close.listing_fixes || []).length) {
    if (meta) {
      meta.textContent = "No fixes yet. [index.html:listings-meta]";
    }
    var d = document.createElement("div");
    d.className = "fix";
    d.innerHTML = "<b>No close yet</b> — run demo. " +
      'Fixes cite like <span class="cite">[reviews.csv:4]</span>. [index.html:listing-empty]';
    box.appendChild(d);
    return;
  }
  var q = (state.filters.qListings || "").toLowerCase();
  var rows = (close.listing_fixes || []).filter(function (f) {
    if (!q) {
      return true;
    }
    return (String(f.fix || "") + " " + String(f.title || "")).toLowerCase().indexOf(q) >= 0;
  });
  if (meta) {
    meta.textContent = rows.length + " of " + (close.listing_fixes || []).length +
      " fix(es) [app.js:renderListings]";
  }
  rows.forEach(function (f) {
    var div = document.createElement("div");
    div.className = "fix";
    var t = document.createElement("p");
    t.className = "fix-title";
    t.textContent = "[" + (f.fix || "FIX") + "] " + trunc(f.title || "", 140);
    div.appendChild(t);
    var mrow = document.createElement("div");
    mrow.className = "reply-meta";
    var c = document.createElement("span");
    c.className = "cite";
    c.textContent = String(f.evidence || "[listing]");
    mrow.appendChild(c);
    var b = document.createElement("button");
    b.className = "btn";
    b.type = "button";
    b.textContent = "⧉ Copy";
    b.addEventListener("click", function () {
      copyText("Listing fix [" + (f.fix || "") + "] " + (f.title || "") + " " + (f.evidence || ""));
    });
    mrow.appendChild(b);
    div.appendChild(mrow);
    box.appendChild(div);
  });
}

/**
 * Render Files tab (ingest report + raw JSON + drop log).
 * @param {Object|null} close Close bundle.
 * cite: [app.js:renderFiles]
 */
function renderFiles(close) {
  var pre = byId("ingestReport");
  var raw = byId("rawJSON");
  if (pre) {
    if (!close || !close.ingest_report) {
      pre.textContent = '{ "status": "no close yet — press Demo close", "hint": "POST /api/v1/seller/close {\\"demo\\": true}", "cite": "[index.html:ingest-empty]" }';
    } else {
      pre.textContent = safeStringify(close.ingest_report);
    }
  }
  if (raw) {
    if (!close) {
      raw.textContent = '{ "hint": "run demo — full close.json appears here", "cite": "[index.html:raw-empty]" }';
    } else {
      raw.textContent = safeStringify(close).slice(0, 60000);
    }
  }
  renderFileList();
}

/**
 * Render browser-side drop log (Files tab).
 * cite: [app.js:renderFiles]
 */
function renderFileList() {
  var ul = byId("fileList");
  if (!ul) {
    return;
  }
  ul.innerHTML = "";
  if (!state.files.length) {
    var li = document.createElement("li");
    var s1 = document.createElement("span");
    s1.textContent = "No files dropped yet";
    li.appendChild(s1);
    var c = document.createElement("span");
    c.className = "cite";
    c.textContent = "[index.html:files-empty]";
    li.appendChild(c);
    ul.appendChild(li);
    return;
  }
  state.files.slice(0, 20).forEach(function (f) {
    var li2 = document.createElement("li");
    var a = document.createElement("span");
    a.textContent = String(f.name || "?") + (f.size ? " (" + f.size + "B)" : "");
    li2.appendChild(a);
    var cc = document.createElement("span");
    cc.className = "cite";
    cc.textContent = "[browser-drop] names only";
    li2.appendChild(cc);
    ul.appendChild(li2);
  });
}

/* --------------------------------------------------------------------- */
/* 10. Tabs (Today/Reorder+PO/Replies/Leaks/Listings/Files)              */
/* Keyboard: 1..6, arrows. Persisted to localStorage close_tab.         */
/* cite: [app.js:tabs]                                                 */
/* --------------------------------------------------------------------- */

/**
 * Switch visible tab (idempotent, ARIA-correct).
 * @param {string} name Tab name.
 * cite: [app.js:tabs]
 */
function switchTab(name) {
  if (TAB_ORDER.indexOf(name) < 0) {
    name = "today";
  }
  state.tab = name;
  try {
    localStorage.setItem(LS.tab, name);
  } catch (e) {
    /* ignore */
  }
  var tabs = $all('[role="tab"][data-tab]');
  for (var i = 0; i < tabs.length; i++) {
    var t = tabs[i];
    var on = t.getAttribute("data-tab") === name;
    t.setAttribute("aria-selected", on ? "true" : "false");
    if (on) {
      t.removeAttribute("tabindex");
    } else {
      t.setAttribute("tabindex", "-1");
    }
  }
  var panels = $all('[role="tabpanel"][data-panel]');
  for (var j = 0; j < panels.length; j++) {
    var p = panels[j];
    if (p.getAttribute("data-panel") === name) {
      p.classList.remove("hidden");
    } else {
      p.classList.add("hidden");
    }
  }
  // Focus search of new tab on "/" — nothing else to do here.
}

/**
 * Wire tab buttons (click + arrow keys).
 * cite: [app.js:tabs]
 */
function initTabs() {
  var tabs = $all('[role="tab"][data-tab]');
  tabs.forEach(function (btn) {
    btn.addEventListener("click", function () {
      switchTab(btn.getAttribute("data-tab") || "today");
    });
    btn.addEventListener("keydown", function (e) {
      var cur = TAB_ORDER.indexOf(state.tab);
      if (e.key === "ArrowRight") {
        e.preventDefault();
        var nx = TAB_ORDER[(cur + 1) % TAB_ORDER.length];
        switchTab(nx);
        var el = $('[role="tab"][data-tab="' + nx + '"]');
        if (el) {
          el.focus();
        }
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        var pv = TAB_ORDER[(cur - 1 + TAB_ORDER.length) % TAB_ORDER.length];
        switchTab(pv);
        var el2 = $('[role="tab"][data-tab="' + pv + '"]');
        if (el2) {
          el2.focus();
        }
      } else if (e.key === "Home") {
        e.preventDefault();
        switchTab(TAB_ORDER[0]);
      } else if (e.key === "End") {
        e.preventDefault();
        switchTab(TAB_ORDER[TAB_ORDER.length - 1]);
      }
    });
  });
  // Restore saved tab (?tab= wins).
  var initial = "today";
  try {
    var q = new URLSearchParams(window.location.search).get("tab");
    if (q && TAB_ORDER.indexOf(q) >= 0) {
      initial = q;
    } else {
      var saved = localStorage.getItem(LS.tab);
      if (saved && TAB_ORDER.indexOf(saved) >= 0) {
        initial = saved;
      }
    }
  } catch (e) {
    /* ignore */
  }
  switchTab(initial);
}

/* --------------------------------------------------------------------- */
/* 11. Filters / search / sort wiring                                    */
/* cite: [app.js:filters]                                              */
/* --------------------------------------------------------------------- */

/**
 * Bind value with optional debounce re-render.
 * @param {string} id Element id.
 * @param {string} key state.filters key.
 * @param {Function} rerender Which renderer to call.
 * @param {boolean} deb Debounce?
 * cite: [app.js:filters]
 */
function bindFilter(id, key, rerender, deb) {
  var el = byId(id);
  if (!el) {
    return;
  }
  function apply() {
    state.filters[key] = String(el.value == null ? "" : el.value);
    rerender(state.close);
  }
  el.addEventListener("input", deb ? debounce(apply, 160) : apply);
  el.addEventListener("change", apply);
}

/**
 * Wire table header click-to-sort (reorder).
 * cite: [app.js:filters]
 */
function initSortHeaders() {
  var ths = $all('th[data-sort]');
  ths.forEach(function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-sort") || "days_left";
      // Toggle: clicking same key flips direction for product only;
      // others have fixed useful direction (see filteredReorder).
      state.filters.sortReorder = k;
      var sel = byId("sortReorder");
      if (sel) {
        try {
          sel.value = k;
        } catch (e) {
          /* custom key like on_hand not in select — keep */
        }
      }
      renderReorder(state.close);
      toast("Sorted by " + k + " [app.js:filters]");
    });
  });
}

/**
 * Init all search/filter/sort controls.
 * cite: [app.js:filters]
 */
function initFilters() {
  bindFilter("searchToday", "qToday", renderToday, true);
  bindFilter("searchReorder", "qReorder", renderReorder, true);
  bindFilter("searchReplies", "qReplies", renderReplies, true);
  bindFilter("searchLeaks", "qLeaks", renderLeaks, true);
  bindFilter("searchListings", "qListings", renderListings, true);
  bindFilter("filterUrgency", "urgency", renderReorder, false);
  bindFilter("sortReorder", "sortReorder", renderReorder, false);
  bindFilter("filterPriority", "priority", renderReplies, false);
  bindFilter("filterChannel", "channel", renderReplies, false);
  bindFilter("filterLeak", "leak", renderLeaks, false);
  initSortHeaders();
}

/* --------------------------------------------------------------------- */
/* 12. Controls: shop/seed/api/demo/csv/copy/theme/print                */
/* cite: [app.js:controls]                                             */
/* --------------------------------------------------------------------- */

/**
 * Wire header + control buttons.
 * cite: [app.js:controls]
 */
function initControls() {
  // Restore persisted shop/seed/api into inputs.
  try {
    var s = localStorage.getItem(LS.shop);
    var shopBox = byId("shopInput");
    if (shopBox && s) {
      shopBox.value = s;
    }
  } catch (e) {
    /* ignore */
  }
  try {
    var sd = localStorage.getItem(LS.seed);
    var seedBox = byId("seedInput");
    if (seedBox && sd != null && sd !== "") {
      seedBox.value = String(sd);
    }
  } catch (e2) {
    /* ignore */
  }
  try {
    var ab = localStorage.getItem(LS.api) || apiOverrideFromURL();
    var apiBox = byId("apiInput");
    if (apiBox && ab) {
      apiBox.value = ab;
    }
  } catch (e3) {
    /* ignore */
  }
  var shopIn = byId("shopInput");
  if (shopIn) {
    shopIn.addEventListener("change", function () {
      setShop(shopIn.value);
      // Live-update shop label + PO drafts (re-render, no refetch).
      if (state.close) {
        state.close.shop = getShop();
        renderClose(state.close);
      } else {
        var cs = byId("closeShop");
        if (cs) {
          cs.textContent = getShop();
        }
      }
    });
  }
  var seedIn = byId("seedInput");
  if (seedIn) {
    seedIn.addEventListener("change", function () {
      setSeed(seedIn.value);
    });
  }
  var apiIn = byId("apiInput");
  if (apiIn) {
    apiIn.addEventListener("change", function () {
      setApiBase(apiIn.value);
      toast("API base saved. [app.js:api-client]");
    });
  }
  function onDemo(e) {
    if (e) {
      e.preventDefault();
    }
    loadDemo();
  }
  function onFetch(e) {
    if (e) {
      e.preventDefault();
    }
    fetchClose();
  }
  function onCSV(e) {
    if (e) {
      e.preventDefault();
    }
    downloadCSV();
  }
  function onPrint(e) {
    if (e) {
      e.preventDefault();
    }
    window.print();
  }
  var pairs = [
    ["btnDemo", onDemo],
    ["btnDemoTop", onDemo],
    ["btnTodayDemo", onDemo],
    ["btnFetch", onFetch],
    ["btnCSV", onCSV],
    ["btnCSVTop", onCSV],
    ["btnTodayCSV", onCSV],
    ["btnPrintTop", onPrint],
    ["btnTodayPrint", onPrint],
  ];
  pairs.forEach(function (pr) {
    var b = byId(pr[0]);
    if (b) {
      b.addEventListener("click", pr[1]);
    }
  });
  var bf = byId("btnFolder");
  if (bf) {
    bf.addEventListener("click", function () {
      loadFolderHint();
      switchTab("files");
    });
  }
  var br = byId("btnRetry");
  if (br) {
    br.addEventListener("click", function () {
      hideError();
      fetchClose();
    });
  }
  var bld = byId("btnLoadDemoFallback");
  if (bld) {
    bld.addEventListener("click", function () {
      hideError();
      loadDemo();
    });
  }
  var bcc = byId("btnClearCache");
  if (bcc) {
    bcc.addEventListener("click", function () {
      clearCache();
    });
  }
  var bcp = byId("btnCopyPO");
  if (bcp) {
    bcp.addEventListener("click", function () {
      copyEl("poPre");
    });
  }
  var bcp2 = byId("btnCopyPO2");
  if (bcp2) {
    bcp2.addEventListener("click", function () {
      copyEl("poPre");
    });
  }
  var bcr = byId("btnCopyReplies");
  if (bcr) {
    bcr.addEventListener("click", function () {
      copyAllReplies();
    });
  }
  var bcar = byId("btnCopyAllReplies");
  if (bcar) {
    bcar.addEventListener("click", function () {
      copyAllReplies();
    });
  }
  var bcrc = byId("btnCopyReorderCSV");
  if (bcrc) {
    bcrc.addEventListener("click", function () {
      copyReorderCSV();
    });
  }
  var bcj = byId("btnCopyJSON");
  if (bcj) {
    bcj.addEventListener("click", function () {
      copyEl("rawJSON");
    });
  }
  var bdj = byId("btnDownloadJSON");
  if (bdj) {
    bdj.addEventListener("click", function () {
      if (state.close) {
        saveTextFile("close.json", safeStringify(state.close), "application/json");
      } else {
        toast("No close to download. [app.js:download]");
      }
    });
  }
  var bdp = byId("btnDownloadPO");
  if (bdp) {
    bdp.addEventListener("click", function () {
      var el = byId("poPre");
      saveTextFile("po.txt", el ? el.textContent : "", "text/plain");
    });
  }
  var bt = byId("btnTheme");
  if (bt) {
    bt.addEventListener("click", function () {
      cycleTheme();
    });
  }
}

/**
 * Copy all reply drafts (joined, with citations).
 * cite: [app.js:copy]
 */
function copyAllReplies() {
  if (!state.close || !(state.close.reply_queue || []).length) {
    toast("No replies to copy. [app.js:copy]");
    return Promise.resolve(false);
  }
  var rows = filteredReplies(state.close.reply_queue || []);
  if (!rows.length) {
    rows = state.close.reply_queue || [];
  }
  var text = rows.map(function (r, i) {
    return "[" + (i + 1) + "] " + (r.customer || "") + " (" + (r.citation || "") + ")\n" + (r.draft || "");
  }).join("\n\n---\n\n");
  return copyText(text);
}

/**
 * Copy filtered reorder rows as CSV.
 * cite: [app.js:copy]
 */
function copyReorderCSV() {
  if (!state.close) {
    toast("No reorder to copy. [app.js:copy]");
    return Promise.resolve(false);
  }
  var rows = filteredReorder(state.close.reorder_sheet || []);
  var lines = ["product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation"];
  rows.forEach(function (r) {
    lines.push([r.product, r.on_hand, r.sold_7d, r.days_left, r.reorder_qty, r.supplier, r.urgency, r.citation].map(function (v) {
      var s = String(v == null ? "" : v);
      if (/[",\n]/.test(s)) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }).join(","));
  });
  return copyText(lines.join("\n"));
}

/* --------------------------------------------------------------------- */
/* 13. Dropzone (folder-drop + demo button)                              */
/* Browsers cannot upload server paths — drops log names + show hint.   */
/* cite: [app.js:dropzone]                                             */
/* --------------------------------------------------------------------- */

/**
 * Wire folder dropzone (drag/drop + click + file input).
 * cite: [app.js:dropzone]
 */
function initDropzone() {
  var dz = byId("dropzone");
  var fi = byId("fileInput");
  if (!dz) {
    return;
  }
  function over(e) {
    e.preventDefault();
    dz.classList.add("drag");
  }
  function leave(e) {
    e.preventDefault();
    dz.classList.remove("drag");
  }
  function drop(e) {
    e.preventDefault();
    dz.classList.remove("drag");
    var files = null;
    try {
      files = (e.dataTransfer && e.dataTransfer.files) || null;
    } catch (err) {
      files = null;
    }
    if (files && files.length) {
      loadFolderHint(files);
      switchTab("files");
    } else {
      loadFolderHint("drop (no file list)");
    }
  }
  dz.addEventListener("dragover", over);
  dz.addEventListener("dragenter", over);
  dz.addEventListener("dragleave", leave);
  dz.addEventListener("drop", drop);
  dz.addEventListener("click", function () {
    // Click → hint (not file picker, to avoid implying upload works).
    // Still allow picker via double-click for name logging.
    loadFolderHint();
  });
  dz.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      loadFolderHint();
    }
  });
  if (fi) {
    fi.addEventListener("change", function () {
      if (fi.files && fi.files.length) {
        loadFolderHint(fi.files);
        switchTab("files");
      }
      try {
        fi.value = "";
      } catch (e) {
        /* ignore */
      }
    });
  }
}

/* --------------------------------------------------------------------- */
/* 14. Theme (dark-friendly)                                             */
/* cite: [app.js:theme]                                                */
/* --------------------------------------------------------------------- */

/**
 * Apply theme (auto|light|dark).
 * @param {string} t Theme.
 * cite: [app.js:theme]
 */
function applyTheme(t) {
  var root = document.documentElement;
  if (t !== "light" && t !== "dark") {
    t = "auto";
  }
  if (t === "auto") {
    root.setAttribute("data-theme", "auto");
  } else {
    root.setAttribute("data-theme", t);
  }
  try {
    localStorage.setItem(LS.theme, t);
  } catch (e) {
    /* ignore */
  }
}

/**
 * Cycle theme auto → light → dark → auto.
 * cite: [app.js:theme]
 */
function cycleTheme() {
  var cur = "auto";
  try {
    cur = localStorage.getItem(LS.theme) || document.documentElement.getAttribute("data-theme") || "auto";
  } catch (e) {
    cur = "auto";
  }
  var nx = cur === "auto" ? "light" : cur === "light" ? "dark" : "auto";
  applyTheme(nx);
  toast("Theme: " + nx + " [app.js:theme]");
}

/**
 * Init theme from storage.
 * cite: [app.js:theme]
 */
function initTheme() {
  var t = "auto";
  try {
    t = localStorage.getItem(LS.theme) || "auto";
  } catch (e) {
    t = "auto";
  }
  applyTheme(t);
}

/* --------------------------------------------------------------------- */
/* 15. Keyboard shortcuts                                                */
/*   1..6 tabs · d demo · c csv · p print · / search · Esc blur         */
/* cite: [app.js:keyboard]                                             */
/* --------------------------------------------------------------------- */

/**
 * Focus search box of current tab.
 * cite: [app.js:keyboard]
 */
function focusSearch() {
  var map = {
    today: "searchToday",
    reorder: "searchReorder",
    replies: "searchReplies",
    leaks: "searchLeaks",
    listings: "searchListings",
    files: "searchListings",
  };
  var id = map[state.tab] || "searchToday";
  var el = byId(id);
  // Files tab has no search — jump to listings search instead? keep simple.
  if (!el && state.tab === "files") {
    switchTab("reorder");
    el = byId("searchReorder");
  }
  if (el) {
    el.focus();
    try {
      el.select();
    } catch (e) {
      /* ignore */
    }
  }
}

/**
 * Init global keyboard shortcuts (ignored when typing).
 * cite: [app.js:keyboard]
 */
function initKeyboard() {
  document.addEventListener("keydown", function (e) {
    var tag = "";
    try {
      tag = String((e.target && e.target.tagName) || "").toLowerCase();
    } catch (err) {
      tag = "";
    }
    var typing = tag === "input" || tag === "textarea" || tag === "select" || (e.target && e.target.isContentEditable);
    if (e.key === "Escape") {
      var tst = byId("toast");
      if (tst) {
        tst.classList.add("hidden");
      }
      if (document.activeElement && document.activeElement.blur) {
        document.activeElement.blur();
      }
      return;
    }
    if (typing) {
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) {
      return;
    }
    var k = String(e.key || "");
    if (k >= "1" && k <= "6") {
      e.preventDefault();
      switchTab(TAB_ORDER[parseInt(k, 10) - 1]);
    } else if (k === "d" || k === "D") {
      e.preventDefault();
      loadDemo();
    } else if (k === "c" || k === "C") {
      e.preventDefault();
      downloadCSV();
    } else if (k === "p" || k === "P") {
      e.preventDefault();
      window.print();
    } else if (k === "/") {
      e.preventDefault();
      focusSearch();
    }
  });
}

/* --------------------------------------------------------------------- */
/* 16. Boot (DOMContentLoaded)                                           */
/*   - init theme/tabs/filters/controls/dropzone/keyboard                */
/*   - online/offline listeners                                          */
/*   - restore 24h cache → render immediately (offline-first)            */
/*   - ?demo=1 autodemo · ?seed= · ?shop= · ?tab= · ?api=                */
/* cite: [app.js:boot]                                                 */
/* --------------------------------------------------------------------- */

/**
 * Apply URL presets (?shop= ?seed= ?tab= ?api= ?demo=).
 * cite: [app.js:boot]
 */
function applyURLPresets() {
  try {
    var q = new URLSearchParams(window.location.search);
    var shop = q.get("shop");
    if (shop && shop.trim()) {
      setShop(shop);
      var sb = byId("shopInput");
      if (sb) {
        sb.value = getShop();
      }
    }
    var seed = q.get("seed");
    if (seed != null && seed !== "" && isFinite(parseInt(seed, 10))) {
      setSeed(parseInt(seed, 10));
      var eb = byId("seedInput");
      if (eb) {
        eb.value = String(getSeed());
      }
    }
    var api = q.get("api");
    if (api && api.trim()) {
      setApiBase(api.trim());
    }
  } catch (e) {
    /* ignore [app.js:boot] */
  }
}

/**
 * Boot the PWA (called on DOMContentLoaded).
 * cite: [app.js:boot]
 */
function boot() {
  initTheme();
  applyURLPresets();
  initTabs();
  initFilters();
  initControls();
  initDropzone();
  initKeyboard();
  updateOfflineBanner();
  updateCacheLine();
  try {
    window.addEventListener("online", function () {
      updateOfflineBanner();
      toast("Back online. [app.js:offline]");
    });
    window.addEventListener("offline", function () {
      updateOfflineBanner();
      toast("Offline — showing cache. [app.js:offline]");
    });
  } catch (e) {
    /* ignore */
  }
  // Restore cache first (instant paint, offline-first).
  var cached = loadCache();
  if (cached && cached.close) {
    state.close = cached.close;
    state.source = "cache";
    renderClose(state.close);
    setStatus(
      "Restored cached close (" + (cached.shop || "?") + ") — press Demo/Fetch for fresh. [app.js:cache]",
      ""
    );
  } else {
    renderClose(null);
  }
  // ?demo=1 (or #demo) → autodemo for kiosks/links.
  var wantDemo = false;
  try {
    var q = new URLSearchParams(window.location.search);
    if (q.get("demo") === "1" || q.get("demo") === "true") {
      wantDemo = true;
    }
    if (String(window.location.hash || "").indexOf("demo") >= 0) {
      wantDemo = true;
    }
  } catch (e) {
    wantDemo = false;
  }
  if (wantDemo) {
    loadDemo();
  } else if (!cached) {
    setStatus("Idle. Press “Demo close” (d) or drop a folder. API: POST " + API_CLOSE + " [app.js:boot]");
  }
  // Re-apply API box after boot (so ?api= shows).
  try {
    var ab = getApiBase();
    var box = byId("apiInput");
    if (box && ab && !box.value) {
      box.value = ab;
    }
  } catch (e) {
    /* ignore */
  }
}

// Expose required globals for smoke tests + console power users.
// cite: [app.js:exports]
try {
  window.loadDemo = loadDemo;
  window.loadFolderHint = loadFolderHint;
  window.renderClose = renderClose;
  window.copyText = copyText;
  window.downloadCSV = downloadCSV;
  window.CloseApp = {
    state: state,
    getApiBase: getApiBase,
    setApiBase: setApiBase,
    getShop: getShop,
    getSeed: getSeed,
    fetchClose: fetchClose,
    switchTab: switchTab,
    saveCache: saveCache,
    loadCache: loadCache,
    clearCache: clearCache,
    apiURL: apiURL,
  };
} catch (e) {
  /* non-browser — ignore [app.js:exports] */
}

// Boot on DOM ready (defer-safe + readyState-safe).
// cite: [app.js:boot]
try {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
} catch (e) {
  try {
    document.addEventListener("DOMContentLoaded", boot);
  } catch (e2) {
    /* ignore */
  }
}



