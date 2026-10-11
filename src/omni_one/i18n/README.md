# i18n — reply drafts in the customer's language

`from omni_one.i18n import detect_locale, list_locales`
`from omni_one.i18n.drafts import build_reply, build_po`

Locales: `en es zh fr de` (`src/omni_one/i18n/<locale>.py`). Every template carries the
`{citation}` (`[file:line]`) — no invented order numbers. `detect_locale` uses CJK ratio
+ accent/keyword heuristics (100% on fixtures). `channels.normalize_dm` handles
instagram/tiktok/etsy/amazon/whatsapp/email shapes; `parse_review_row` normalizes
1-5/★/"one star". Golden: ES draft promises "2 horas", ZH draft is CJK + citation.
