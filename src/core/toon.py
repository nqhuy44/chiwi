"""TOON (Token-Oriented Object Notation) encoder.

Compact serialization for structured context sent to LLMs. Typically
~40-60% fewer tokens than pretty-printed JSON for uniform object arrays
because it eliminates quotes on keys, drops brackets/braces in favor of
indentation, and renders arrays of uniform objects as CSV-style tables
with a length annotation.

Reference: https://github.com/toon-format/toon

Format sketch the encoder produces:

    # Scalar
    key: value

    # Nested object
    user:
      name: Alice
      address:
        city: HCMC

    # Array of primitives
    tags[3]: coffee,work,weekly

    # Array of uniform scalar-only objects (biggest savings)
    users[2]{id,name,age}:
      1,Alice,30
      2,Bob,25

    # Array of mixed/nested objects — per-item blocks
    items[2]:
      -
        name: Alice
        meta:
          tier: gold
      -
        name: Bob

Strings are quoted only when they contain a delimiter (``, : { } [ ]``),
leading/trailing whitespace, or control characters.
"""

from __future__ import annotations

from typing import Any

_INDENT = "  "
_QUOTE_CHARS = set(',:{}[]"\n\r\t')


def to_toon(data: Any) -> str:
    """Encode ``data`` to a TOON string.

    Accepts dicts, lists, and JSON-compatible scalars. Non-standard types
    (datetime, Decimal, etc.) are coerced with ``str()`` — callers should
    pre-convert when a specific representation matters.
    """
    return _encode(data, 0).rstrip("\n")


# -- internals ---------------------------------------------------------------


def _is_scalar(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


def _needs_quote(s: str) -> bool:
    if s == "":
        return True
    if s[0].isspace() or s[-1].isspace():
        return True
    return any(c in _QUOTE_CHARS for c in s)


def _quote(s: str) -> str:
    escaped = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _format_key(k: Any) -> str:
    s = str(k)
    return _quote(s) if _needs_quote(s) else s


def _format_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return _quote(s) if _needs_quote(s) else s


def _uniform_object_keys(items: list[Any]) -> list[str] | None:
    """Return shared keys if ``items`` is a non-empty list of dicts with
    identical key sets and scalar-only values; else ``None``."""
    if not items or not all(isinstance(x, dict) for x in items):
        return None
    keys = list(items[0].keys())
    if not keys:
        return None
    expected = set(keys)
    for obj in items:
        if set(obj.keys()) != expected:
            return None
        if not all(_is_scalar(obj[k]) for k in keys):
            return None
    return keys


def _encode(data: Any, depth: int) -> str:
    if _is_scalar(data):
        return _format_scalar(data)
    if isinstance(data, dict):
        return _encode_dict(data, depth)
    if isinstance(data, (list, tuple)):
        return _encode_root_list(list(data), depth)
    return _format_scalar(str(data))


def _encode_dict(d: dict, depth: int) -> str:
    if not d:
        return f"{_INDENT * depth}{{}}"
    pad = _INDENT * depth
    lines: list[str] = []
    for k, v in d.items():
        key = _format_key(k)
        if _is_scalar(v):
            lines.append(f"{pad}{key}: {_format_scalar(v)}")
        elif isinstance(v, dict):
            if not v:
                lines.append(f"{pad}{key}: {{}}")
            else:
                lines.append(f"{pad}{key}:")
                lines.append(_encode_dict(v, depth + 1))
        elif isinstance(v, (list, tuple)):
            lines.append(_encode_list_field(key, list(v), depth))
        else:
            lines.append(f"{pad}{key}: {_format_scalar(str(v))}")
    return "\n".join(lines)


def _encode_list_field(key: str, items: list, depth: int) -> str:
    pad = _INDENT * depth
    n = len(items)
    if n == 0:
        return f"{pad}{key}[0]:"

    if all(_is_scalar(x) for x in items):
        csv = ",".join(_format_scalar(x) for x in items)
        return f"{pad}{key}[{n}]: {csv}"

    keys = _uniform_object_keys(items)
    if keys is not None:
        header = ",".join(_format_key(k) for k in keys)
        lines = [f"{pad}{key}[{n}]{{{header}}}:"]
        inner = _INDENT * (depth + 1)
        for obj in items:
            row = ",".join(_format_scalar(obj[k]) for k in keys)
            lines.append(f"{inner}{row}")
        return "\n".join(lines)

    # Mixed/nested: per-item blocks.
    lines = [f"{pad}{key}[{n}]:"]
    inner = _INDENT * (depth + 1)
    for obj in items:
        if isinstance(obj, dict):
            lines.append(f"{inner}-")
            lines.append(_encode_dict(obj, depth + 2))
        elif isinstance(obj, (list, tuple)):
            lines.append(f"{inner}-")
            lines.append(_encode_list_field("_", list(obj), depth + 2))
        else:
            lines.append(f"{inner}- {_format_scalar(obj)}")
    return "\n".join(lines)


def _encode_root_list(items: list, depth: int) -> str:
    """Top-level list: emit under a synthetic ``items`` key for legibility."""
    return _encode_list_field("items", items, depth)
