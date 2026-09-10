from __future__ import annotations

import re
from pathlib import Path


def sanitize_token(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\-]+", "", token.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def last4_document_number(document_number: str) -> str:
    value = document_number.strip()
    return value[-4:] if len(value) >= 4 else value


def build_filename(
    skus: list[str],
    last4: str,
    place_code: str,
    mmmyy: str,
) -> str:
    sku_part = "-".join(filter(None, (sanitize_token(sku) for sku in skus)))
    parts = [
        "Challan",
        sku_part,
        sanitize_token(last4),
        sanitize_token(place_code).upper(),
        sanitize_token(mmmyy).upper(),
    ]
    if not all(parts):
        raise ValueError("Filename is missing SKU, document number, place, or date")
    return "-".join(parts) + ".pdf"


def unique_filename(
    name: str,
    dest_dir: Path,
    used: set[str],
    ignore: Path | None = None,
) -> str:
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    stem = name[:-4]
    candidate = name
    counter = 2
    ignore_resolved = ignore.resolve() if ignore and ignore.exists() else None
    while True:
        dest = dest_dir / candidate
        taken = candidate in used
        exists = dest.exists()
        is_self = ignore_resolved is not None and exists and dest.resolve() == ignore_resolved
        if not taken and (not exists or is_self):
            break
        candidate = f"{stem}-{counter}.pdf"
        counter += 1
    used.add(candidate)
    return candidate


def zip_name_for_batch(
    mmmyy_values: set[str],
    file_count: int,
    user_name: str = "",
) -> str | None:
    if file_count <= 0:
        return None
    if len(mmmyy_values) == 1:
        mmmyy = sanitize_token(next(iter(mmmyy_values))).upper()
        return f"{mmmyy}-{file_count}.zip"
    cleaned = user_name.strip()
    if cleaned.lower().endswith(".zip"):
        cleaned = cleaned[:-4]
    cleaned = sanitize_token(cleaned)
    if not cleaned:
        return None
    return f"{cleaned}-{file_count}.zip"
