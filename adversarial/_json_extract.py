"""
Robust JSON object extraction from noisy LLM output.

Fixes the M1 bug: a greedy ``re.search(r"\\{.*\\}", txt, re.DOTALL)`` will
match across multiple JSON objects when the LLM emits commentary plus JSON,
producing invalid syntax. We do proper brace-balanced extraction with
string-aware quote handling instead.

Used by both ``attacks.news_rewriter._judge`` and
``judges.injection_landed._parse``.
"""

from __future__ import annotations

import json


def extract_first_json_object(text: str) -> dict | None:
    """Return the first valid JSON object literal in ``text`` or None.

    Walks character by character, tracking brace depth and quote state so
    that braces inside string literals do not confuse the matcher.
    """
    if not text:
        return None
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, n):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[i:j + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        break  # this candidate failed, try next "{"
        i += 1
    return None


def parse_llm_json(raw: str) -> dict | None:
    """Try strict JSON, then code-fence-stripped, then balanced-extract.
    Returns None if nothing usable is found."""
    if raw is None:
        return None
    txt = raw.strip()
    # 1. strict
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    # 2. strip ``` fences
    fenced = txt
    if fenced.startswith("```"):
        fenced = fenced.strip("`")
        if fenced.lower().startswith("json"):
            fenced = fenced[4:]
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass
    # 3. balanced-extract first object
    return extract_first_json_object(txt)
