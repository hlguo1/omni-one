"""Chinese (zh) locale module for Omni-One i18n seller replies.

\u57fa\u7840\u56de\u590d\u6a21\u677f\uff1a\u6bcf\u4e2a\u6a21\u677f\u90fd\u5305\u542b ``{citation}`` \u5360\u4f4d\u7b26\uff0c
\u8c03\u7528\u8005\u5fc5\u987b\u586b\u5199\u771f\u5b9e\u6765\u6e90\u6587\u4ef6\u540d\uff08\u4f8b\u5982 ``reviews.csv``
\u6216 ``tiktok_dm.json``\uff09\u3002\u4e0d\u865a\u6784\u8ba2\u5355\u53f7\uff1b\u8349\u7a3f\u4e2d\u6c38\u8fdc
\u4e0d\u5305\u542b ``#123`` \u7c7b\u6807\u8bc6\u7b26\u3002\u6240\u6709\u51fd\u6570\u662f\u786e\u5b9a\u6027\u7684\u3002

Exports:
  LOCALE, LANGUAGE_NAME, FORMALITY,
  COMPLAINT_PHRASES (15+), NEGATIVE_WORDS (20+), ISSUE_LABELS,
  DM_REPLY_TEMPLATE, REVIEW_REPLY_TEMPLATE, PO_EMAIL_TEMPLATE,
  COVER_NOTE_14D_TEMPLATE, STRINGS,
  DM_REPLY(customer, issue, citation, shop),
  REVIEW_REPLY(product, citation, shop),
  PO_EMAIL(supplier, lines, shop, citation),
  cover_note_14d(shop, citation),
  is_complaint(text), is_negative(text), get_issue_label(text),
  format_po_lines(lines), greeting(customer), closing(shop)
"""

from __future__ import annotations

LOCALE = "zh"
LANGUAGE_NAME = "\u4e2d\u6587"

# ---------------------------------------------------------------------------
# \u6b63\u5f0f\u6ce8\u610f\u4e8b\u9879
# ---------------------------------------------------------------------------
# \u4e2d\u6587\u5356\u5bb6\u8bed\u6c14\uff1a\u793c\u8c8c\u3001\u7b80\u6d01\u3001\u4e13\u4e1a\u3002
# \u4e0b\u9762\u6a21\u677f\u4e2d\u7f16\u7801\u7684\u6307\u5357\uff1a
FORMALITY = """\u4e2d\u6587\u6b63\u5f0f\u8bf4\u660e\uff08\u5356\u5bb6\u8bed\u6c14\uff09\uff1a
- \u5df2\u77e5\u59d3\u540d\u65f6\u7528\u59d3\u540d\u79f0\u547c\uff1a\u201c\u60a8\u597d {customer}\uff0c\u201d\u3002
- \u4fdd\u6301\u6e29\u548c\u4e13\u4e1a\u7684\u5e02\u573a\u8bed\u6c14\uff1b\u4e0d\u7528\u4fd7\u8bed\uff0c\u4e0d\u7528\u5168\u5927\u5199\u3002
- \u7b80\u77ed\u9053\u6b49\u4e00\u6b21\uff0c\u4e0d\u627f\u8ba4\u6cd5\u5f8b\u8d23\u4efb\u3002
- \u627f\u8bfa\u5177\u4f53\u56de\u590d\u65f6\u95f4\uff1a\u201c2\u5c0f\u65f6\u5185\u201d\u3002
- \u59cb\u7ec8\u7528\u6765\u6e90\u6587\u4ef6\u5f15\u7528\u652f\u6491\u56de\u590d\u3002
- \u6c38\u8fdc\u4e0d\u865a\u6784\u8ba2\u5355\u53f7\u3001\u7269\u6d41\u5355\u53f7\u6216\u9000\u6b3e\u5355\u53f7\u3002
- \u7ed3\u5c3e\u5199\u660e\u5e97\u94fa\u540d\uff0c\u8ba9\u4e70\u5bb6\u77e5\u9053\u662f\u8c01\u5728\u56de\u590d\u3002
- \u5bf9\u4e8e\u8bc4\u4ef7\uff0c\u5373\u4f7f\u662f\u5dee\u8bc4\u4e5f\u8981\u8868\u793a\u611f\u8c22\u3002
- \u91c7\u8d2d\u90ae\u4ef6\u4f7f\u7528\u6e05\u6670\u7684\u4e3b\u9898\u884c\u548c\u9879\u76ee\u5217\u8868\u3002
- \u8986\u76d6\u8bf4\u660e\u660e\u786e\u5199\u51fa 14 \u5929\uff08\u201c\u63a5\u4e0b\u6765 14 \u5929\u201d\uff09\u3002
- \u4f7f\u7528\u7b80\u5355\u53e5\u5b50\uff1b\u907f\u514d\u673a\u5668\u7ffb\u8bd1\u5bb9\u6613\u51fa\u9519\u7684\u6210\u8bed\u3002
- \u91c7\u8d2d\u90ae\u4ef6\u4e2d\u4e0d\u7528\u8868\u60c5\u7b26\u53f7\uff1bDM \u4e2d\u6700\u591a\u4e00\u4e2a\u611f\u53f9\u53f7\u3002
- DM \u56de\u590d\u63a7\u5236\u5728\u7ea6 120 \u5b57\u4ee5\u5185\uff0c\u65b9\u4fbf\u590d\u5236\u7c98\u8d34\u3002
- \u8bc4\u4ef7\u56de\u590d\u63a7\u5236\u5728\u7ea6 80 \u5b57\u4ee5\u5185\uff0c\u65b9\u4fbf\u5e02\u573a\u53d1\u5e03\u3002
- \u6570\u5b57\u4fdd\u7559\u201c2\u5c0f\u65f6\u201d\u3001\u201c14\u5929\u201d\u7684\u7ea6\u5b9a\u8868\u8ff0\u3002
- \u53ea\u6709\u6e90\u6570\u636e\u660e\u786e\u91d1\u989d\u65f6\u624d\u63d0\u91d1\u989d\u3002
- \u5982\u679c\u95ee\u9898\u4e0d\u660e\uff0c\u53ea\u95ee\u4e00\u4e2a\u660e\u786e\u95ee\u9898\uff0c\u4e0d\u95ee\u4e09\u4e2a\u3002
- \u4e0d\u627f\u8bfa\u5177\u4f53\u9000\u6b3e\u91d1\u989d\uff1b\u8868\u793a\u201c\u9000\u6b3e\u6216\u8865\u53d1\u201d\u3002
- \u7f72\u540d\u7528\u5e97\u94fa\u540d\uff0c\u4e0d\u7528\u4e2a\u4eba\u59d3\u540d\uff0c\u65b9\u4fbf\u56e2\u961f\u4f7f\u7528\u3002
- \u65f6\u95f4\u6233\u548c\u53d1\u4ef6\u4eba\u6765\u81ea\u6e20\u9053\u89e3\u6790\uff0c\u4e0d\u53ef\u865a\u6784\u3002
- \u4f7f\u7528\u201c\u60a8\u201d\u4fdd\u6301\u793c\u8c8c\uff0c\u4e0d\u7528\u968f\u610f\u7684\u201c\u4f60\u201d\u3002
- \u907f\u514d\u4e0d\u5fc5\u8981\u7684\u82f1\u6587\u5916\u6765\u8bcd\uff1b\u7528\u201c\u8ba2\u5355\u201d\u800c\u4e0d\u662f order\u3002
"""

# ---------------------------------------------------------------------------
# \u6295\u8bc9\u77ed\u8bed\uff0815+\uff09\uff1a\u4e70\u5bb6\u4e0d\u6ee1\u65f6\u7684\u5e38\u7528\u8868\u8ff0\u3002
# is_complaint() \u4e0d\u533a\u5206\u5927\u5c0f\u5199\u8fdb\u884c\u5b50\u4e32\u5339\u914d\u3002
# ---------------------------------------------------------------------------

COMPLAINT_PHRASES = [
    "\u6211\u7684\u8ba2\u5355\u5ef6\u8fdf\u4e86",  # \u5ef6\u8fdf
    "\u5feb\u9012\u592a\u6162\u4e86",  # \u6162
    "\u5230\u8d27\u65f6\u574f\u4e86",  # \u635f\u574f
    "\u6536\u5230\u65f6\u5df2\u7ecf\u635f\u574f",  # \u635f\u574f\u53d8\u4f53
    "\u53d1\u9519\u8d27\u4e86",  # \u53d1\u9519
    "\u6536\u5230\u7684\u5546\u54c1\u4e0d\u5bf9",  # \u9519\u8bef\u5546\u54c1
    "\u7f3a\u5c11\u4e00\u4e2a\u914d\u4ef6",  # \u7f3a\u5c11
    "\u5305\u88f9\u4ece\u672a\u5230\u8fbe",  # \u4e22\u5931
    "\u6211\u8981\u9000\u6b3e",  # \u9000\u6b3e\u8bf7\u6c42
    "\u8bf7\u7ed9\u6211\u9000\u6b3e",  # \u9000\u6b3e\u53d8\u4f53
    "\u8fd9\u4e0d\u53ef\u63a5\u53d7",  # \u5f3a\u70c8\u4e0d\u6ee1
    "\u975e\u5e38\u5931\u671b",  # \u5931\u671b
    "\u8d28\u91cf\u592a\u5dee",  # \u8d28\u91cf\u6295\u8bc9
    "\u4e0e\u63cf\u8ff0\u4e0d\u7b26",  # \u4e0e\u5217\u8868\u4e0d\u7b26
    "\u6211\u8981\u9000\u8d27",  # \u9000\u8d27\u8bf7\u6c42
    "\u4e00\u76f4\u6ca1\u6709\u6536\u5230",  # \u7b49\u5f85
    "\u8bf7\u5e2e\u6211\u89e3\u51b3\u8fd9\u4e2a\u95ee\u9898",  # \u5e2e\u52a9\u8bf7\u6c42
    "\u4ea7\u54c1\u65e0\u6cd5\u4f7f\u7528",  # \u6709\u7f3a\u9677
]

# ---------------------------------------------------------------------------
# \u8d1f\u9762\u8bcd\uff0820+\uff09\uff1a\u8868\u793a\u4e0d\u6ee1\u7684\u5355\u8bcd\u3002
# ---------------------------------------------------------------------------

NEGATIVE_WORDS = [
    "\u5ef6\u8fdf",  # \u5ef6\u8fdf
    "\u592a\u6162",  # \u6162
    "\u574f\u4e86",  # \u635f\u574f
    "\u635f\u574f",  # \u635f\u574f
    "\u7834\u635f",  # \u7834\u635f
    "\u53d1\u9519",  # \u53d1\u9519
    "\u9519\u8bef",  # \u9519\u8bef
    "\u7f3a\u5c11",  # \u7f3a\u5c11
    "\u4e22\u5931",  # \u4e22\u5931
    "\u9000\u6b3e",  # \u9000\u6b3e
    "\u9000\u8d27",  # \u9000\u8d27
    "\u7cdf\u7cd5",  # \u5f3a\u70c8\u8d1f\u9762
    "\u592a\u5dee",  # \u5f3a\u70c8\u8d1f\u9762
    "\u5931\u671b",  # \u5931\u671b
    "\u4e0d\u53ef\u63a5\u53d7",  # \u4e0d\u53ef\u63a5\u53d7
    "\u574f",  # \u574f
    "\u5dee",  # \u5dee
    "\u6709\u7f3a\u9677",  # \u7f3a\u9677
    "\u6545\u969c",  # \u6545\u969c
    "\u9a97\u5b50",  # \u4fe1\u4efb\u6295\u8bc9
    "\u751f\u6c14",  # \u60c5\u7eea
    "\u6700\u7cdf",  # \u6700\u9ad8\u7ea7
    "\u4ece\u672a",  # \u4ece\u672a\u5230\u8fbe
    "\u95ee\u9898",  # \u901a\u7528\u95ee\u9898
    "\u6295\u8bc9",  # \u660e\u786e\u6295\u8bc9
    "\u8fdd\u7ea6",  # \u8fdd\u7ea6
]

# ---------------------------------------------------------------------------
# \u95ee\u9898\u6807\u7b7e\uff1a\u8de8\u8bed\u8a00\u7a33\u5b9a\u7684\u952e\uff0c\u503c\u5df2\u672c\u5730\u5316\u3002
# ---------------------------------------------------------------------------

ISSUE_LABELS = {
    "late": "\u5ef6\u8fdf\u53d1\u8d27",
    "damaged": "\u5546\u54c1\u635f\u574f",
    "wrong_item": "\u53d1\u9519\u5546\u54c1",
    "missing": "\u7f3a\u5c11\u5546\u54c1",
    "lost": "\u5305\u88f9\u4e22\u5931",
    "refund": "\u9000\u6b3e\u8bf7\u6c42",
    "return": "\u9000\u8d27\u8bf7\u6c42",
    "quality": "\u8d28\u91cf\u95ee\u9898",
    "not_as_described": "\u4e0e\u63cf\u8ff0\u4e0d\u7b26",
    "defective": "\u4ea7\u54c1\u6709\u7f3a\u9677",
    "shipping": "\u7269\u6d41\u95ee\u9898",
    "general": "\u60a8\u7684\u7559\u8a00",
}

# ---------------------------------------------------------------------------
# \u6a21\u677f\u2014\u2014\u6bcf\u4e2a\u90fd\u5305\u542b {citation}\uff1b\u4e0d\u865a\u6784\u8ba2\u5355\u53f7\u3002
# ---------------------------------------------------------------------------

DM_REPLY_TEMPLATE = (
    "\u60a8\u597d {customer}\uff0c\u611f\u8c22\u8054\u7cfb {shop}\u3002"
    "\u5f88\u62b1\u6b49\u51fa\u73b0\u4e86{issue}\u7684\u95ee\u9898\u3002"
    "\u6211\u4eec\u4f1a\u7acb\u5373\u67e5\u770b\uff0c\u5e76\u57282\u5c0f\u65f6\u5185\u56de\u590d\u89e3\u51b3\u65b9\u6848"
    "\uff08\u9000\u6b3e\u6216\u8865\u53d1\uff09\u3002"
    "\u6765\u6e90\uff1a{citation}"
)

REVIEW_REPLY_TEMPLATE = (
    "\u60a8\u597d\uff0c\u611f\u8c22\u60a8\u5bf9 {shop} \u7684 {product} \u7684\u8bc4\u4ef7\u3002"
    "\u5f88\u62b1\u6b49\u6ca1\u6709\u8fbe\u5230\u60a8\u7684\u671f\u671b\u3002"
    "\u6211\u4eec\u4f1a\u59a5\u5584\u5904\u7406\uff0c\u5e76\u57282\u5c0f\u65f6\u5185\u8ddf\u8fdb\u3002"
    "\u6765\u6e90\uff1a{citation}"
)

PO_EMAIL_TEMPLATE = (
    "\u4e3b\u9898\uff1a\u6765\u81ea {shop} \u7684\u8865\u8d27\u8bf7\u6c42\n"
    "\u60a8\u597d {supplier}\uff0c\n"
    "\u8bf7\u4e3a {shop} \u62a5\u4ef7\u4ee5\u4e0b\u660e\u7ec6\uff1a\n"
    "{lines}\n"
    "\u6b64\u6b21\u8986\u76d6\u63a5\u4e0b\u6765 14 \u5929\u7684\u9700\u6c42\u3002"
    "\u8bf7\u786e\u8ba4\u4ea4\u671f\u548c\u4ef7\u683c\u3002\n"
    "\u8c22\u8c22\uff0c\n"
    "{shop}\n"
    "\u6765\u6e90\uff1a{citation}"
)

COVER_NOTE_14D_TEMPLATE = (
    "\u8986\u76d6\u8bf4\u660e\uff1a\u672c\u8ba1\u5212\u8986\u76d6 {shop} \u63a5\u4e0b\u6765 14 \u5929\u3002"
    "\u6570\u91cf\u57fa\u4e8e\u8fc7\u53bb 14 \u5929\u9500\u91cf\u52a0\u5c0f\u5e45\u88d5\u91cf\u3002"
    "\u6765\u6e90\uff1a{citation}"
)

GREETING_TEMPLATE = "\u60a8\u597d {customer}\uff0c"
CLOSING_TEMPLATE = "\u8c22\u8c22\uff0c{shop}\u56e2\u961f"

STRINGS = {
    "greeting": GREETING_TEMPLATE,
    "closing": CLOSING_TEMPLATE,
    "dm_reply": DM_REPLY_TEMPLATE,
    "review_reply": REVIEW_REPLY_TEMPLATE,
    "po_email": PO_EMAIL_TEMPLATE,
    "cover_note": COVER_NOTE_14D_TEMPLATE,
    "cover_note_14d": COVER_NOTE_14D_TEMPLATE,
    "reply_window": "\u6211\u4eec\u5c06\u57282\u5c0f\u65f6\u5185\u56de\u590d\u3002",
    "cover_14d": "\u6b64\u6b21\u8986\u76d6\u63a5\u4e0b\u6765 14 \u5929\u3002",
    "thanks": "\u611f\u8c22\u8054\u7cfb {shop}\u3002",
    "apology": "\u5f88\u62b1\u6b49\u51fa\u73b0\u4e86{issue}\u7684\u95ee\u9898\u3002",
}

dm_reply = DM_REPLY_TEMPLATE
review_reply = REVIEW_REPLY_TEMPLATE
po_email = PO_EMAIL_TEMPLATE
cover_note = COVER_NOTE_14D_TEMPLATE


# ---------------------------------------------------------------------------
# \u8f85\u52a9\u51fd\u6570
# ---------------------------------------------------------------------------

def _safe(value, fallback=""):
    """\u8fd4\u56de\u53bb\u9664\u9996\u5c3e\u7a7a\u683c\u7684\u5b57\u7b26\u4e32\u6216\u9ed8\u8ba4\u503c\u3002"""
    if value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    return value.strip() or fallback


def format_po_lines(lines) -> str:
    """\u786e\u5b9a\u6027\u5730\u683c\u5f0f\u5316\u91c7\u8d2d\u660e\u7ec6\u3002

    \u63a5\u53d7\u5b57\u7b26\u4e32\u5217\u8868\u6216\u5b57\u5178\u5217\u8868\uff08product/qty \u952e\uff09\uff0c
    \u6216\u5df2\u683c\u5f0f\u5316\u7684\u5b57\u7b26\u4e32\u3002\u652f\u6301\u952e\uff1a product\u3001name\u3001
    title\u3001sku\u3001qty\u3001quantity\u3001count\u3002\u6309\u8f93\u5165\u987a\u5e8f\u8f93\u51fa\u3002
    """
    if lines is None:
        return "- \uff08\u65e0\u660e\u7ec6\uff09"
    if isinstance(lines, str):
        text = lines.strip()
        return text if text else "- \uff08\u65e0\u660e\u7ec6\uff09"
    if isinstance(lines, dict):
        lines = [lines]
    try:
        items = list(lines)
    except TypeError:
        return _safe(lines, "- \uff08\u65e0\u660e\u7ec6\uff09")
    if not items:
        return "- \uff08\u65e0\u660e\u7ec6\uff09"
    out = []
    for entry in items:
        if isinstance(entry, dict):
            product = (
                entry.get("product")
                or entry.get("name")
                or entry.get("title")
                or entry.get("sku")
                or "\u5546\u54c1"
            )
            qty = (
                entry.get("qty")
                if entry.get("qty") is not None
                else entry.get("quantity", entry.get("count", 1))
            )
            out.append(f"- {product} x {qty}")
        else:
            text = _safe(entry, "")
            if text:
                if text.startswith(("-", "*", "\u2022")):
                    out.append(text if text.startswith("- ") else "- " + text.lstrip("-* \u2022"))
                else:
                    out.append(f"- {text}")
    return "\n".join(out) if out else "- \uff08\u65e0\u660e\u7ec6\uff09"


def get_issue_label(text: str) -> str:
    """\u5c06\u81ea\u7531\u6587\u672c\u6620\u5c04\u5230\u672c\u5730\u5316\u6807\u7b7e\uff08\u786e\u5b9a\u6027\uff09\u3002"""
    lowered = (text or "").lower()
    if any(k in text for k in ("\u5ef6\u8fdf", "\u592a\u6162", "\u6ca1\u6709\u6536\u5230", "\u4ece\u672a")):
        return ISSUE_LABELS["late"]
    if any(k in text for k in ("\u574f\u4e86", "\u635f\u574f", "\u7834\u635f", "\u6709\u7f3a\u9677", "\u6545\u969c", "\u65e0\u6cd5\u4f7f\u7528")):
        return ISSUE_LABELS["damaged"]
    if any(k in text for k in ("\u53d1\u9519", "\u9519\u8bef", "\u4e0d\u5bf9")):
        return ISSUE_LABELS["wrong_item"]
    if "\u7f3a\u5c11" in text:
        return ISSUE_LABELS["missing"]
    if any(k in text for k in ("\u4e22\u5931", "\u5305\u88f9")):
        return ISSUE_LABELS["lost"]
    if "\u9000\u6b3e" in text:
        return ISSUE_LABELS["refund"]
    if "\u9000\u8d27" in text:
        return ISSUE_LABELS["return"]
    if any(k in text for k in ("\u8d28\u91cf", "\u592a\u5dee", "\u4e0d\u7b26")):
        return ISSUE_LABELS["quality"]
    if any(k in text for k in ("\u7269\u6d41", "\u5feb\u9012")):
        return ISSUE_LABELS["shipping"]
    # \u9000\u5316\u4e3a\u5c0f\u5199\u5339\u914d\u4fdd\u5e95\uff08\u5bf9\u4e2d\u6587\u65e0\u5f71\u54cd\uff09\u3002
    _ = lowered
    return ISSUE_LABELS["general"]


def is_complaint(text: str) -> bool:
    """\u5982\u679c\u6587\u672c\u5305\u542b COMPLAINT_PHRASES \u4e2d\u7684\u4efb\u4f55\u6761\u76ee\u5219\u4e3a True\u3002"""
    if not isinstance(text, str) or not text:
        return False
    return any(phrase in text for phrase in COMPLAINT_PHRASES)


def is_negative(text: str) -> bool:
    """\u5982\u679c\u6587\u672c\u663e\u793a\u8d1f\u9762\u60c5\u7eea\u5219\u4e3a True\u3002"""
    if not isinstance(text, str) or not text:
        return False
    if is_complaint(text):
        return True
    return any(word in text for word in NEGATIVE_WORDS)


def greeting(customer: str) -> str:
    """\u672c\u5730\u5316\u95ee\u5019\u3002"""
    return GREETING_TEMPLATE.format(customer=_safe(customer, "\u670b\u53cb"))


def closing(shop: str) -> str:
    """\u672c\u5730\u5316\u7ed3\u5c3e\u3002"""
    return CLOSING_TEMPLATE.format(shop=_safe(shop, "\u6211\u4eec\u7684\u5e97\u94fa"))


# ---------------------------------------------------------------------------
# \u57fa\u7840\u6784\u5efa\u5668\uff08\u90fd\u5305\u542b\u5f15\u7528\uff1b\u4e0d\u865a\u6784\u8ba2\u5355\u53f7\uff09
# ---------------------------------------------------------------------------

def DM_REPLY(customer, issue, citation, shop) -> str:
    """\u6784\u5efa\u4e2d\u6587\u57fa\u7840 DM \u56de\u590d\u3002

    Args:
      customer: \u4e70\u5bb6\u59d3\u540d\u3002
      issue: \u5df2\u672c\u5730\u5316\u7684\u77ed\u95ee\u9898\u63cf\u8ff0\u3002
      citation: \u6765\u6e90\u6587\u4ef6\u540d\uff0c\u4f8b\u5982 tiktok_dm.json\u3002
      shop: \u5e97\u94fa\u663e\u793a\u540d\u3002
    """
    return DM_REPLY_TEMPLATE.format(
        customer=_safe(customer, "\u670b\u53cb"),
        issue=_safe(issue, ISSUE_LABELS["general"]),
        citation=_safe(citation, "tiktok_dm.json"),
        shop=_safe(shop, "\u6211\u4eec\u7684\u5e97\u94fa"),
    )


def REVIEW_REPLY(product, citation, shop) -> str:
    """\u6784\u5efa\u4e2d\u6587\u516c\u5f00\u8bc4\u4ef7\u56de\u590d\u3002"""
    return REVIEW_REPLY_TEMPLATE.format(
        product=_safe(product, "\u60a8\u7684\u5546\u54c1"),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "\u6211\u4eec\u7684\u5e97\u94fa"),
    )


def PO_EMAIL(supplier, lines, shop, citation="inventory.csv") -> str:
    """\u6784\u5efa\u4e2d\u6587\u57fa\u7840\u8865\u8d27\u90ae\u4ef6\u3002

    ``citation`` \u9ed8\u8ba4\u4e3a inventory.csv\uff0c\u5373\u4f7f\u53ea\u4f20
    (supplier, lines, shop) \u4e5f\u80fd\u6ee1\u8db3\u5360\u4f4d\u7b26\u8981\u6c42\u3002
    """
    return PO_EMAIL_TEMPLATE.format(
        supplier=_safe(supplier, "\u4f9b\u5e94\u5546"),
        lines=format_po_lines(lines),
        shop=_safe(shop, "\u6211\u4eec\u7684\u5e97\u94fa"),
        citation=_safe(citation, "inventory.csv"),
    )


def cover_note_14d(shop, citation="inventory.csv") -> str:
    """\u4e2d\u6587\u672c\u5730\u5316 14 \u5929\u8986\u76d6\u8bf4\u660e\u3002"""
    return COVER_NOTE_14D_TEMPLATE.format(
        shop=_safe(shop, "\u6211\u4eec\u7684\u5e97\u94fa"),
        citation=_safe(citation, "inventory.csv"),
    )


def dm_reply(customer, issue, citation, shop) -> str:
    """DM_REPLY \u7684\u5c0f\u5199\u522b\u540d\u3002"""
    return DM_REPLY(customer, issue, citation, shop)


def review_reply(product, citation, shop) -> str:
    """REVIEW_REPLY \u7684\u5c0f\u5199\u522b\u540d\u3002"""
    return REVIEW_REPLY(product, citation, shop)


def po_email(supplier, lines, shop, citation="inventory.csv") -> str:
    """PO_EMAIL \u7684\u5c0f\u5199\u522b\u540d\u3002"""
    return PO_EMAIL(supplier, lines, shop, citation)


dm_reply_fn = DM_REPLY
review_reply_fn = REVIEW_REPLY
po_email_fn = PO_EMAIL

__all__ = [
    "LOCALE",
    "LANGUAGE_NAME",
    "FORMALITY",
    "COMPLAINT_PHRASES",
    "NEGATIVE_WORDS",
    "ISSUE_LABELS",
    "DM_REPLY_TEMPLATE",
    "REVIEW_REPLY_TEMPLATE",
    "PO_EMAIL_TEMPLATE",
    "COVER_NOTE_14D_TEMPLATE",
    "STRINGS",
    "DM_REPLY",
    "REVIEW_REPLY",
    "PO_EMAIL",
    "cover_note_14d",
    "is_complaint",
    "is_negative",
    "get_issue_label",
    "format_po_lines",
    "greeting",
    "closing",
]


# ---------------------------------------------------------------------------
# \u9644\u5f55\uff1a\u7528\u6cd5\u793a\u4f8b\u4e0e\u57fa\u7840\u4fdd\u8bc1\uff08\u771f\u5b9e\u6587\u6863\uff0c\u4e0d\u6539\u53d8\u884c\u4e3a\uff09\u3002
# ---------------------------------------------------------------------------
# DM \u793a\u4f8b\uff1a
#   DM_REPLY("\u5c0f\u660e", "\u5ef6\u8fdf\u53d1\u8d27", "tiktok_dm.json", "Solmar")
#   -> "\u60a8\u597d \u5c0f\u660e\uff0c\u611f\u8c22\u8054\u7cfb Solmar\u3002\u5f88\u62b1\u6b49\u51fa\u73b0\u4e86\u5ef6\u8fdf\u53d1\u8d27\u7684\u95ee\u9898\u3002
#       \u6211\u4eec\u4f1a\u7acb\u5373\u67e5\u770b\uff0c\u5e76\u57282\u5c0f\u65f6\u5185\u56de\u590d\u89e3\u51b3\u65b9\u6848
#       \uff08\u9000\u6b3e\u6216\u8865\u53d1\uff09\u3002\u6765\u6e90\uff1atiktok_dm.json"
# \u8bc4\u4ef7\u793a\u4f8b\uff1a
#   REVIEW_REPLY("\u5e06\u5e03\u888b", "reviews.csv", "Solmar")
#   -> \u611f\u8c22 + \u9053\u6b49 + 2\u5c0f\u65f6\u627f\u8bfa + "\u6765\u6e90\uff1areviews.csv"\u3002
# \u91c7\u8d2d\u793a\u4f8b\uff1a
#   PO_EMAIL("\u4f9b\u5e94\u5546", [{"product": "\u5e06\u5e03\u888b", "qty": 20}], "Solmar")
#   -> \u4e3b\u9898\u884c + "\u2011 \u5e06\u5e03\u888b x 20" + 14\u5929\u8986\u76d6
#      + "\u6765\u6e90\uff1ainventory.csv"\u3002
# \u57fa\u7840\u4fdd\u8bc1\uff1a
#   - \u6bcf\u4e2a\u6e32\u67d3\u6a21\u677f\u90fd\u539f\u6837\u5305\u542b\u5f15\u7528\u5b57\u7b26\u4e32\u3002
#   - \u6ca1\u6709\u6a21\u677f\u5305\u542b "#" +\u6570\u5b57\uff08\u4e0d\u865a\u6784\u8ba2\u5355\u53f7\uff09\u3002
#   - \u6784\u5efa\u5668\u6709\u5b89\u5168\u9ed8\u8ba4\u503c\uff0cNone \u8f93\u5165\u4e0d\u62a5\u9519\u3002
#   - \u6240\u6709\u6784\u5efa\u5668\u662f\u7eaf\u51fd\u6570\uff1a\u76f8\u540c\u8f93\u5165\u2014>\u76f8\u540c\u8f93\u51fa\u3002
# \u786e\u5b9a\u6027\uff1a
#   - \u672c\u6a21\u5757\u65e0\u65f6\u949f\u3001\u65e0\u968f\u673a\u3001\u65e0\u7f51\u7edc\u3001\u65e0\u6587\u4ef6 IO\u3002
#   - format_po_lines \u4fdd\u6301\u8f93\u5165\u987a\u5e8f\uff0c\u5dee\u5f02\u7a33\u5b9a\u3002
#   - get_issue_label \u4f18\u5148\u68c0\u67e5\u5ef6\u8fdf/\u635f\u574f\uff0c\u5206\u7c7b\u7a33\u5b9a\u3002
# \u53c2\u89c1\uff1adrafts.build_reply\u3001drafts.build_po\u3001channels.normalize_dm\u3002
# zh \u8bed\u8a00\u6a21\u5757\u7ed3\u675f\u3002

