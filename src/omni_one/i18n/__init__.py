"""i18n package for Omni-One seller replies.

Supported locales: en, es, zh, fr, de.
Deterministic, no network, no LLM calls.

Public API:
  SUPPORTED: list of locale codes
  list_locales() -> list[str]
  detect_locale(text) -> locale code
  t(key, locale, **vars) -> localized string with en fallback
  get_locale_module(locale) -> module
"""

from __future__ import annotations

import re

SUPPORTED = ["en", "es", "zh", "fr", "de"]

# ---------------------------------------------------------------------------
# Lazy locale module registry
# ---------------------------------------------------------------------------

_LOCALE_MODULES: dict = {}


def get_locale_module(locale: str):
    """Return the locale module for ``locale`` (fallback to en)."""
    loc = (locale or "en").strip().lower()
    if loc not in SUPPORTED:
        loc = "en"
    if loc in _LOCALE_MODULES:
        return _LOCALE_MODULES[loc]
    # Local imports to avoid circularity; package lives in same dir.
    if loc == "en":
        from . import en as mod
    elif loc == "es":
        from . import es as mod
    elif loc == "zh":
        from . import zh as mod
    elif loc == "fr":
        from . import fr as mod
    elif loc == "de":
        from . import de as mod
    else:  # pragma: no cover - defensive
        from . import en as mod
    _LOCALE_MODULES[loc] = mod
    return mod


def list_locales() -> list:
    """Return supported locale codes in canonical order."""
    return list(SUPPORTED)


# ---------------------------------------------------------------------------
# detect_locale
# ---------------------------------------------------------------------------

# CJK Unified Ideographs + extensions + compat + hiragana/katakana.
# Hiragana/katakana are Japanese, but for this seller pack any CJK-heavy
# text is treated as zh (no ja locale supported). This is documented.
_CJK_RE = re.compile(
    "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    "\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)

_ES_KEYWORDS = [
    "hola",
    "gracias",
    "por favor",
    "pedido",
    "env\u00edo",
    "envio",
    "reembolso",
    "roto",
    "rota",
    "rotos",
    "tarde",
    "problema",
    "ayuda",
    "devoluci\u00f3n",
    "devolucion",
    "lleg\u00f3",
    "llego",
    "d\u00f3nde",
    "donde",
    "cu\u00e1ndo",
    "horas",
    "tienda",
    "disculpa",
    "retraso",
    "da\u00f1ado",
]

_FR_KEYWORDS = [
    "bonjour",
    "merci",
    "commande",
    "livraison",
    "remboursement",
    "cass\u00e9",
    "casse",
    "retard",
    "probl\u00e8me",
    "probleme",
    "aide",
    "retour",
    "arriv\u00e9",
    "arrive",
    "o\u00f9",
    "heures",
    "boutique",
    "d\u00e9sol\u00e9",
    "desole",
    "svp",
    "s'il vous pla\u00eet",
]

_DE_KEYWORDS = [
    "hallo",
    "danke",
    "bitte",
    "bestellung",
    "lieferung",
    "erstattung",
    "kaputt",
    "versp\u00e4tet",
    "verspaetet",
    "hilfe",
    "r\u00fccksendung",
    "ruecksendung",
    "angekommen",
    "stunden",
    "gesch\u00e4ft",
    "geschaeft",
    "entschuldigung",
    "sendung",
    "reklamation",
    "beschwerde",
]

# Unique accent chars (é shared es/fr is intentionally excluded here;
# shared accents do not discriminate, keywords do).
_ES_UNIQUE_ACCENTS = set("\u00f1\u00bf\u00a1\u00e1\u00ed\u00f3\u00fa\u00fc")
_FR_UNIQUE_ACCENTS = set("\u00e0\u00e2\u00e7\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u00ff\u0153\u00e6")
_DE_UNIQUE_ACCENTS = set("\u00e4\u00f6\u00fc\u00df")


def _count_keyword_hits(text_lower: str, keywords: list) -> int:
    hits = 0
    for kw in keywords:
        kw_l = kw.lower()
        # Phrases / apostrophe forms: substring match.
        if " " in kw_l or "'" in kw_l:
            if kw_l in text_lower:
                hits += 1
        else:
            # Word-boundary match for single tokens (avoids 'wo' in 'where').
            if re.search(r"(?<!\w)" + re.escape(kw_l) + r"(?!\w)", text_lower):
                hits += 1
    return hits


def _count_unique_accents(text_lower: str, charset: set) -> int:
    return sum(1 for ch in text_lower if ch in charset)


def detect_locale(text) -> str:
    """Detect locale for ``text``.

    Heuristics (deterministic, no network):
      1. CJK ratio -> zh. Any text with >=3 CJK chars, or CJK ratio > 3%,
         is zh. CJK chars are essentially absent from en/es/fr/de fixtures.
      2. Accent + keyword scoring for es/fr/de. Each scores
         ``3 * keyword_hits + 2 * unique_accent_count``. If the best score
         is > 0, return that locale.
      3. Default en.

    Empty / None / non-string input defaults to en.
    """
    if not isinstance(text, str) or not text.strip():
        return "en"
    lowered = text.lower()
    cjk_chars = _CJK_RE.findall(text)
    n_cjk = len(cjk_chars)
    if n_cjk >= 3:
        return "zh"
    if n_cjk >= 1 and (n_cjk / max(1, len(text))) > 0.03:
        return "zh"
    # Single CJK char in a longer mixed string still signals zh if the
    # surrounding text is short; otherwise fall through to keyword check
    # but keep zh bias for any CJK presence with Asian punctuation.
    if n_cjk >= 1:
        if any(c in text for c in ("\u3002", "\uff0c", "\u8bf7", "\u8c22", "\u60a8", "\u6211")):
            return "zh"

    es_kw = _count_keyword_hits(lowered, _ES_KEYWORDS)
    fr_kw = _count_keyword_hits(lowered, _FR_KEYWORDS)
    de_kw = _count_keyword_hits(lowered, _DE_KEYWORDS)
    es_ac = _count_unique_accents(lowered, _ES_UNIQUE_ACCENTS)
    fr_ac = _count_unique_accents(lowered, _FR_UNIQUE_ACCENTS)
    de_ac = _count_unique_accents(lowered, _DE_UNIQUE_ACCENTS)

    es_score = 3 * es_kw + 2 * es_ac
    fr_score = 3 * fr_kw + 2 * fr_ac
    de_score = 3 * de_kw + 2 * de_ac

    best = max(es_score, fr_score, de_score)
    if best <= 0:
        return "en"
    # Deterministic tie-break: es > fr > de is arbitrary but fixed.
    # Ties should not occur in curated fixtures; this keeps behaviour stable.
    if es_score == best and (es_score > fr_score or es_score > de_score or (es_score == fr_score == best and es_kw >= fr_kw)):
        # Need explicit tie handling below for full determinism.
        pass
    scores = {"es": es_score, "fr": fr_score, "de": de_score}
    # Sort by (-score, canonical order es, fr, de) for determinism.
    order = {"es": 0, "fr": 1, "de": 2}
    winner = sorted(scores.items(), key=lambda kv: (-kv[1], order[kv[0]]))[0][0]
    return winner


# ---------------------------------------------------------------------------
# t(key, locale, **vars)
# ---------------------------------------------------------------------------

def t(key: str, locale: str = "en", **vars) -> str:
    """Translate ``key`` for ``locale`` with English fallback.

    Lookup order:
      1. ``STRINGS[key]`` in the locale module, formatted with ``vars``.
      2. Module attribute ``key`` / ``key.upper()`` if it is a string template.
      3. Same lookups in the ``en`` module (fallback).
    Raises KeyError if the key exists nowhere.
    """
    loc = (locale or "en").strip().lower()
    if loc not in SUPPORTED:
        loc = "en"
    mod = get_locale_module(loc)
    en_mod = get_locale_module("en")

    template = None
    if hasattr(mod, "STRINGS"):
        try:
            strings = getattr(mod, "STRINGS")
            if isinstance(strings, dict) and key in strings:
                template = strings[key]
        except Exception:
            template = None
    if template is None:
        if hasattr(mod, key) and isinstance(getattr(mod, key), str):
            template = getattr(mod, key)
        elif hasattr(mod, key.upper()) and isinstance(getattr(mod, key.upper()), str):
            template = getattr(mod, key.upper())

    if template is None:
        # English fallback.
        if hasattr(en_mod, "STRINGS"):
            try:
                strings = getattr(en_mod, "STRINGS")
                if isinstance(strings, dict) and key in strings:
                    template = strings[key]
            except Exception:
                template = None
        if template is None:
            if hasattr(en_mod, key) and isinstance(getattr(en_mod, key), str):
                template = getattr(en_mod, key)
            elif hasattr(en_mod, key.upper()) and isinstance(getattr(en_mod, key.upper()), str):
                template = getattr(en_mod, key.upper())
    if template is None:
        raise KeyError(f"i18n key not found: {key!r}")
    if callable(template) and not isinstance(template, str):
        # String constants are the norm; callables are invoked with vars.
        try:
            return template(**vars)
        except TypeError:
            return template()
    if isinstance(template, str):
        try:
            return template.format(**vars) if vars else template
        except KeyError:
            # Missing placeholder vars: return raw template rather than crash.
            return template
    return str(template)


__all__ = ["SUPPORTED", "list_locales", "detect_locale", "t", "get_locale_module"]
