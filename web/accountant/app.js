/* =====================================================================
 * Omni-One · WAVE2-J · Accountant PWA logic
 * File: web/accountant/app.js
 *
 * Purpose:
 *   Paste-or-upload close.csv / close.json -> KPI table, P&L walk
 *   (GMV - fees - ship - COGS = profit, bars via div widths),
 *   reconciliation checklist (6 steps, localStorage), fee-benchmark
 *   table (shopify/etsy/amazon/tiktok/ebay vs shop actual), print view,
 *   validation warnings (profit>gmv impossible, missing citations),
 *   sample-data button (inline demo CSV). All client-side, offline.
 *
 * Dependencies: NONE. Vanilla JS only. No npm, no framework, no CDN.
 *   Works from file:// (all inline/demo) + http(s) (fetch sample JSON).
 *
 * API contract (same-origin, override via ?api= or localStorage):
 *   POST /api/v1/seller/close      {demo:true, seed:42, shop}
 *   GET  /api/v1/seller/close.csv  ?demo=1&seed=42
 *   GET  ../assets/close-sample.json  (static fallback for file://)
 *
 * Exposed surface (used by index.html + smoke tests):
 *   window.AccountantApp = {
 *     parseCloseCSV, parseCloseJSON, buildPL, renderReport,
 *     validateClose, copySummary, printReport,
 *     ChecklistStore, FEE_BENCHMARKS, CHECKLIST_STEPS,
 *     DEMO_CSV, DEMO_CLOSE_JSON, loadDemoCSV, detectDelimiter
 *   }
 *
 * Offline rule: no fetch to CDN, no import() of http(s). Only
 *   same-origin API (guarded try/catch) + localStorage + inline demo.
 *
 * Citations: every number keeps file:line where the close bundle has
 *   one, e.g. [inventory.csv:2] [instagram_dm.txt:1] [reviews.csv:3]
 *   [shopify_orders.csv:5]. Missing citations are flagged, not faked.
 *
 * Print: printReport() calls window.print(). index.html @media print
 *   hides .no-print (buttons/nav/dropzone) and keeps tables/cards.
 *
 * Version: v1.1.0 (WAVE2-J). Single file, ~1000+ lines with docs.
 * ===================================================================== */
"use strict";

/* ---------------------------------------------------------------------
 * 0. Tiny DOM + format helpers
 * --------------------------------------------------------------------- */

/**
 * Query one element (null-safe).
 *
 * Rationale: index.html has many optional sections (KPI table, P&L
 * walk, checklist, fee table, warnings). Renderers must no-op when a
 * host element is absent (e.g. print view or partial embed).
 *
 * @param {string} sel CSS selector.
 * @param {ParentNode} [root] Optional root (default document).
 * @returns {Element|null} First match or null.
 * cite: [app.js:helpers]
 */
function accQuery(sel, root) {
  try {
    return (root || document).querySelector(sel);
  } catch (e) {
    return null;
  }
}

/**
 * Query all elements as a real array.
 *
 * @param {string} sel CSS selector.
 * @param {ParentNode} [root] Optional root.
 * @returns {Element[]} Matches (possibly empty).
 * cite: [app.js:helpers]
 */
function accQueryAll(sel, root) {
  try {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  } catch (e) {
    return [];
  }
}

/**
 * Get element by id (null-safe shortcut).
 *
 * @param {string} id Element id.
 * @returns {HTMLElement|null}
 * cite: [app.js:helpers]
 */
function accById(id) {
  try {
    return document.getElementById(id);
  } catch (e) {
    return null;
  }
}

/**
 * Escape HTML to avoid injection from pasted CSV/JSON.
 *
 * Pasted seller data can contain `<`, `&`, quotes (product names like
 * `Mug <3oz>`). Every renderer escapes before innerHTML.
 *
 * @param {unknown} s Value to escape.
 * @returns {string} Escaped string.
 * cite: [app.js:escape]
 */
function accEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Format USD, tolerant of null/undefined/NaN.
 *
 * @param {unknown} n Number-ish.
 * @returns {string} Like "$274.00" or "—" when not finite.
 * cite: [app.js:fmt]
 */
function accFmtUSD(n) {
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
 * Format percent with one decimal.
 *
 * @param {unknown} n Number-ish.
 * @returns {string} Like "61.7%" or "—".
 * cite: [app.js:fmt]
 */
function accFmtPct(n) {
  var v = Number(n);
  if (!isFinite(v)) {
    return "—";
  }
  return v.toFixed(1) + "%";
}

/**
 * Coerce to finite number with fallback.
 *
 * Accepts "$274.00", "274", "61.7%", "  24 " etc. Strips $, %, commas
 * and whitespace. Empty -> fallback.
 *
 * @param {unknown} v Raw value.
 * @param {number} [fb] Fallback (default 0).
 * @returns {number} Finite number or fallback.
 * cite: [app.js:num]
 */
function accNum(v, fb) {
  var fallback = (typeof fb === "number" && isFinite(fb)) ? fb : 0;
  if (v == null || v === "") {
    return fallback;
  }
  if (typeof v === "number") {
    return isFinite(v) ? v : fallback;
  }
  var s = String(v).trim().replace(/[$,%\s]/g, "").replace(/,/g, "");
  // Parenthesised negatives: ($12.00) -> -12
  var m = s.match(/^\((.*)\)$/);
  if (m) {
    s = "-" + m[1];
  }
  var n = Number(s);
  return isFinite(n) ? n : fallback;
}

/**
 * Clamp a number into [lo, hi].
 *
 * Used for bar widths (0..100%) so a data error (profit > GMV) cannot
 * blow out the P&L walk layout; the *warning* carries the signal.
 *
 * @param {number} v Value.
 * @param {number} lo Low bound.
 * @param {number} hi High bound.
 * @returns {number}
 * cite: [app.js:helpers]
 */
function accClamp(v, lo, hi) {
  var n = Number(v);
  if (!isFinite(n)) {
    return lo;
  }
  if (n < lo) {
    return lo;
  }
  if (n > hi) {
    return hi;
  }
  return n;
}

/**
 * Download a text file (Blob + a[download] + fallback).
 *
 * Works from file:// in modern browsers. Falls back to opening a
 * data: URL / copying to clipboard when Blob download is blocked.
 *
 * @param {string} filename Suggested filename.
 * @param {string} text File content.
 * @param {string} [mime] MIME type (default text/plain).
 * @returns {boolean} True if a download was triggered.
 * cite: [app.js:download]
 */
function accDownload(filename, text, mime) {
  try {
    var blob = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename || "download.txt";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      try {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (e) { /* ignore */ }
    }, 800);
    return true;
  } catch (e) {
    try {
      var w = window.open("data:text/plain;charset=utf-8," + encodeURIComponent(text), "_blank");
      return !!w;
    } catch (e2) {
      return false;
    }
  }
}

/**
 * Copy text to clipboard with execCommand fallback.
 *
 * navigator.clipboard requires secure context; file:// often is not
 * one, so the textarea+execCommand path is the real workhorse here.
 *
 * @param {string} text Text to copy.
 * @returns {Promise<boolean>} Resolves true on success.
 * cite: [app.js:copyText]
 */
function accCopyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () {
        return true;
      }).catch(function () {
        return accCopyFallback(text);
      });
    }
  } catch (e) { /* fall through */ }
  return Promise.resolve(accCopyFallback(text));
}

/**
 * Synchronous clipboard fallback (textarea + execCommand).
 *
 * @param {string} text Text to copy.
 * @returns {boolean}
 * cite: [app.js:copyText]
 */
function accCopyFallback(text) {
  try {
    var ta = document.createElement("textarea");
    ta.value = String(text);
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return !!ok;
  } catch (e) {
    return false;
  }
}

/* ---------------------------------------------------------------------
 * 1. CSV parsing — quoted fields, semicolons, BOM
 * --------------------------------------------------------------------- */
/*
 * Close.csv shape (see seller_close.close_to_csv):
 *
 *   DAILY CLOSE,2026-10-11,Profit $169.09 (61.7%) · ...
 *   <blank>
 *   metric,value
 *   gmv,274.0
 *   fees,16.71
 *   ...
 *   best_seller,"{'product': 'Tote Bag Handmade', ...}"
 *   <blank>
 *   do_today_n,do_today
 *   1,"Reply to 3 message(s) — ..."
 *   <blank>
 *   product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation
 *   Tote Bag Handmade,2,6,2.3,10,Acme Textiles,ORDER TODAY,[inventory.csv:2] ...
 *   <blank>
 *   leak,amount_usd,note,evidence
 *   ...,...
 *
 * Real-world mess this parser tolerates:
 *   - UTF-8 BOM (\uFEFF) from Excel on Windows.
 *   - Semicolon delimiter from EU locales (Excel `;`-CSV).
 *   - Quoted fields with commas, embedded newlines, "" escapes.
 *   - Blank lines between sections, trailing newline or not.
 *   - Numbers like "$274.00", "61.7%", "(12.00)", "1 234,56".
 *   - Sellers pasting from Sheets with tab characters.
 *
 * Design: single-pass state machine over the raw string (no regex
 * split on commas — that breaks quoted commas). Delimiter is
 * auto-detected per file (comma vs semicolon vs tab) from the first
 * non-empty lines, then applied consistently.
 */

/**
 * Strip a leading UTF-8 BOM if present.
 *
 * Excel on Windows prepends \uFEFF; if we do not strip it, the first
 * header cell becomes "\uFEFFDAILY CLOSE" and section detection fails.
 *
 * @param {string} text Raw file/paste text.
 * @returns {string} Text without leading BOM.
 * cite: [app.js:csv-bom]
 */
function stripBOM(text) {
  var s = String(text == null ? "" : text);
  if (s.charCodeAt(0) === 0xFEFF) {
    return s.slice(1);
  }
  return s;
}

/**
 * Detect CSV delimiter: comma, semicolon, or tab.
 *
 * Heuristic: look at the first up-to-8 non-empty lines, count
 * occurrences of each candidate *outside quotes*, pick the max.
 * Ties prefer comma (US default), then semicolon, then tab.
 *
 * Why not just comma? EU Excel writes `a;b;c` when the decimal
 * separator is a comma. Sellers paste that verbatim; guessing wrong
 * collapses every row into one column and the KPI table goes empty.
 *
 * @param {string} text CSV text (BOM already stripped ideally).
 * @returns {string} One of ",", ";", "\t".
 * cite: [app.js:csv-delimiter]
 */
function detectDelimiter(text) {
  var s = String(text == null ? "" : text);
  var lines = s.split(/\r\n|\r|\n/).filter(function (ln) {
    return ln.trim() !== "";
  }).slice(0, 8);
  var cands = [",", ";", "\t"];
  var counts = [0, 0, 0];
  for (var i = 0; i < lines.length; i++) {
    var ln = lines[i];
    var inQ = false;
    for (var k = 0; k < ln.length; k++) {
      var ch = ln[k];
      if (ch === '"') {
        // "" inside quotes is an escaped quote, not a toggle.
        if (inQ && ln[k + 1] === '"') {
          k++;
        } else {
          inQ = !inQ;
        }
      } else if (!inQ) {
        if (ch === ",") {
          counts[0]++;
        } else if (ch === ";") {
          counts[1]++;
        } else if (ch === "\t") {
          counts[2]++;
        }
      }
    }
  }
  // Tie-break: comma > semicolon > tab.
  var best = 0;
  if (counts[1] > counts[best]) {
    best = 1;
  }
  if (counts[2] > counts[best]) {
    best = 2;
  }
  return cands[best];
}

/**
 * Parse one CSV row starting at offset `pos`.
 *
 * State machine: inQuotes toggles on `"`, `""` inside quotes emits a
 * literal quote, delimiter outside quotes ends the field, `\n` outside
 * quotes ends the row (`\r\n` and lone `\r` also end rows).
 *
 * @param {string} s Full CSV text.
 * @param {number} pos Start offset.
 * @param {string} delim Delimiter (from detectDelimiter).
 * @returns {{fields: string[], next: number}} Parsed fields + next offset.
 * cite: [app.js:csv-row]
 */
function parseCSVRow(s, pos, delim) {
  var fields = [];
  var cur = "";
  var inQ = false;
  var i = pos;
  // Empty input at end -> single empty row signal handled by caller.
  while (i <= s.length) {
    var ch = i < s.length ? s[i] : "\n"; // sentinel newline flushes last field
    var atEnd = (i >= s.length);
    if (inQ) {
      if (ch === '"') {
        if (s[i + 1] === '"') {
          cur += '"';
          i += 2;
          continue;
        } else {
          inQ = false;
          i++;
          continue;
        }
      } else {
        cur += ch;
        i++;
        if (atEnd) {
          break;
        }
        continue;
      }
    } else {
      if (ch === '"') {
        // Quote only special at field start (after delim) — but be
        // lenient: treat a quote after whitespace at field start as open.
        if (cur === "" || cur.match(/^\s*$/)) {
          // Preserve leading spaces? No — CSV trims nothing; keep it
          // simple: drop pure-whitespace prefix before opening quote.
          if (cur.match(/^\s+$/)) {
            cur = "";
          }
          inQ = true;
          i++;
          continue;
        } else {
          cur += ch;
          i++;
          continue;
        }
      } else if (ch === delim) {
        fields.push(cur);
        cur = "";
        i++;
        continue;
      } else if (ch === "\r" || ch === "\n") {
        fields.push(cur);
        // Consume \r\n as one row break.
        if (ch === "\r" && s[i + 1] === "\n") {
          i += 2;
        } else {
          i += 1;
        }
        break;
      } else {
        cur += ch;
        i++;
        if (atEnd) {
          // Sentinel already pushed? Guard double-push at EOF.
          break;
        }
        continue;
      }
    }
  }
  return { fields: fields, next: i };
}

/**
 * Split full CSV text into rows of fields.
 *
 * Skips nothing: blank rows are returned as [""] so section splitters
 * can use them as boundaries (close.csv uses blank lines between
 * metric / do_today / reorder / leaks sections).
 *
 * @param {string} text Raw CSV text.
 * @param {string} [delimOverride] Force delimiter (auto when omitted).
 * @returns {{rows: string[][], delimiter: string}} Rows + delimiter used.
 * cite: [app.js:csv-split]
 */
function splitCSVRows(text, delimOverride) {
  var s = stripBOM(String(text == null ? "" : text));
  // Normalise lone \r (old Mac Excel) to \n for the state machine.
  s = s.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  var delim = delimOverride || detectDelimiter(s);
  var rows = [];
  var pos = 0;
  // Guard: empty file -> zero rows (not one empty row).
  if (s === "") {
    return { rows: rows, delimiter: delim };
  }
  while (pos < s.length) {
    var r = parseCSVRow(s, pos, delim);
    rows.push(r.fields);
    if (r.next <= pos) {
      break; // safety: never infinite-loop on weird input
    }
    pos = r.next;
  }
  return { rows: rows, delimiter: delim };
}

/**
 * True when a row is blank (zero fields or all-whitespace).
 *
 * @param {string[]} row Parsed row.
 * @returns {boolean}
 * cite: [app.js:csv-blank]
 */
function isBlankRow(row) {
  if (!row || row.length === 0) {
    return true;
  }
  for (var i = 0; i < row.length; i++) {
    if (String(row[i]).trim() !== "") {
      return false;
    }
  }
  return true;
}

/**
 * Parse a close.csv file/paste into a structured bundle.
 *
 * Returns a close-like object compatible with buildPL/renderReport:
 *   { date, headline, kpis:{gmv,fees,shipping,net,cogs,true_profit,
 *     margin_pct,orders,aov,best_seller,money_at_risk_usd},
 *     doToday[], reorder[], leaks[], rawRows, delimiter, citationsFound }
 *
 * Section detection is header-driven (metric/value, do_today_n,
 * product/on_hand, leak/amount_usd) so reordered or partial CSVs still
 * parse. Unknown extra sections are ignored, not fatal.
 *
 * @param {string} text Raw close.csv text.
 * @returns {object} Structured close bundle (never throws).
 * cite: [app.js:parseCloseCSV]
 */
function parseCloseCSV(text) {
  var out = {
    kind: "csv",
    date: "",
    headline: "",
    shop: "",
    kpis: {},
    doToday: [],
    reorder: [],
    leaks: [],
    rawRows: [],
    delimiter: ",",
    citationsFound: 0,
    parseNotes: []
  };
  try {
    var s = stripBOM(String(text == null ? "" : text));
    if (s.trim() === "") {
      out.parseNotes.push("empty input — paste close.csv or press Sample data");
      return out;
    }
    var split = splitCSVRows(s);
    var rows = split.rows;
    out.rawRows = rows;
    out.delimiter = split.delimiter;
    if (rows.length === 0) {
      out.parseNotes.push("no rows parsed (delimiter " + split.delimiter + ")");
      return out;
    }
    // Row 0: DAILY CLOSE,date,headline (best-effort).
    var r0 = rows[0] || [];
    if (String(r0[0] || "").trim().toUpperCase().indexOf("DAILY CLOSE") === 0) {
      out.date = String(r0[1] || "").trim();
      out.headline = String(r0[2] || "").trim();
    } else {
      out.parseNotes.push("first row is not DAILY CLOSE — trying section scan anyway");
    }
    // Walk sections.
    var mode = "none"; // none | metrics | dotoday | reorder | leaks
    var metricMap = {};
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (isBlankRow(row)) {
        continue;
      }
      var cells = row.map(function (c) {
        return String(c == null ? "" : c).trim();
      });
      var head = cells.join("|").toLowerCase();
      // Section headers (accept both comma and semicolon originals).
      if (cells[0].toLowerCase() === "metric" && cells[1].toLowerCase() === "value") {
        mode = "metrics";
        continue;
      }
      if (cells[0].toLowerCase() === "do_today_n" || cells[0].toLowerCase() === "do_today") {
        mode = "dotoday";
        continue;
      }
      if (cells[0].toLowerCase() === "product" && head.indexOf("on_hand") !== -1) {
        mode = "reorder";
        continue;
      }
      if (cells[0].toLowerCase() === "leak" && head.indexOf("amount_usd") !== -1) {
        mode = "leaks";
        continue;
      }
      if (mode === "metrics") {
        // metric,value — but a new section header may appear without
        // blank line; the header checks above already handle that.
        var k = cells[0];
        var v = row.length > 1 ? String(row[1]) : "";
        if (k) {
          metricMap[k] = v;
        }
      } else if (mode === "dotoday") {
        var txt = cells.length >= 2 ? String(row[1]) : cells.join(" ");
        if (txt) {
          out.doToday.push(txt);
        }
      } else if (mode === "reorder") {
        // product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation
        out.reorder.push({
          product: String(row[0] || ""),
          on_hand: String(row[1] || ""),
          sold_7d: String(row[2] || ""),
          days_left: String(row[3] || ""),
          reorder_qty: String(row[4] || ""),
          supplier: String(row[5] || ""),
          urgency: String(row[6] || ""),
          citation: String(row[7] || "")
        });
      } else if (mode === "leaks") {
        // leak,amount_usd,note,evidence
        out.leaks.push({
          leak: String(row[0] || ""),
          amount_usd: String(row[1] || ""),
          note: String(row[2] || ""),
          evidence: String(row[3] || "")
        });
      } else {
        // mode none: ignore stray rows before first section header.
      }
    }
    // Normalise metrics into numeric kpis.
    var bestRaw = metricMap["best_seller"] || "";
    out.kpis = {
      gmv: accNum(metricMap["gmv"], NaN),
      fees: accNum(metricMap["fees"], NaN),
      shipping: accNum(metricMap["shipping"], NaN),
      net: accNum(metricMap["net"], NaN),
      cogs: accNum(metricMap["cogs"], NaN),
      true_profit: accNum(metricMap["true_profit"], NaN),
      margin_pct: accNum(metricMap["margin_pct"], NaN),
      orders: accNum(metricMap["orders"], NaN),
      aov: accNum(metricMap["aov"], NaN),
      money_at_risk_usd: accNum(metricMap["money_at_risk_usd"], 0),
      best_seller: bestRaw,
      _raw: metricMap
    };
    // Count citations anywhere in the file (evidence of audit trail).
    var citeRe = /\[[^\[\]]+\.(csv|txt|py|json):[^\]]+\]/g;
    var m = s.match(citeRe);
    out.citationsFound = m ? m.length : 0;
    if (out.delimiter === ";") {
      out.parseNotes.push("semicolon delimiter detected (EU Excel) — parsed with ';'");
    }
    if (out.delimiter === "\t") {
      out.parseNotes.push("tab delimiter detected (Sheets paste) — parsed with TAB");
    }
    var missing = [];
    ["gmv", "fees", "shipping", "cogs", "true_profit"].forEach(function (k) {
      if (!isFinite(out.kpis[k])) {
        missing.push(k);
      }
    });
    if (missing.length) {
      out.parseNotes.push("missing metrics: " + missing.join(", "));
    }
    return out;
  } catch (e) {
    out.parseNotes.push("parse error: " + e);
    return out;
  }
}

/* ---------------------------------------------------------------------
 * 2. JSON loader — close.json / close-sample.json
 * --------------------------------------------------------------------- */
/*
 * Close.json shape (see seller_close.build_daily_close):
 *   { date, shop, headline, kpis:{gmv,fees,shipping,net,cogs,
 *     true_profit,margin_pct,orders,aov,best_seller,money_at_risk_usd},
 *     do_today[], reorder_sheet[], reply_queue[], money_leaks[],
 *     listing_fixes[], po_draft, citations, free, offline }
 *
 * The loader accepts that shape, the trimmed assets sample, and the
 * CSV-derived bundle above, normalising all three into one internal
 * shape so buildPL/renderReport only handle one format.
 */

/**
 * Parse close.json text (or an already-parsed object).
 *
 * Never throws: on invalid JSON returns { _error } so the UI can show
 * a friendly message instead of a blank page.
 *
 * @param {string|object} input JSON text or object.
 * @returns {object} Normalised close bundle (see parseCloseCSV shape).
 * cite: [app.js:parseCloseJSON]
 */
function parseCloseJSON(input) {
  var obj = null;
  if (input != null && typeof input === "object") {
    obj = input;
  } else {
    var s = stripBOM(String(input == null ? "" : input));
    if (s.trim() === "") {
      return {
        kind: "json", kpis: {}, doToday: [], reorder: [], leaks: [],
        citationsFound: 0, parseNotes: ["empty JSON input"], _error: "empty input"
      };
    }
    try {
      obj = JSON.parse(s);
    } catch (e) {
      return {
        kind: "json", kpis: {}, doToday: [], reorder: [], leaks: [],
        citationsFound: 0, parseNotes: ["invalid JSON: " + e],
        _error: "invalid JSON: " + e
      };
    }
  }
  return normalizeCloseObject(obj);
}

/**
 * Normalise any close-like object to the internal bundle shape.
 *
 * Accepts keys in snake_case (reorder_sheet, do_today, money_leaks)
 * or camelCase (reorder, doToday, leaks) — both are mapped.
 *
 * @param {object} obj Raw close object.
 * @returns {object} Normalised bundle.
 * cite: [app.js:normalizeClose]
 */
function normalizeCloseObject(obj) {
  var out = {
    kind: "json",
    date: "",
    headline: "",
    shop: "",
    kpis: {},
    doToday: [],
    reorder: [],
    leaks: [],
    replies: [],
    listingFixes: [],
    poDraft: "",
    rawRows: [],
    delimiter: ",",
    citationsFound: 0,
    parseNotes: []
  };
  try {
    obj = obj || {};
    out.date = String(obj.date || "");
    out.headline = String(obj.headline || "");
    out.shop = String(obj.shop || "");
    var k = obj.kpis || {};
    var best = k.best_seller || k.bestSeller || "";
    if (best && typeof best === "object") {
      best = (best.product || "") + " x" + (best.qty != null ? best.qty : "?");
    }
    out.kpis = {
      gmv: accNum(k.gmv, NaN),
      fees: accNum(k.fees, NaN),
      shipping: accNum(k.shipping, NaN),
      net: accNum(k.net, NaN),
      cogs: accNum(k.cogs, NaN),
      true_profit: accNum(k.true_profit != null ? k.true_profit : k.trueProfit, NaN),
      margin_pct: accNum(k.margin_pct != null ? k.margin_pct : k.marginPct, NaN),
      orders: accNum(k.orders, NaN),
      aov: accNum(k.aov, NaN),
      money_at_risk_usd: accNum(k.money_at_risk_usd != null ? k.money_at_risk_usd : k.moneyAtRisk, 0),
      best_seller: best,
      _raw: k
    };
    var dt = obj.do_today || obj.doToday || [];
    out.doToday = Array.isArray(dt) ? dt.map(String) : [];
    var rs = obj.reorder_sheet || obj.reorderSheet || obj.reorder || [];
    out.reorder = (Array.isArray(rs) ? rs : []).map(function (r) {
      r = r || {};
      return {
        product: String(r.product || ""),
        on_hand: String(r.on_hand != null ? r.on_hand : (r.onHand || "")),
        sold_7d: String(r.sold_7d != null ? r.sold_7d : (r.sold7d || "")),
        days_left: String(r.days_left != null ? r.days_left : (r.daysLeft || "")),
        reorder_qty: String(r.reorder_qty != null ? r.reorder_qty : (r.reorderQty || "")),
        supplier: String(r.supplier || ""),
        urgency: String(r.urgency || ""),
        citation: String(r.citation || "")
      };
    });
    var ml = obj.money_leaks || obj.moneyLeaks || obj.leaks || [];
    out.leaks = (Array.isArray(ml) ? ml : []).map(function (l) {
      l = l || {};
      return {
        leak: String(l.leak || ""),
        amount_usd: String(l.amount_usd != null ? l.amount_usd : (l.amountUsd || "")),
        note: String(l.note || ""),
        evidence: String(l.evidence || "")
      };
    });
    var rq = obj.reply_queue || obj.replyQueue || obj.replies || [];
    out.replies = (Array.isArray(rq) ? rq : []).map(function (q) {
      q = q || {};
      return {
        channel: String(q.channel || ""),
        customer: String(q.customer || ""),
        summary: String(q.summary || ""),
        draft: String(q.draft || ""),
        citation: String(q.citation || ""),
        priority: String(q.priority || "")
      };
    });
    var lf = obj.listing_fixes || obj.listingFixes || [];
    out.listingFixes = Array.isArray(lf) ? lf : [];
    out.poDraft = String(obj.po_draft != null ? obj.po_draft : (obj.poDraft || ""));
    // Citation census across the whole bundle.
    var blob = "";
    try {
      blob = JSON.stringify(obj);
    } catch (e) {
      blob = String(obj.headline || "") + String(obj.po_draft || "");
    }
    var m = blob.match(/\[[^\[\]]+\.(csv|txt|py|json):[^\]]+\]/g);
    out.citationsFound = m ? m.length : 0;
    // Also count citation fields directly (more precise than regex).
    var fieldCites = 0;
    out.reorder.forEach(function (r) {
      if (r.citation) {
        fieldCites++;
      }
    });
    out.replies.forEach(function (q) {
      if (q.citation) {
        fieldCites++;
      }
    });
    out._fieldCitations = fieldCites;
    return out;
  } catch (e) {
    out.parseNotes.push("normalize error: " + e);
    out._error = String(e);
    return out;
  }
}

/* ---------------------------------------------------------------------
 * 3. P&L calculator + validation + fee benchmarks
 * --------------------------------------------------------------------- */
/*
 * P&L walk identity (the whole page hangs on this):
 *
 *   GMV − fees − shipping − COGS = true profit
 *   margin = profit / GMV · 100
 *   net (after marketplace payout) = GMV − fees − shipping
 *
 * Validation rules (accountant-grade, not dashboard-grade):
 *   V1 profit > GMV is impossible (profit is a subset of GMV).
 *   V2 negative GMV/fees/shipping/COGS are data errors (refunds are
 *      separate rows, not negative GMV).
 *   V3 margin outside [-100%, 100%] is flagged (V1 implies it, but we
 *      check explicitly for a clearer message).
 *   V4 stated profit != recomputed profit beyond $0.01 tolerance.
 *   V5 missing citations flagged (audit trail broken).
 *   V6 fees == 0 with GMV > 0 is suspicious (forgotten fee export?).
 *   V7 shipping == 0 with orders > 0 is suspicious (free-ship leak?).
 *   V8 COGS == 0 with GMV > 0 is suspicious (no supplier costs?).
 */

/**
 * Marketplace fee benchmarks (public rate cards, 2026).
 *
 * Sources (checked Oct 2026; re-verify yearly — rates move):
 *   Shopify:  2.9% + $0.30 online (Basic). In-person 2.7%. Shop Pay same.
 *   Etsy:     6.5% transaction + 3% + $0.25 payment + $0.20 listing.
 *             Effective ~9-10% on a $30 order — we show 6.5%+$0.20 base.
 *   Amazon:   15% referral on most categories (8% floor, up to 45%).
 *   TikTok:   ~5-6% marketplace commission + ~2% payment (US, 2024+).
 *             We show 5% + $0.30 blended for comparison.
 *   eBay:     ~13.25% final value (most categories) + $0.30/order.
 *
 * The table compares the shop's ACTUAL fee rate (fees/GMV) against
 * each benchmark so the accountant can say "you pay X%, Etsy would
 * cost Y% on the same GMV".
 *
 * cite: [app.js:fee-benchmarks]
 */
var FEE_BENCHMARKS = [
  { id: "shopify", name: "Shopify", rate: 0.029, fixed: 0.30, note: "2.9% + $0.30 online (Basic)" },
  { id: "etsy", name: "Etsy", rate: 0.065, fixed: 0.20, note: "6.5% + $0.20 (+3% + $0.25 payment sep.)" },
  { id: "amazon", name: "Amazon", rate: 0.15, fixed: 0.00, note: "15% referral (most categories)" },
  { id: "tiktok", name: "TikTok Shop", rate: 0.05, fixed: 0.30, note: "~5% + $0.30 blended (US)" },
  { id: "ebay", name: "eBay", rate: 0.1325, fixed: 0.30, note: "13.25% + $0.30 final value" }
];

/**
 * Build the P&L walk from a normalised close bundle.
 *
 * Steps (each with amount + bar width % of GMV for div bars):
 *   0 GMV (100%)
 *   1 − fees
 *   2 − shipping
 *   3 − COGS
 *   4 = true profit (recomputed; stated kept for V4 check)
 *
 * @param {object} close Normalised bundle (parseCloseCSV/JSON output).
 * @returns {object} { gmv, fees, shipping, cogs, profit, statedProfit,
 *   marginPct, net, orders, aov, steps[], warnings[], feeActual }
 * cite: [app.js:buildPL]
 */
function buildPL(close) {
  close = close || {};
  var k = close.kpis || {};
  var gmv = accNum(k.gmv, 0);
  var fees = accNum(k.fees, 0);
  var shipping = accNum(k.shipping, 0);
  var cogs = accNum(k.cogs, 0);
  var stated = k.true_profit;
  var statedProfit = isFinite(Number(stated)) ? Number(stated) : NaN;
  var orders = accNum(k.orders, 0);
  var aov = accNum(k.aov, orders > 0 && gmv > 0 ? gmv / orders : 0);
  // Recomputed identity — the source of truth for bars + margin.
  var profit = gmv - fees - shipping - cogs;
  var marginPct = gmv > 0 ? (profit / gmv) * 100 : NaN;
  var net = gmv - fees - shipping;
  var base = gmv > 0 ? gmv : 1; // avoid div-by-zero in widths
  var steps = [
    { id: "gmv", label: "GMV (gross sales)", amount: gmv, kind: "total", widthPct: 100 },
    { id: "fees", label: "− Marketplace fees", amount: -fees, kind: "cost", widthPct: accClamp((fees / base) * 100, 0, 100) },
    { id: "ship", label: "− Shipping paid", amount: -shipping, kind: "cost", widthPct: accClamp((shipping / base) * 100, 0, 100) },
    { id: "cogs", label: "− COGS (supplier cost)", amount: -cogs, kind: "cost", widthPct: accClamp((cogs / base) * 100, 0, 100) },
    { id: "profit", label: "= True profit", amount: profit, kind: profit < 0 ? "loss" : "profit", widthPct: accClamp((Math.max(profit, 0) / base) * 100, 0, 100) }
  ];
  var feeActual = gmv > 0 ? fees / gmv : NaN;
  var warnings = validateClose(close, { gmv: gmv, fees: fees, shipping: shipping, cogs: cogs, profit: profit, marginPct: marginPct, statedProfit: statedProfit, orders: orders });
  return {
    gmv: gmv, fees: fees, shipping: shipping, cogs: cogs,
    profit: profit, statedProfit: statedProfit, marginPct: marginPct,
    net: net, orders: orders, aov: aov, steps: steps,
    warnings: warnings, feeActual: feeActual
  };
}

/**
 * Validate a close bundle. Returns warning objects.
 *
 * Each warning: { code, severity: "error"|"warn"|"info", message }.
 * Errors block sign-off (V1 impossible math). Warns need review.
 * Infos are gentle nudges (suspicious zeros).
 *
 * @param {object} close Normalised bundle.
 * @param {object} [pl] Precomputed numbers (recomputed if omitted).
 * @returns {object[]} Warnings (possibly empty).
 * cite: [app.js:validateClose]
 */
function validateClose(close, pl) {
  var warns = [];
  close = close || {};
  var k = close.kpis || {};
  var gmv = pl ? pl.gmv : accNum(k.gmv, 0);
  var fees = pl ? pl.fees : accNum(k.fees, 0);
  var shipping = pl ? pl.shipping : accNum(k.shipping, 0);
  var cogs = pl ? pl.cogs : accNum(k.cogs, 0);
  var profit = pl ? pl.profit : (gmv - fees - shipping - cogs);
  var marginPct = pl ? pl.marginPct : (gmv > 0 ? (profit / gmv) * 100 : NaN);
  var statedProfit = pl ? pl.statedProfit : accNum(k.true_profit, NaN);
  var orders = pl ? pl.orders : accNum(k.orders, 0);
  // V1 — impossible math (error). Both the recomputed walk and the
  // stated file value are checked: profit is a subset of GMV, so either
  // one exceeding GMV means a sign error or a missing cost row.
  if (isFinite(profit) && isFinite(gmv) && profit > gmv + 1e-9) {
    warns.push({
      code: "V1_PROFIT_GT_GMV",
      severity: "error",
      message: "Impossible: true profit (" + accFmtUSD(profit) + ") exceeds GMV (" + accFmtUSD(gmv) + "). Profit is a subset of GMV — check for a sign error or a missing cost row."
    });
  }
  if (isFinite(statedProfit) && isFinite(gmv) && statedProfit > gmv + 1e-9) {
    warns.push({
      code: "V1_STATED_PROFIT_GT_GMV",
      severity: "error",
      message: "Impossible: stated profit (" + accFmtUSD(statedProfit) + ") exceeds GMV (" + accFmtUSD(gmv) + "). Profit cannot be bigger than gross sales — check the true_profit row."
    });
  }
  // V2 — negatives (error).
  [["GMV", gmv], ["fees", fees], ["shipping", shipping], ["COGS", cogs]].forEach(function (pair) {
    if (isFinite(pair[1]) && pair[1] < -1e-9) {
      warns.push({
        code: "V2_NEGATIVE_" + pair[0].toUpperCase(),
        severity: "error",
        message: "Invalid: " + pair[0] + " is negative (" + accFmtUSD(pair[1]) + "). Refunds belong on separate rows — costs here must be ≥ $0."
      });
    }
  });
  if (isFinite(orders) && orders < 0) {
    warns.push({ code: "V2_NEGATIVE_ORDERS", severity: "error", message: "Invalid: orders is negative (" + orders + ")." });
  }
  // V3 — margin sanity (error when absurd, warn when thin).
  if (isFinite(marginPct) && (marginPct > 100.0001 || marginPct < -100.0001)) {
    warns.push({
      code: "V3_MARGIN_ABSURD",
      severity: "error",
      message: "Impossible margin " + accFmtPct(marginPct) + " (outside ±100%). Recompute: profit/GMV."
    });
  } else if (isFinite(marginPct) && marginPct < 0) {
    warns.push({
      code: "V3_MARGIN_NEGATIVE",
      severity: "warn",
      message: "Negative margin " + accFmtPct(marginPct) + " — the shop lost money on these sales. Check COGS + shipping rows."
    });
  } else if (isFinite(marginPct) && marginPct < 10 && gmv > 0) {
    warns.push({
      code: "V3_MARGIN_THIN",
      severity: "warn",
      message: "Thin margin " + accFmtPct(marginPct) + " (< 10%). Fees + shipping + COGS eat almost all GMV — see leaks."
    });
  }
  // V4 — stated vs recomputed (warn).
  if (isFinite(statedProfit) && isFinite(profit) && Math.abs(statedProfit - profit) > 0.015) {
    warns.push({
      code: "V4_PROFIT_MISMATCH",
      severity: "warn",
      message: "Stated profit " + accFmtUSD(statedProfit) + " ≠ recomputed " + accFmtUSD(profit) + " (GMV−fees−ship−COGS). Trust the recomputed walk; fix the source row."
    });
  }
  // V5 — citations (warn). Missing audit trail != wrong numbers, but
  // the accountant cannot file without it.
  var cites = Number(close.citationsFound || 0);
  if (!cites || cites === 0) {
    warns.push({
      code: "V5_NO_CITATIONS",
      severity: "warn",
      message: "Missing citations: no [file:line] references found. Every number should cite its source (e.g. [shopify_orders.csv:5]). Flagged, not faked."
    });
  }
  // V6/V7/V8 — suspicious zeros (info).
  if (gmv > 0 && !(fees > 0)) {
    warns.push({ code: "V6_ZERO_FEES", severity: "info", message: "Fees are $0 on " + accFmtUSD(gmv) + " GMV — did the fee export get forgotten? Marketplaces always take a cut." });
  }
  if (orders > 0 && !(shipping > 0)) {
    warns.push({ code: "V7_ZERO_SHIPPING", severity: "info", message: "Shipping is $0 on " + orders + " order(s) — free-shipping leak or missing label costs?" });
  }
  if (gmv > 0 && !(cogs > 0)) {
    warns.push({ code: "V8_ZERO_COGS", severity: "info", message: "COGS is $0 on " + accFmtUSD(gmv) + " GMV — no supplier costs recorded? Add inventory/supplier rows." });
  }
  // V9 — parse notes surface here too (info).
  (close.parseNotes || []).forEach(function (n) {
    warns.push({ code: "V9_PARSE_NOTE", severity: "info", message: "Parse note: " + n });
  });
  return warns;
}

/**
 * Compare the shop's actual fee rate against benchmarks.
 *
 * For each marketplace: hypotheticalFee = GMV*rate + orders*fixed,
 * saving = actualFees − hypothetical (negative = shop pays MORE).
 *
 * @param {number} gmv Gross sales.
 * @param {number} actualFees Shop's actual fees.
 * @param {number} orders Order count (for per-order fixed part).
 * @returns {object[]} Rows { id, name, rate, fixed, note, hypo, delta }.
 * cite: [app.js:benchmarkFees]
 */
function benchmarkFees(gmv, actualFees, orders) {
  var g = accNum(gmv, 0);
  var f = accNum(actualFees, 0);
  var o = accNum(orders, 0);
  return FEE_BENCHMARKS.map(function (b) {
    var hypo = g * b.rate + o * b.fixed;
    return {
      id: b.id, name: b.name, rate: b.rate, fixed: b.fixed, note: b.note,
      hypo: hypo, delta: f - hypo
    };
  });
}

/* ---------------------------------------------------------------------
 * 4. Reconciliation checklist store (6 steps, localStorage)
 * --------------------------------------------------------------------- */
/*
 * The 6-step close ritual (accountant sign-off order):
 *   R1 gmv_orders   — GMV ties to orders × AOV (no dropped rows).
 *   R2 fees         — Fees match payout report (marketplace cut).
 *   R3 shipping     — Shipping labels reconciled (no free-ship leak).
 *   R4 cogs         — COGS matches supplier invoices.
 *   R5 citations    — Every number has file:line (audit trail).
 *   R6 export       — Printed / saved CSV+JSON for the file.
 *
 * Persistence: localStorage key `acct_checklist_v1` -> { stepId: true }.
 * Namespaced per close date (`acct_checklist_v1_<date>`) when a date is
 * known, so checking off Oct-10 does not fake Oct-11. Progress renders
 * as "4/6" + a div-width bar (same bar idiom as the P&L walk).
 */

/**
 * The six reconciliation steps (id, title, detail).
 * cite: [app.js:checklist-steps]
 */
var CHECKLIST_STEPS = [
  { id: "gmv_orders", title: "1 · GMV ties to orders", detail: "GMV ≈ orders × AOV. Re-import if a row dropped (profit>GMV flag clears here)." },
  { id: "fees", title: "2 · Fees match payout", detail: "Marketplace payout report agrees with the fees row. Compare vs benchmark table below." },
  { id: "shipping", title: "3 · Shipping reconciled", detail: "Label costs entered; free-shipping promos accounted as a leak, not $0." },
  { id: "cogs", title: "4 · COGS matches invoices", detail: "Supplier invoices / inventory.csv agree with COGS. Note dead-stock cash locked." },
  { id: "citations", title: "5 · Citations complete", detail: "Every number cites [file:line]. Missing citations flagged in warnings — fix at source." },
  { id: "export", title: "6 · Exported + filed", detail: "Print view saved as PDF (or CSV+JSON downloaded) and filed for the accountant." }
];

/**
 * localStorage-backed checklist store.
 *
 * Storage shape: JSON { <stepId>: true }. Unknown ids are ignored on
 * load (forward-compat when steps evolve). All methods no-op safely
 * when localStorage is unavailable (private mode / file:// quirks).
 *
 * cite: [app.js:checklist-store]
 */
var ChecklistStore = {
  KEY: "acct_checklist_v1",
  /**
   * Key for a close date (per-day sign-off isolation).
   * @param {string} [date] Close date YYYY-MM-DD.
   * @returns {string} Storage key.
   */
  keyFor: function (date) {
    var d = String(date || "").trim();
    if (d) {
      return this.KEY + "_" + d.replace(/[^0-9A-Za-z-]/g, "");
    }
    return this.KEY;
  },
  /**
   * Load checked map for a date.
   * @param {string} [date] Close date.
   * @returns {object} { stepId: true } (only known ids).
   */
  load: function (date) {
    var out = {};
    try {
      var raw = localStorage.getItem(this.keyFor(date));
      if (!raw) {
        return out;
      }
      var parsed = JSON.parse(raw);
      CHECKLIST_STEPS.forEach(function (s) {
        if (parsed && parsed[s.id] === true) {
          out[s.id] = true;
        }
      });
    } catch (e) { /* private mode etc — return empty */ }
    return out;
  },
  /**
   * Persist checked map for a date.
   * @param {object} map { stepId: true }.
   * @param {string} [date] Close date.
   */
  save: function (map, date) {
    try {
      var clean = {};
      CHECKLIST_STEPS.forEach(function (s) {
        if (map && map[s.id] === true) {
          clean[s.id] = true;
        }
      });
      localStorage.setItem(this.keyFor(date), JSON.stringify(clean));
    } catch (e) { /* ignore quota/private-mode */ }
  },
  /**
   * Toggle one step and persist.
   * @param {string} id Step id.
   * @param {string} [date] Close date.
   * @returns {object} Updated map.
   */
  toggle: function (id, date) {
    var map = this.load(date);
    if (map[id]) {
      delete map[id];
    } else {
      var known = CHECKLIST_STEPS.some(function (s) {
        return s.id === id;
      });
      if (known) {
        map[id] = true;
      }
    }
    this.save(map, date);
    return map;
  },
  /**
   * Reset all steps for a date.
   * @param {string} [date] Close date.
   */
  reset: function (date) {
    try {
      localStorage.removeItem(this.keyFor(date));
    } catch (e) { /* ignore */ }
  },
  /**
   * Count checked steps.
   * @param {object} map Checked map.
   * @returns {number} 0..6.
   */
  count: function (map) {
    var n = 0;
    CHECKLIST_STEPS.forEach(function (s) {
      if (map && map[s.id] === true) {
        n++;
      }
    });
    return n;
  }
};

/* ---------------------------------------------------------------------
 * 5. Demo data — inline so file:// works with WiFi off
 * --------------------------------------------------------------------- */
/*
 * DEMO_CSV mirrors close_to_csv() for the seed-42 demo shop:
 * GMV $274.00 · fees $16.71 · ship $24.00 · COGS $64.20 ·
 * profit $169.09 (61.7%) · 8 orders · AOV $34.25. Same numbers as
 * web/assets/close-sample.json so both entry points agree.
 *
 * Embedded (not fetched) because fetch() is blocked on file:// and
 * the whole point is offline-capable: double-click index.html and the
 * Sample button still works with WiFi off.
 */

/**
 * Inline demo close.csv (seed 42, shop "our shop", 2026-10-11).
 * cite: [app.js:demo-csv]
 */
var DEMO_CSV = [
  "DAILY CLOSE,2026-10-11,Profit $169.09 (61.7%) \u00B7 $102.75 at risk in 3 angry messages \u00B7 1 reorder(s) TODAY \u00B7 0 leak(s) to plug",
  "",
  "metric,value",
  "gmv,274.0",
  "fees,16.71",
  "shipping,24.0",
  "net,233.29",
  "cogs,64.2",
  "true_profit,169.09",
  "margin_pct,61.7",
  "orders,8",
  "aov,34.25",
  "\"best_seller\",\"{'product': 'Tote Bag Handmade', 'qty': 6, 'gmv': 140.0}\"",
  "money_at_risk_usd,102.75",
  "",
  "do_today_n,do_today",
  "1,\"Reply to 3 message(s) \u2014 $102.75 at risk (drafts below, cite file:line)\"",
  "2,Reorder Tote Bag Handmade x10 from Acme Textiles (2.3d left)",
  "3,No money leaks \u2014 push best seller",
  "",
  "product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation",
  "\"Tote Bag Handmade\",2,6,2.3,10,Acme Textiles,ORDER TODAY,\"[inventory.csv:2] Tote Bag Handmade on_hand=2\"",
  "",
  "leak,amount_usd,note,evidence",
  "\"margin_note\",169.09,\"True margin 61.7% \u2014 profit $169.09 on $274 GMV\",\"[orders] gmv/fees + supplier COGS\""
].join("\n");

/**
 * Inline demo close.json (trimmed bundle, same numbers as DEMO_CSV).
 * cite: [app.js:demo-json]
 */
var DEMO_CLOSE_JSON = {
  date: "2026-10-11",
  shop: "our shop",
  headline: "Profit $169.09 (61.7%) \u00B7 $102.75 at risk in 3 angry messages \u00B7 1 reorder(s) TODAY \u00B7 0 leak(s) to plug",
  kpis: {
    gmv: 274.0, fees: 16.71, shipping: 24.0, net: 233.29, cogs: 64.2,
    true_profit: 169.09, margin_pct: 61.7, orders: 8, aov: 34.25,
    best_seller: { product: "Tote Bag Handmade", qty: 6, gmv: 140.0 },
    money_at_risk_usd: 102.75
  },
  do_today: [
    "Reply to 3 message(s) \u2014 $102.75 at risk (drafts below, cite file:line)",
    "Reorder Tote Bag Handmade x10 from Acme Textiles (2.3d left)",
    "No money leaks \u2014 push best seller"
  ],
  reorder_sheet: [
    {
      product: "Tote Bag Handmade", on_hand: 2, sold_7d: 6,
      daily_velocity: 0.86, days_left: 2.3, reorder_qty: 10,
      cover_days: 14, supplier: "Acme Textiles", urgency: "ORDER TODAY",
      citation: "[inventory.csv:2] Tote Bag Handmade on_hand=2"
    }
  ],
  reply_queue: [
    {
      channel: "dm", customer: "Alice",
      summary: "Alice: Hi! My tote bag hasn't arrived yet, ordered 5 days ago. Worried.",
      draft: "Hi Alice! I'm really sorry about your late delivery \u2014 update within 2 hours.",
      citation: "[instagram_dm.txt:1] Alice: Hi! My tote bag hasn't arrived yet, ordered 5 days",
      priority: "P0-reply-in-2h"
    },
    {
      channel: "dm", customer: "Charlie",
      summary: "Charlie: Where is my order? No tracking.",
      draft: "Hi Charlie! I'm really sorry about your missing tracking \u2014 update within 2 hours.",
      citation: "[instagram_dm.txt:4] Charlie: Where is my order? No tracking.",
      priority: "P0-reply-in-2h"
    },
    {
      channel: "review", customer: "customer",
      summary: "2024-09-11 Ceramic Mug 2 Arrived chipped, very disappointed",
      draft: "Thank you for flagging this \u2014 DM us for a free replacement or refund.",
      citation: "[reviews.csv:3] 2024-09-11 Ceramic Mug 2 Arrived chipped, very disappointed",
      priority: "P0-reply-in-2h"
    }
  ],
  money_leaks: [],
  listing_fixes: [
    { fix: "REVIEW_CRISIS", title: "Bad review \u2014 fix + public reply: Ceramic Mug chipped", evidence: "[reviews.csv:3] 2024-09-11 Ceramic Mug 2 Arrived chipped, very disappointed" }
  ],
  po_draft: "Subject: Reorder request \u2014 Acme Textiles\n\nHi Acme Textiles!\n\nPlease send the following for our shop:\n  - Tote Bag Handmade: 10 units (have 2, 2.3d left) [[inventory.csv:2] Tote Bag Handmade on_hand=2]\n\nPlease confirm price + ETA.\n\nThanks!\nour shop",
  citations: "every number cites [file:line]; audit via /seller/operations",
  free: true,
  offline: true
};

/**
 * Load the inline demo CSV and render (Sample-data button handler).
 *
 * Fills the paste textarea (so sellers see what a real close.csv looks
 * like), parses, builds P&L, renders. Returns the bundle for tests.
 *
 * @returns {object} Normalised demo bundle.
 * cite: [app.js:loadDemoCSV]
 */
function loadDemoCSV() {
  var ta = accById("pasteArea");
  if (ta) {
    ta.value = DEMO_CSV;
  }
  var close = parseCloseCSV(DEMO_CSV);
  var pl = buildPL(close);
  renderReport(close, pl);
  setStatus("Loaded inline demo CSV (seed 42: GMV $274.00 \u00B7 profit $169.09) — offline, no upload.");
  return close;
}

/**
 * Load the inline demo JSON and render.
 *
 * @returns {object} Normalised demo bundle.
 * cite: [app.js:loadDemoJSON]
 */
function loadDemoJSON() {
  var close = parseCloseJSON(DEMO_CLOSE_JSON);
  var pl = buildPL(close);
  renderReport(close, pl);
  setStatus("Loaded inline demo JSON (seed 42) — offline, no upload.");
  return close;
}

/* ---------------------------------------------------------------------
 * 6. Status + summary + print helpers
 * --------------------------------------------------------------------- */

/**
 * Set the status line (aria-live polite for screen readers).
 *
 * @param {string} msg Message.
 * cite: [app.js:status]
 */
function setStatus(msg) {
  try {
    var el = accById("statusLine");
    if (el) {
      el.textContent = String(msg);
    }
  } catch (e) { /* ignore */ }
}

/**
 * Build a plain-text accountant summary (for Copy + print header).
 *
 * One page, copy-pasteable into email/Sheets: headline, P&L walk,
 * fee benchmark verdict, warnings count, checklist progress, PO line.
 *
 * @param {object} close Normalised bundle.
 * @param {object} pl buildPL output.
 * @param {object} [checkMap] Checklist checked map.
 * @returns {string} Summary text.
 * cite: [app.js:copy-summary]
 */
function buildSummaryText(close, pl, checkMap) {
  close = close || {};
  pl = pl || buildPL(close);
  var lines = [];
  lines.push("DAILY CLOSE — ACCOUNTANT SUMMARY");
  lines.push("Date: " + (close.date || "—") + "   Shop: " + (close.shop || "our shop"));
  lines.push("Headline: " + (close.headline || "—"));
  lines.push("");
  lines.push("P&L WALK (GMV − fees − ship − COGS = profit)");
  lines.push("  GMV:      " + accFmtUSD(pl.gmv));
  lines.push("  − fees:   " + accFmtUSD(pl.fees));
  lines.push("  − ship:   " + accFmtUSD(pl.shipping));
  lines.push("  − COGS:   " + accFmtUSD(pl.cogs));
  lines.push("  = profit: " + accFmtUSD(pl.profit) + "  (" + accFmtPct(pl.marginPct) + " margin)");
  lines.push("  net payout (GMV−fees−ship): " + accFmtUSD(pl.net));
  lines.push("  orders: " + pl.orders + "   AOV: " + accFmtUSD(pl.aov));
  lines.push("");
  var warns = pl.warnings || [];
  var errs = warns.filter(function (w) {
    return w.severity === "error";
  }).length;
  lines.push("VALIDATION: " + warns.length + " flag(s), " + errs + " error(s)");
  warns.forEach(function (w) {
    lines.push("  [" + w.severity.toUpperCase() + "/" + w.code + "] " + w.message);
  });
  if (!warns.length) {
    lines.push("  clean — no flags");
  }
  lines.push("");
  lines.push("FEE BENCHMARK (actual " + (isFinite(pl.feeActual) ? (pl.feeActual * 100).toFixed(2) + "%" : "—") + " of GMV)");
  benchmarkFees(pl.gmv, pl.fees, pl.orders).forEach(function (r) {
    lines.push("  " + r.name + " (" + r.note + "): would cost " + accFmtUSD(r.hypo) +
      (r.delta >= 0 ? " — shop SAVES " + accFmtUSD(r.delta) : " — shop PAYS EXTRA " + accFmtUSD(-r.delta)));
  });
  lines.push("");
  var done = ChecklistStore.count(checkMap || {});
  lines.push("RECONCILIATION: " + done + "/6 steps checked");
  CHECKLIST_STEPS.forEach(function (s) {
    var mark = (checkMap && checkMap[s.id]) ? "[x]" : "[ ]";
    lines.push("  " + mark + " " + s.title);
  });
  lines.push("");
  lines.push("CITATIONS: " + (close.citationsFound || 0) + " [file:line] reference(s)" +
    ((close.citationsFound || 0) === 0 ? " — MISSING, flagged above" : ""));
  if (close.poDraft) {
    lines.push("");
    lines.push("PO DRAFT:");
    lines.push(String(close.poDraft).slice(0, 600));
  }
  lines.push("");
  lines.push("Generated offline by Accountant PWA v1.1.0 — paste close.csv/close.json, no upload.");
  return lines.join("\n");
}

/**
 * Copy the current report summary to clipboard.
 *
 * Reads last-rendered bundle from module state (set by renderReport).
 *
 * @returns {Promise<boolean>} True on copy success.
 * cite: [app.js:copySummary]
 */
function copySummary() {
  var st = copySummary._last || null;
  var text;
  if (st && st.close && st.pl) {
    var map = ChecklistStore.load(st.close.date);
    text = buildSummaryText(st.close, st.pl, map);
  } else {
    text = "DAILY CLOSE — ACCOUNTANT SUMMARY\n(no report loaded yet — press Sample data)\n";
  }
  return accCopyText(text).then(function (ok) {
    setStatus(ok ? "Summary copied to clipboard (paste into email/Sheets)." : "Copy blocked — select the summary manually (Ctrl/Cmd+C).");
    return ok;
  });
}

/**
 * Print helper — triggers the @media print view.
 *
 * index.html print CSS hides .no-print (dropzone/buttons/nav) and
 * keeps KPI / P&L / checklist / fee / warnings tables. Before printing
 * we stamp the print date so the paper trail shows when it was filed.
 *
 * cite: [app.js:print-helper]
 */
function printReport() {
  try {
    var el = accById("printStamp");
    if (el) {
      var d = new Date();
      el.textContent = "Printed " + d.toLocaleString() + " — Accountant PWA v1.1.0 (offline)";
    }
  } catch (e) { /* ignore */ }
  try {
    window.print();
    setStatus("Print view opened — save as PDF for the file (Ctrl/Cmd+P).");
  } catch (e) {
    setStatus("Print blocked: " + e);
  }
}

/* ---------------------------------------------------------------------
 * 7. renderReport — KPI table, P&L walk, checklist, fees, warnings
 * --------------------------------------------------------------------- */

/**
 * Module state: last rendered bundle (for copy/print/summary).
 * cite: [app.js:render-state]
 */
var _lastRender = { close: null, pl: null };

/**
 * Master renderer: KPI table + P&L walk + warnings + fee table +
 * checklist + reorder/replies/PO. Idempotent — safe to call twice.
 *
 * Validates first (warnings render even when numbers are partial), so
 * a half-pasted CSV still shows *something* plus clear flags instead
 * of a blank page.
 *
 * @param {object} close Normalised bundle (parseCloseCSV/JSON output).
 * @param {object} [pl] Optional buildPL output (recomputed if omitted).
 * @returns {object} { close, pl } for chaining/tests.
 * cite: [app.js:renderReport]
 */
function renderReport(close, pl) {
  close = close || { kpis: {}, doToday: [], reorder: [], leaks: [] };
  pl = pl || buildPL(close);
  _lastRender = { close: close, pl: pl };
  copySummary._last = { close: close, pl: pl };
  try {
    renderHeadline(close, pl);
    renderKPITable(close, pl);
    renderPLWalk(close, pl);
    renderWarnings(close, pl);
    renderFeeTable(close, pl);
    renderChecklist(close, pl);
    renderDetailTables(close, pl);
    renderExports(close, pl);
  } catch (e) {
    setStatus("Render error: " + e);
  }
  return { close: close, pl: pl };
}

/**
 * Render headline + date + shop + citation count.
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-headline]
 */
function renderHeadline(close, pl) {
  var h = accById("reportHeadline");
  if (h) {
    h.textContent = close.headline || ("Profit " + accFmtUSD(pl.profit) + " (" + accFmtPct(pl.marginPct) + ")");
  }
  var meta = accById("reportMeta");
  if (meta) {
    meta.textContent = "Date " + (close.date || "—") + " · Shop " + (close.shop || "our shop") +
      " · " + (close.citationsFound || 0) + " citation(s) · delimiter '" + (close.delimiter === "\t" ? "TAB" : (close.delimiter || ",")) + "'";
  }
}

/**
 * Render KPI table rows.
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-kpi]
 */
function renderKPITable(close, pl) {
  var tb = accById("kpiBody");
  if (!tb) {
    return;
  }
  var k = close.kpis || {};
  function citeFor(key) {
    // Best-effort source hints (generic close.csv section names).
    var map = {
      gmv: "[orders] gmv", fees: "[orders] fees", shipping: "[orders] shipping",
      cogs: "[inventory.csv] supplier COGS", true_profit: "[orders] gmv/fees + supplier COGS",
      margin_pct: "profit/GMV", orders: "[orders] count", aov: "GMV/orders",
      best_seller: "[orders] best seller", money_at_risk_usd: "[instagram_dm.txt]/[reviews.csv]"
    };
    return map[key] || "";
  }
  var rows = [
    ["GMV", accFmtUSD(pl.gmv), citeFor("gmv")],
    ["Marketplace fees", accFmtUSD(pl.fees) + (isFinite(pl.feeActual) ? " (" + (pl.feeActual * 100).toFixed(2) + "% of GMV)" : ""), citeFor("fees")],
    ["Shipping paid", accFmtUSD(pl.shipping), citeFor("shipping")],
    ["Net payout (GMV−fees−ship)", accFmtUSD(pl.net), "[orders] payout"],
    ["COGS", accFmtUSD(pl.cogs), citeFor("cogs")],
    ["True profit (recomputed)", accFmtUSD(pl.profit), citeFor("true_profit")],
    ["Stated profit (file)", isFinite(pl.statedProfit) ? accFmtUSD(pl.statedProfit) : "—", "close.csv metric true_profit"],
    ["Margin", accFmtPct(pl.marginPct), citeFor("margin_pct")],
    ["Orders", String(pl.orders), citeFor("orders")],
    ["AOV", accFmtUSD(pl.aov), citeFor("aov")],
    ["Best seller", accEsc(String(k.best_seller || "—")), citeFor("best_seller")],
    ["Money at risk", accFmtUSD(accNum(k.money_at_risk_usd, 0)), citeFor("money_at_risk_usd")]
  ];
  tb.innerHTML = rows.map(function (r) {
    return "<tr><td>" + accEsc(r[0]) + "</td><td class=\"num\">" + r[1] + "</td><td class=\"cite\">" + accEsc(r[2]) + "</td></tr>";
  }).join("");
}

/**
 * Render the P&L walk with div-width bars.
 *
 * Bar idiom: each `.bar > span` width is % of GMV (clamped 0..100).
 * Profit bar is green, loss bar red, cost bars amber/grey. Numbers
 * never lie via widths alone — exact $ labels sit next to each bar.
 *
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-plwalk]
 */
function renderPLWalk(close, pl) {
  var wrap = accById("plWalk");
  if (!wrap) {
    return;
  }
  var html = pl.steps.map(function (s) {
    var cls = "bar-total";
    if (s.kind === "cost") {
      cls = "bar-cost";
    } else if (s.kind === "loss") {
      cls = "bar-loss";
    } else if (s.kind === "profit") {
      cls = "bar-profit";
    }
    var w = accClamp(s.widthPct, 0, 100).toFixed(1);
    return "<div class=\"plrow\">" +
      "<div class=\"pllabel\">" + accEsc(s.label) + " <b>" + accFmtUSD(s.amount) + "</b></div>" +
      "<div class=\"bar " + cls + "\"><span style=\"width:" + w + "%\"></span></div>" +
      "<div class=\"plpct\">" + w + "% of GMV</div>" +
      "</div>";
  }).join("");
  // Identity footer: GMV − fees − ship − COGS = profit.
  html += "<div class=\"plidentity\">" + accFmtUSD(pl.gmv) + " − " + accFmtUSD(pl.fees) +
    " − " + accFmtUSD(pl.shipping) + " − " + accFmtUSD(pl.cogs) +
    " = <b>" + accFmtUSD(pl.profit) + "</b> (" + accFmtPct(pl.marginPct) + ")</div>";
  wrap.innerHTML = html;
}

/**
 * Render validation warnings (errors red, warns amber, infos grey).
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-warnings]
 */
function renderWarnings(close, pl) {
  var box = accById("warnBox");
  var count = accById("warnCount");
  if (!box) {
    return;
  }
  var warns = pl.warnings || [];
  if (count) {
    var errs = warns.filter(function (w) {
      return w.severity === "error";
    }).length;
    count.textContent = warns.length === 0 ? "0 flags — clean" : warns.length + " flag(s) · " + errs + " error(s)";
  }
  if (warns.length === 0) {
    box.innerHTML = "<div class=\"warn ok\">Clean — no validation flags. GMV math checks out and citations are present.</div>";
    return;
  }
  box.innerHTML = warns.map(function (w) {
    var cls = w.severity === "error" ? "warn err" : (w.severity === "warn" ? "warn amber" : "warn info");
    return "<div class=\"" + cls + "\"><b>[" + accEsc(w.severity.toUpperCase()) + " · " + accEsc(w.code) + "]</b> " + accEsc(w.message) + "</div>";
  }).join("");
}

/**
 * Render fee-benchmark table (shop actual vs 5 marketplaces).
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-fees]
 */
function renderFeeTable(close, pl) {
  var tb = accById("feeBody");
  if (!tb) {
    return;
  }
  var actual = accNum(pl.fees, 0);
  var rows = benchmarkFees(pl.gmv, pl.fees, pl.orders).map(function (r) {
    var verdict = r.delta >= 0
      ? "<span class=\"save\">saves " + accFmtUSD(r.delta) + "</span>"
      : "<span class=\"extra\">costs extra " + accFmtUSD(-r.delta) + "</span>";
    return "<tr><td>" + accEsc(r.name) + "<div class=\"tiny\">" + accEsc(r.note) + "</div></td>" +
      "<td class=\"num\">" + (r.rate * 100).toFixed(2) + "% + " + accFmtUSD(r.fixed) + "</td>" +
      "<td class=\"num\">" + accFmtUSD(r.hypo) + "</td>" +
      "<td class=\"num\">" + verdict + "</td></tr>";
  }).join("");
  tb.innerHTML = rows;
  var actualEl = accById("feeActual");
  if (actualEl) {
    actualEl.textContent = "Shop actual: " + accFmtUSD(actual) +
      (isFinite(pl.feeActual) ? " (" + (pl.feeActual * 100).toFixed(2) + "% of " + accFmtUSD(pl.gmv) + " GMV on " + pl.orders + " orders)" : "");
  }
}

/**
 * Render the 6-step reconciliation checklist (checkboxes persist).
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-checklist]
 */
function renderChecklist(close, pl) {
  var box = accById("checkList");
  if (!box) {
    return;
  }
  var date = close.date || "";
  var map = ChecklistStore.load(date);
  box.innerHTML = CHECKLIST_STEPS.map(function (s) {
    var checked = map[s.id] ? " checked" : "";
    return "<label class=\"check\"><input type=\"checkbox\" data-step=\"" + accEsc(s.id) + "\"" + checked + ">" +
      "<span><b>" + accEsc(s.title) + "</b><span class=\"tiny\">" + accEsc(s.detail) + "</span></span></label>";
  }).join("");
  // Wire toggles (rebind each render — innerHTML wipes listeners).
  accQueryAll("input[data-step]", box).forEach(function (cb) {
    cb.addEventListener("change", function () {
      var id = cb.getAttribute("data-step");
      var updated = ChecklistStore.toggle(id, date);
      renderCheckProgress(updated);
    });
  });
  renderCheckProgress(map);
}

/**
 * Render checklist progress "n/6" + bar.
 * @param {object} map Checked map.
 * cite: [app.js:render-check-progress]
 */
function renderCheckProgress(map) {
  var n = ChecklistStore.count(map);
  var label = accById("checkProgress");
  if (label) {
    label.textContent = n + "/6 steps checked" + (n === 6 ? " — ready to file" : "");
  }
  var bar = accById("checkBarFill");
  if (bar) {
    bar.style.width = ((n / 6) * 100).toFixed(1) + "%";
  }
}

/**
 * Render reorder / leaks / replies / PO detail tables.
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-details]
 */
function renderDetailTables(close, pl) {
  var rb = accById("reorderBody");
  if (rb) {
    if (!close.reorder || !close.reorder.length) {
      rb.innerHTML = "<tr><td colspan=\"5\" class=\"muted\">No reorder rows — stock healthy or section missing from CSV.</td></tr>";
    } else {
      rb.innerHTML = close.reorder.map(function (r) {
        return "<tr><td>" + accEsc(r.product) + "</td><td class=\"num\">" + accEsc(r.on_hand) +
          "</td><td class=\"num\">" + accEsc(r.days_left) + "d</td><td class=\"num\">" +
          accEsc(r.reorder_qty) + "</td><td class=\"cite\">" + accEsc(r.citation || "— missing") + "</td></tr>";
      }).join("");
    }
  }
  var lb = accById("leakBody");
  if (lb) {
    var leaks = close.leaks || [];
    if (!leaks.length) {
      lb.innerHTML = "<tr><td colspan=\"4\" class=\"muted\">No leaks in this close — push the best seller.</td></tr>";
    } else {
      lb.innerHTML = leaks.map(function (l) {
        return "<tr><td>" + accEsc(l.leak) + "</td><td class=\"num\">" + accEsc(l.amount_usd || "—") +
          "</td><td>" + accEsc(l.note) + "</td><td class=\"cite\">" + accEsc(l.evidence || "— missing") + "</td></tr>";
      }).join("");
    }
  }
  var dt = accById("doTodayList");
  if (dt) {
    var items = close.doToday || [];
    dt.innerHTML = items.length
      ? items.map(function (t, i) {
        return "<div>" + (i + 1) + ". " + accEsc(t) + "</div>";
      }).join("")
      : "<div class=\"muted\">No do-today items parsed.</div>";
  }
  var po = accById("poPre");
  if (po) {
    po.textContent = close.poDraft || "(no PO draft in this bundle — reorder section covers it)";
  }
  var rp = accById("replyList");
  if (rp) {
    var replies = close.replies || [];
    rp.innerHTML = replies.length
      ? replies.map(function (q) {
        return "<div class=\"reply\"><b>" + accEsc(q.priority || "reply") + " · " + accEsc(q.channel) +
          " · " + accEsc(q.customer) + "</b><div class=\"tiny\">" + accEsc(q.summary) +
          "</div><div class=\"tiny cite\">" + accEsc(q.citation || "— missing citation") +
          "</div></div>";
      }).join("")
      : "<div class=\"muted\">No reply queue in this bundle (CSV carries KPIs; JSON carries drafts).</div>";
  }
}

/**
 * Render export-row state (download buttons enabled when data exists).
 * @param {object} close Bundle.
 * @param {object} pl P&L.
 * cite: [app.js:render-exports]
 */
function renderExports(close, pl) {
  var btns = accQueryAll("[data-needs-data]");
  var has = isFinite(pl.gmv) && pl.gmv !== 0;
  btns.forEach(function (b) {
    try {
      b.disabled = !has && !close.headline;
    } catch (e) { /* ignore */ }
  });
}

/* ---------------------------------------------------------------------
 * 8. Input wiring — paste, file upload, JSON, API, boot
 * --------------------------------------------------------------------- */

/**
 * Handle pasted/typed text: auto-detect CSV vs JSON.
 *
 * JSON starts with `{` (after BOM/whitespace); everything else is
 * treated as CSV (close.csv starts with `DAILY CLOSE`). Renders +
 * statuses. Never throws to the button handler.
 *
 * cite: [app.js:handlePaste]
 */
function handlePasteInput() {
  try {
    var ta = accById("pasteArea");
    var raw = ta ? ta.value : "";
    if (!raw || !raw.trim()) {
      setStatus("Paste close.csv or close.json first — or press Sample data.");
      return null;
    }
    var s = stripBOM(raw).trim();
    var close;
    if (s[0] === "{") {
      close = parseCloseJSON(s);
    } else {
      close = parseCloseCSV(raw);
    }
    var pl = buildPL(close);
    renderReport(close, pl);
    // Persist last bundle for the next visit (24h-ish, best-effort).
    try {
      localStorage.setItem("acct_last_close", JSON.stringify({ date: close.date, headline: close.headline, kpis: close.kpis }));
    } catch (e) { /* ignore */ }
    setStatus("Parsed " + (close.kind === "json" ? "JSON" : "CSV") +
      " — GMV " + accFmtUSD(pl.gmv) + ", profit " + accFmtUSD(pl.profit) +
      ", " + (close.citationsFound || 0) + " citation(s), " + pl.warnings.length + " flag(s).");
    return close;
  } catch (e) {
    setStatus("Could not parse input: " + e);
    return null;
  }
}

/**
 * Handle a file upload (close.csv / close.json / .txt paste).
 *
 * Reads via FileReader (UTF-8). Large files (>2MB) warn but still try.
 *
 * @param {File} file Uploaded file.
 * cite: [app.js:handleFile]
 */
function handleFile(file) {
  if (!file) {
    return;
  }
  try {
    if (file.size > 2 * 1024 * 1024) {
      setStatus("Large file (" + Math.round(file.size / 1024) + "KB) — parsing anyway…");
    }
    var rd = new FileReader();
    rd.onload = function () {
      try {
        var text = String(rd.result || "");
        var ta = accById("pasteArea");
        if (ta) {
          ta.value = text.slice(0, 200000); // cap textarea, parse full text
        }
        var name = (file.name || "").toLowerCase();
        var close = (name.slice(-5) === ".json" || stripBOM(text).trim()[0] === "{")
          ? parseCloseJSON(text)
          : parseCloseCSV(text);
        var pl = buildPL(close);
        renderReport(close, pl);
        setStatus("Loaded " + file.name + " (" + Math.round(file.size / 1024) + "KB) — " + (close.citationsFound || 0) + " citation(s).");
      } catch (e) {
        setStatus("Could not read file: " + e);
      }
    };
    rd.onerror = function () {
      setStatus("File read failed — try paste instead.");
    };
    rd.readAsText(file, "utf-8");
  } catch (e) {
    setStatus("Upload failed: " + e);
  }
}

/**
 * Fetch the static sample JSON (http(s) only; file:// falls back).
 *
 * Tries ../assets/close-sample.json then ./assets fallback, then the
 * inline DEMO_CLOSE_JSON. Demonstrates the offline rule: network is
 * best-effort, inline demo is the guarantee.
 *
 * @returns {Promise<object>} Normalised bundle.
 * cite: [app.js:loadSampleJSON]
 */
function loadSampleJSON() {
  var urls = ["../assets/close-sample.json", "web/assets/close-sample.json", "assets/close-sample.json"];
  function tryNext(i) {
    if (i >= urls.length) {
      return Promise.resolve(loadDemoJSON());
    }
    return fetch(urls[i], { cache: "no-store" }).then(function (r) {
      if (!r.ok) {
        throw new Error("HTTP " + r.status);
      }
      return r.json();
    }).then(function (obj) {
      var close = parseCloseJSON(obj);
      var pl = buildPL(close);
      renderReport(close, pl);
      setStatus("Loaded static sample JSON (" + urls[i] + ") — offline fallback is inline demo.");
      return close;
    }).catch(function () {
      return tryNext(i + 1);
    });
  }
  try {
    return tryNext(0);
  } catch (e) {
    return Promise.resolve(loadDemoJSON());
  }
}

/**
 * Run Daily Close demo via same-origin API (progressive enhancement).
 *
 * POST /api/v1/seller/close {demo:true, seed:42}. Fails gracefully
 * offline (file:// or server down) with a fallback to inline demo —
 * old sections keep working without a server either way.
 *
 * cite: [app.js:runCloseAPI]
 */
function runCloseAPI() {
  setStatus("Running Daily Close demo via API (free, local)…");
  var base = "";
  try {
    var q = new URLSearchParams(location.search).get("api");
    base = q || localStorage.getItem("omni_api") || location.origin;
    if (location.protocol === "file:") {
      base = localStorage.getItem("omni_api") || "";
    }
  } catch (e) {
    base = "";
  }
  if (!base) {
    setStatus("No API reachable (file://) — loaded inline demo instead.");
    return Promise.resolve(loadDemoCSV());
  }
  return fetch(base + "/api/v1/seller/close", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ demo: true, seed: 42, shop: "our shop" })
  }).then(function (r) {
    if (!r.ok) {
      throw new Error("HTTP " + r.status);
    }
    return r.json();
  }).then(function (obj) {
    var close = parseCloseJSON(obj);
    var pl = buildPL(close);
    renderReport(close, pl);
    setStatus("Daily Close via API — profit " + accFmtUSD(pl.profit) + " (live bundle, $0).");
    return close;
  }).catch(function (e) {
    setStatus("API failed (" + e + ") — loaded inline demo instead.");
    return loadDemoCSV();
  });
}

/**
 * Download the current close as CSV (re-serialised from bundle).
 * cite: [app.js:downloadCSV]
 */
function downloadCSV() {
  var st = _lastRender;
  if (!st || !st.close) {
    setStatus("Nothing to download — press Sample data first.");
    return false;
  }
  var c = st.close;
  var k = (c.kpis && c.kpis._raw) || c.kpis || {};
  var lines = ["metric,value"];
  ["gmv", "fees", "shipping", "net", "cogs", "true_profit", "margin_pct", "orders", "aov", "money_at_risk_usd"].forEach(function (key) {
    var v = k[key] != null ? k[key] : (c.kpis ? c.kpis[key] : "");
    // Quote when the value contains comma/quote/newline.
    var s = String(v == null ? "" : v);
    if (/[",\n]/.test(s)) {
      s = "\"" + s.replace(/"/g, "\"\"") + "\"";
    }
    lines.push(key + "," + s);
  });
  var ok = accDownload("accountant-close.csv", "DAILY CLOSE," + (c.date || "") + "," + (c.headline || "") + "\n\n" + lines.join("\n") + "\n", "text/csv");
  setStatus(ok ? "Downloaded accountant-close.csv." : "Download blocked — use Copy summary.");
  return ok;
}

/**
 * Wire all buttons/inputs on boot. Idempotent.
 * cite: [app.js:wireUI]
 */
function wireUI() {
  function on(id, ev, fn) {
    try {
      var el = accById(id);
      if (el && !el._acctWired) {
        el.addEventListener(ev, fn);
        el._acctWired = true;
      }
    } catch (e) { /* ignore */ }
  }
  on("parseBtn", "click", handlePasteInput);
  on("sampleCsvBtn", "click", loadDemoCSV);
  on("sampleJsonBtn", "click", loadSampleJSON);
  on("apiBtn", "click", runCloseAPI);
  on("printBtn", "click", printReport);
  on("copyBtn", "click", copySummary);
  on("csvBtn", "click", downloadCSV);
  on("clearBtn", "click", function () {
    var ta = accById("pasteArea");
    if (ta) {
      ta.value = "";
    }
    setStatus("Cleared input — paste a new close.csv/close.json or press Sample data.");
  });
  on("resetCheckBtn", "click", function () {
    var d = (_lastRender.close && _lastRender.close.date) || "";
    ChecklistStore.reset(d);
    renderChecklist(_lastRender.close || { kpis: {} }, _lastRender.pl || buildPL({ kpis: {} }));
    setStatus("Checklist reset for " + (d || "this close") + ".");
  });
  // File input + drag-drop zone.
  try {
    var fi = accById("fileInput");
    if (fi && !fi._acctWired) {
      fi.addEventListener("change", function (e) {
        if (e.target.files && e.target.files[0]) {
          handleFile(e.target.files[0]);
        }
      });
      fi._acctWired = true;
    }
    var dz = accById("dropZone");
    if (dz && !dz._acctWired) {
      ["dragover", "dragenter"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault();
          dz.classList.add("drag");
        });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault();
          dz.classList.remove("drag");
        });
      });
      dz.addEventListener("drop", function (e) {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFile(e.dataTransfer.files[0]);
        }
      });
      dz.addEventListener("click", function () {
        if (fi) {
          fi.click();
        }
      });
      dz._acctWired = true;
    }
  } catch (e) { /* ignore */ }
  // Keyboard: p print, c copy, d demo (when not typing).
  try {
    if (!document._acctKeys) {
      document.addEventListener("keydown", function (e) {
        var t = (e.target && e.target.tagName) || "";
        if (t === "INPUT" || t === "TEXTAREA") {
          return;
        }
        if (e.key === "p") {
          printReport();
        } else if (e.key === "c") {
          copySummary();
        } else if (e.key === "d") {
          loadDemoCSV();
        }
      });
      document._acctKeys = true;
    }
  } catch (e) { /* ignore */ }
  // Restore last close hint (best-effort).
  try {
    var raw = localStorage.getItem("acct_last_close");
    if (raw) {
      var last = JSON.parse(raw);
      if (last && last.headline) {
        setStatus("Welcome back — last close: " + last.headline);
      }
    }
  } catch (e) { /* ignore */ }
}

/* Boot on DOMContentLoaded (script may load in <head>). */
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      wireUI();
      // Auto-load demo when ?demo=1 or when opened with no data (file://).
      try {
        var q = new URLSearchParams(location.search).get("demo");
        if (q === "1") {
          loadDemoCSV();
        }
      } catch (e) { /* ignore */ }
    });
  } else {
    wireUI();
  }
}

/* ---------------------------------------------------------------------
 * 9. Public surface — window.AccountantApp
 * --------------------------------------------------------------------- */

/**
 * Public namespace (smoke-tested). Frozen to prevent accidental
 * override by seller-page scripts when both are open in one tab.
 *
 * Required by spec: parseCloseCSV, buildPL, renderReport.
 * Everything else is bonus surface for index.html + power users.
 *
 * cite: [app.js:AccountantApp]
 */
var AccountantApp = {
  parseCloseCSV: parseCloseCSV,
  parseCloseJSON: parseCloseJSON,
  normalizeCloseObject: normalizeCloseObject,
  buildPL: buildPL,
  validateClose: validateClose,
  benchmarkFees: benchmarkFees,
  renderReport: renderReport,
  copySummary: copySummary,
  buildSummaryText: buildSummaryText,
  printReport: printReport,
  downloadCSV: downloadCSV,
  loadDemoCSV: loadDemoCSV,
  loadDemoJSON: loadDemoJSON,
  loadSampleJSON: loadSampleJSON,
  runCloseAPI: runCloseAPI,
  detectDelimiter: detectDelimiter,
  splitCSVRows: splitCSVRows,
  stripBOM: stripBOM,
  ChecklistStore: ChecklistStore,
  CHECKLIST_STEPS: CHECKLIST_STEPS,
  FEE_BENCHMARKS: FEE_BENCHMARKS,
  DEMO_CSV: DEMO_CSV,
  DEMO_CLOSE_JSON: DEMO_CLOSE_JSON,
  VERSION: "1.1.0"
};

try {
  if (typeof window !== "undefined") {
    window.AccountantApp = AccountantApp;
  }
} catch (e) { /* non-browser (tests) — ignore */ }

try {
  if (typeof module !== "undefined" && module.exports) {
    module.exports = AccountantApp;
  }
} catch (e) { /* browser — ignore */ }

/* =====================================================================
 * APPENDIX A — CSV edge-case catalogue (why the parser looks paranoid)
 * ---------------------------------------------------------------------
 * A01 BOM: Excel Windows writes EF BB BF. Stripped in stripBOM().
 * A02 Semicolons: de-DE/fr-FR Excel uses `;` when decimal is `,`.
 * A03 Tabs: Sheets copy-paste yields tab-separated rows.
 * A04 Quoted commas: `"Tote, Large",2,6` must stay one field.
 * A05 Escaped quotes: `"say ""hi""",2` -> `say "hi"`.
 * A06 Embedded newlines: `"line1\nline2",2` stays one field.
 * A07 Blank separator lines between close.csv sections.
 * A08 Trailing newline present or not — both parse.
 * A09 Lone \r (old Mac Excel) normalised to \n.
 * A10 Numbers with $, %, commas, spaces: `$1,234.56` -> 1234.56.
 * A11 Parenthesised negatives: `($12.00)` -> -12 (accounting style).
 * A12 First row `DAILY CLOSE,date,headline` may contain commas inside
 *     the headline — quoted by close_to_csv, parsed by state machine.
 * A13 best_seller serialises a Python dict with commas — quoted field.
 * A14 do_today rows contain em-dashes and $ — quoted fields.
 * A15 reorder citation contains brackets/commas — quoted field.
 * A16 Duplicate metric keys: last wins (metricMap overwrite).
 * A17 Unknown sections ignored (forward-compat with new close parts).
 * A18 Missing sections yield parseNotes, not exceptions.
 * A19 Empty paste yields a friendly note, not a blank page.
 * A20 2MB+ uploads warn but still parse (FileReader streaming not
 *     needed at seller scale; closes are KBs).
 * ===================================================================== */

/* =====================================================================
 * APPENDIX B — P&L identity worked example (seed 42)
 * ---------------------------------------------------------------------
 * GMV         $274.00  (8 orders x $34.25 AOV)
 * − fees       $16.71  (6.10% of GMV — below Etsy 6.5% base)
 * − shipping   $24.00  ($3.00/order avg)
 * − COGS       $64.20  (supplier cost, inventory.csv)
 * = profit    $169.09  (61.7% margin)
 * net payout  $233.29  (GMV − fees − ship; before COGS)
 * Bar widths (% of GMV): GMV 100 · fees 6.1 · ship 8.8 · COGS 23.4 ·
 * profit 61.7. Widths clamp to [0,100] so V1 errors cannot break CSS.
 * ===================================================================== */

/* =====================================================================
 * APPENDIX C — fee-benchmark reading guide (for the accountant)
 * ---------------------------------------------------------------------
 * C1 Actual rate = fees / GMV. Demo: 16.71/274 = 6.10%.
 * C2 Shopify hypo = GMV*2.9% + orders*$0.30 = 274*.029+8*.30 = $10.35.
 *    Demo shop SAVES vs Shopify? No: actual $16.71 > $10.35, so the
 *    shop PAYS EXTRA $6.36 vs Shopify — flag fee creep.
 * C3 Etsy hypo = GMV*6.5% + orders*$0.20 = 274*.065+8*.20 = $19.41.
 *    Demo shop SAVES $2.70 vs Etsy base (before Etsy's extra 3%+$0.25
 *    payment fee — real Etsy cost is higher; note says so).
 * C4 Amazon hypo = GMV*15% = $41.10. Shop SAVES $24.39 vs Amazon.
 * C5 TikTok hypo = GMV*5% + orders*$0.30 = $16.10. Roughly at parity.
 * C6 eBay hypo = GMV*13.25% + orders*$0.30 = $38.71. Shop SAVES big.
 * C7 Verdict language: "saves" (green) vs "costs extra" (red) uses
 *    delta = actual − hypo, rounded to cents, never bare % without $.
 * ===================================================================== */

/* =====================================================================
 * APPENDIX D — reconciliation SOP (the 6 steps in plain English)
 * ---------------------------------------------------------------------
 * D1 GMV ties to orders: open shopify_orders.csv, count rows, multiply
 *    by average price. If GMV < orders*AOV*0.9, a row dropped.
 * D2 Fees match payout: marketplace payout email/CSV vs fees row. A
 *    mismatch > $1 means a missing refund-fee or currency row.
 * D3 Shipping reconciled: pirate-ship/stamps export vs shipping row.
 *    Free-shipping promos are a marketing cost — book them, not $0.
 * D4 COGS matches invoices: supplier invoice photo (Vision OCR) vs
 *    COGS row. Dead stock is cash locked, not a loss — note it.
 * D5 Citations complete: ctrl-F "[" — every KPI row needs file:line.
 *    No citation = cannot file; send back to the seller.
 * D6 Exported + filed: print view -> PDF, name `close-YYYY-MM-DD.pdf`,
 *    attach close.csv + close.json, email/file. Check the box.
 * ===================================================================== */

/* =====================================================================
 * APPENDIX E — validation catalogue (codes rendered in warnBox)
 * ---------------------------------------------------------------------
 * E-V1 PROFIT_GT_GMV (error): profit subset of GMV. Fix sign error.
 * E-V2 NEGATIVE_* (error): costs ≥ 0. Refunds are separate rows.
 * E-V3 MARGIN_ABSURD (error): |margin| > 100%. Recompute profit/GMV.
 * E-V3 MARGIN_NEGATIVE (warn): loss-making sales. Check ship+COGS.
 * E-V3 MARGIN_THIN (warn): < 10%. See leaks table.
 * E-V4 PROFIT_MISMATCH (warn): stated ≠ recomputed > $0.015. Trust walk.
 * E-V5 NO_CITATIONS (warn): zero [file:line]. Cannot file without it.
 * E-V6 ZERO_FEES (info): $0 fees on GMV>0. Forgot fee export?
 * E-V7 ZERO_SHIPPING (info): $0 ship on orders>0. Free-ship leak?
 * E-V8 ZERO_COGS (info): $0 COGS on GMV>0. Missing supplier rows?
 * E-V9 PARSE_NOTE (info): delimiter/section notes from the parser.
 * ===================================================================== */

/* =====================================================================
 * APPENDIX F — offline + print + keyboard contract
 * ---------------------------------------------------------------------
 * F1 No CDN: grep `<script src="http` must return nothing in
 *    index.html; grep `from "http` must return nothing here.
 * F2 file:// support: Sample CSV/JSON buttons use inline constants;
 *    fetch() paths are try/catch with inline fallback.
 * F3 localStorage keys: acct_checklist_v1[_<date>], acct_last_close,
 *    omni_api (shared with seller/close pages for API override).
 * F4 Print: @media print in index.html hides .no-print; printReport()
 *    stamps #printStamp with locale datetime before window.print().
 * F5 Keyboard: p print · c copy summary · d load demo (not in inputs).
 * F6 Screen readers: #statusLine is aria-live polite; bars have % text
 *    siblings so information is not colour-only.
 * ===================================================================== */
