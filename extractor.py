from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime

import pdfplumber

PLACE_RE = re.compile(
    r"Place of supply\s*:?\s*([^\n(]+)(?:\s*\(\s*State\s*/?\s*UT\s*Code\s*:\s*(\d+)\s*\))?",
    re.IGNORECASE,
)
DOC_NO_RE = re.compile(
    r"Document Number\s+([A-Za-z0-9\-\/]+)",
    re.IGNORECASE,
)
DOC_DATE_RE = re.compile(
    r"Document Date\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)
HEADER_STOPWORDS = {
    "sno",
    "s.no",
    "s no",
    "product description",
    "qty",
    "quantity",
    "unit value",
    "hsn",
    "sac",
    "total",
}


@dataclass
class ExtractedChallan:
    source_name: str
    place_name: str | None = None
    gst_code: str | None = None
    document_number: str | None = None
    last4: str | None = None
    document_date: str | None = None
    mmmyy: str | None = None
    products: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def normalize_product(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def product_key(text: str) -> str:
    return normalize_product(text).lower()


def _parse_date(value: str) -> str | None:
    raw = value.strip().replace("-", "/")
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%b%y").upper()
        except ValueError:
            continue
    return None


def _clean_place_name(name: str) -> str:
    text = re.sub(r"\s+", " ", name).strip(" :")
    text = re.sub(r"\(.*$", "", text).strip()
    return text


def _is_header_cell(value: str) -> bool:
    lowered = normalize_product(value).lower()
    return lowered in HEADER_STOPWORDS or lowered.startswith("unit value")


def _products_from_tables(page) -> list[str]:
    products: list[str] = []
    tables = page.extract_tables() or []
    for table in tables:
        if not table:
            continue
        header_idx = None
        desc_col = None
        for row_i, row in enumerate(table):
            cells = [normalize_product(c or "") for c in row]
            for col_i, cell in enumerate(cells):
                if cell.lower() == "product description":
                    header_idx = row_i
                    desc_col = col_i
                    break
            if desc_col is not None:
                break
        if desc_col is None:
            continue
        for row in table[header_idx + 1 :]:
            if desc_col >= len(row):
                continue
            cell = normalize_product(row[desc_col] or "")
            if not cell or cell.lower() == "total" or _is_header_cell(cell):
                continue
            products.append(cell)
    return products


def _products_from_text(text: str) -> list[str]:
    match = re.search(
        r"Product Description(.*?)(?:Total Value of Goods|Declaration|We declare that)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    block = match.group(1)
    lines = [normalize_product(line) for line in block.splitlines()]
    lines = [line for line in lines if line]
    products: list[str] = []
    current: list[str] = []
    skip_prefixes = (
        "qty",
        "unit value",
        "hsn",
        "sac",
        "igst",
        "cess",
        "total taxable",
        "total value",
        "sno",
    )

    for line in lines:
        lowered = line.lower()
        if lowered == "total" or lowered.startswith("total "):
            break
        if any(lowered.startswith(prefix) for prefix in skip_prefixes):
            continue
        if re.fullmatch(r"\d+(\.\d+)?%?", line.replace(",", "")):
            continue
        if re.match(r"^\d+\s+", line):
            line = re.sub(r"^\d+\s+", "", line)
            if current:
                products.append(normalize_product(" ".join(current)))
                current = []
        if line:
            current.append(line)
    if current:
        products.append(normalize_product(" ".join(current)))
    return [p for p in products if p and p.lower() != "total"]


def extract_challan(data: bytes, source_name: str) -> ExtractedChallan:
    result = ExtractedChallan(source_name=source_name)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if not pdf.pages:
                result.error = "PDF has no pages"
                return result
            page = pdf.pages[0]
            text = page.extract_text() or ""
            products = _products_from_tables(page)
            if not products:
                products = _products_from_text(text)
    except Exception as exc:  # noqa: BLE001 - surface parse failures in the UI
        result.error = f"Could not read PDF: {exc}"
        return result

    place_match = PLACE_RE.search(text)
    if place_match:
        result.place_name = _clean_place_name(place_match.group(1))
        if place_match.group(2):
            result.gst_code = place_match.group(2).zfill(2)

    doc_match = DOC_NO_RE.search(text)
    if doc_match:
        result.document_number = doc_match.group(1).strip()
        result.last4 = result.document_number[-4:]

    date_match = DOC_DATE_RE.search(text)
    if date_match:
        result.document_date = date_match.group(1)
        result.mmmyy = _parse_date(date_match.group(1))

    result.products = [normalize_product(p) for p in products if normalize_product(p)]

    missing: list[str] = []
    if not result.place_name and not result.gst_code:
        missing.append("place of supply")
    if not result.document_number:
        missing.append("document number")
    if not result.mmmyy:
        missing.append("document date")
    if not result.products:
        missing.append("product description")
    if missing:
        result.error = "Missing " + ", ".join(missing)
    return result
