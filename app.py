from __future__ import annotations

import importlib
import io
import zipfile
from collections import Counter
from pathlib import Path

import streamlit as st

import extractor
import namer
import sku_store

importlib.reload(extractor)
importlib.reload(namer)
importlib.reload(sku_store)

from deployment import is_cloud_deployment, supports_native_picker
from extractor import ExtractedChallan, extract_challan, product_key
from file_picker import pick_pdfs
from namer import build_filename, unique_filename, zip_name_for_batch
from sku_store import load_store, lookup_place_code, save_sku_mappings

st.set_page_config(page_title="Challan Renamer", layout="wide")

ParsedItem = tuple[str, bytes, ExtractedChallan, Path | None]
CLOUD_MODE = is_cloud_deployment()


def _file_id(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def _upload_id(uploaded) -> str:
    return f"{uploaded.name}:{uploaded.size}"


def _extract_paths(paths: list[Path]) -> list[ParsedItem]:
    parsed: list[ParsedItem] = []
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        parsed.append((path.name, data, extract_challan(data, path.name), path))
    return parsed


def _extract_uploads(uploads) -> list[ParsedItem]:
    parsed: list[ParsedItem] = []
    for uploaded in uploads:
        data = uploaded.getvalue()
        parsed.append((uploaded.name, data, extract_challan(data, uploaded.name), None))
    return parsed


def _unique_products(results: list[ExtractedChallan]) -> list[tuple[str, str, int]]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for result in results:
        if not result.ok:
            continue
        seen: set[str] = set()
        for product in result.products:
            key = product_key(product)
            display.setdefault(key, product)
            if key in seen:
                continue
            seen.add(key)
            counts[key] += 1
    return [(key, display[key], counts[key]) for key in display]


def _place_for(result: ExtractedChallan, store: dict) -> str | None:
    return lookup_place_code(result.place_name, result.gst_code, store)


def _preview_name(result: ExtractedChallan, sku_by_key: dict[str, str], store: dict) -> str:
    place = _place_for(result, store)
    if not place:
        raise ValueError(f"Unknown place of supply: {result.place_name or result.gst_code}")
    if not result.last4 or not result.mmmyy:
        raise ValueError("Missing document number or date")
    skus = [sku_by_key[product_key(product)] for product in result.products]
    if any(not sku.strip() for sku in skus):
        raise ValueError("SKU missing")
    return build_filename(skus, result.last4, place, result.mmmyy)


def _write_renamed(
    parsed: list[ParsedItem],
    sku_by_key: dict[str, str],
    store: dict,
    *,
    rename_in_place: bool,
) -> tuple[list[dict], bytes, list[ParsedItem]]:
    used_names: set[str] = set()
    rows: list[dict] = []
    updated: list[ParsedItem] = []
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for source_name, data, result, source_path in parsed:
            if not result.ok:
                rows.append(
                    {
                        "original": source_name,
                        "new_name": "",
                        "status": result.error or "Skipped",
                    }
                )
                updated.append((source_name, data, result, source_path))
                continue
            try:
                ignore = source_path if rename_in_place and source_path else None
                dest_dir = source_path.parent if source_path else Path(".")
                new_name = unique_filename(
                    _preview_name(result, sku_by_key, store),
                    dest_dir,
                    used_names,
                    ignore=ignore,
                )
                if rename_in_place and source_path:
                    dest = source_path.parent / new_name
                    if dest.resolve() != source_path.resolve():
                        source_path.rename(dest)
                    updated.append((new_name, data, result, dest))
                else:
                    updated.append((new_name, data, result, None))
                archive.writestr(new_name, data)
                rows.append(
                    {
                        "original": source_name,
                        "new_name": new_name,
                        "status": "Renamed",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "original": source_name,
                        "new_name": "",
                        "status": str(exc),
                    }
                )
                updated.append((source_name, data, result, source_path))
    return rows, zip_buffer.getvalue(), updated


def _load_parsed_from_session() -> list[ParsedItem]:
    raw = st.session_state.get("parsed", [])
    parsed: list[ParsedItem] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 4:
            name, data, result, path = item
            parsed.append(
                (
                    str(name),
                    data,
                    result,
                    Path(path) if path and Path(path).exists() else None,
                )
            )
    return parsed


def _store_parsed(parsed: list[ParsedItem]) -> None:
    st.session_state.parsed = [
        (name, data, result, str(path) if path else None) for name, data, result, path in parsed
    ]


def _reset_results() -> None:
    st.session_state.rename_rows = None
    st.session_state.zip_bytes = None
    st.session_state.zip_filename = None


st.title("Delivery Challan Renamer")
if CLOUD_MODE:
    st.caption(
        "Upload challan PDFs in your browser. Renamed files are packaged as "
        "`Challan-SKU-last4-XX-MMMYY.pdf` inside a ZIP download."
    )
else:
    st.caption(
        "Upload challan PDFs. Each file is renamed in the same folder it was selected from "
        "as `Challan-SKU-last4-XX-MMMYY.pdf`."
    )

store = load_store()
if "selected_paths" not in st.session_state:
    st.session_state.selected_paths = []

if CLOUD_MODE or not supports_native_picker():
    uploads = st.file_uploader(
        "Upload challan PDFs",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if not uploads:
        st.info("Upload one or more delivery challan PDFs to begin.")
        st.stop()

    upload_ids = [_upload_id(item) for item in uploads]
    if st.session_state.get("upload_ids") != upload_ids:
        st.session_state.upload_ids = upload_ids
        _store_parsed(_extract_uploads(uploads))
        _reset_results()

    parsed = _load_parsed_from_session()
    st.write(f"Selected **{len(parsed)}** PDF(s)")
else:
    st.info("After clicking Upload PDFs, look for the macOS file picker — it may open behind this browser window.")

    if st.button("Upload PDFs"):
        with st.spinner("Waiting for file picker..."):
            try:
                chosen = pick_pdfs()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open the file picker: {exc}")
                chosen = []
        if chosen:
            st.session_state.selected_paths = [str(path) for path in chosen]
            st.session_state.file_ids = None
            _reset_results()
            st.rerun()
        elif chosen == []:
            st.warning("No files selected.")

    paths = [Path(item) for item in st.session_state.selected_paths if Path(item).is_file()]
    if not paths:
        st.info("Click Upload PDFs and select one or more delivery challan files.")
        st.stop()

    st.write(f"Selected **{len(paths)}** PDF(s) from `{paths[0].parent}`")

    file_ids = [_file_id(path) for path in paths]
    if st.session_state.get("file_ids") != file_ids:
        st.session_state.file_ids = file_ids
        _store_parsed(_extract_paths(paths))
        _reset_results()

    parsed = _load_parsed_from_session()

results = [item[2] for item in parsed]

st.subheader("Extracted files")
extracted_rows = []
for result in results:
    place = _place_for(result, store) if result.ok or result.place_name or result.gst_code else None
    extracted_rows.append(
        {
            "File": result.source_name,
            "Place": place or result.place_name or "",
            "GST": result.gst_code or "",
            "Last 4": result.last4 or "",
            "Date": result.mmmyy or "",
            "Products": " | ".join(result.products),
            "Status": "OK" if result.ok and place else (result.error or "Unknown place of supply"),
        }
    )
st.dataframe(extracted_rows, width="stretch", hide_index=True)

ok_results = [result for result in results if result.ok and _place_for(result, store)]
unknown_place = [
    result
    for result in results
    if (result.place_name or result.gst_code) and not _place_for(result, store)
]
if unknown_place:
    names = ", ".join(
        f"{item.source_name} ({item.place_name or item.gst_code})" for item in unknown_place
    )
    st.error(f"Unknown place of supply — add it to sku_mappings.json: {names}")

unique_products = _unique_products(ok_results)
if not unique_products:
    st.warning("No files produced a usable product description. Fix the PDFs or try again.")
    st.stop()

st.subheader("SKU mapping")
st.caption("One SKU per unique product description. Values are remembered in sku_mappings.json.")
sku_by_key: dict[str, str] = {}
for key, description, count in unique_products:
    default_sku = store["sku_mappings"].get(key, "")
    sku_by_key[key] = st.text_input(
        f"{description}",
        value=default_sku,
        key=f"sku::{key}",
        help=f"Used in {count} file(s)",
    ).strip()
    st.caption(f"Used in {count} file(s)")

missing_skus = [desc for key, desc, _ in unique_products if not sku_by_key[key]]
can_rename = not missing_skus and bool(ok_results)

st.subheader("Preview")
preview_rows = []
for result in results:
    if result not in ok_results:
        preview_rows.append(
            {
                "Original": result.source_name,
                "New name": "",
                "Status": result.error or "Skipped",
            }
        )
        continue
    try:
        preview_rows.append(
            {
                "Original": result.source_name,
                "New name": _preview_name(result, sku_by_key, store),
                "Status": "Ready" if can_rename else "Waiting for SKUs",
            }
        )
    except Exception as exc:  # noqa: BLE001
        preview_rows.append(
            {
                "Original": result.source_name,
                "New name": "",
                "Status": str(exc),
            }
        )
st.dataframe(preview_rows, width="stretch", hide_index=True)

if missing_skus:
    st.warning("Enter an SKU for every product before renaming.")

mmmyy_values = {result.mmmyy for result in ok_results if result.mmmyy}
zip_file_count = len(ok_results)
zip_name_input = ""
if len(mmmyy_values) > 1:
    st.warning(
        "PDFs have different document dates: "
        + ", ".join(sorted(mmmyy_values))
        + f". Enter a name for the downloaded ZIP ({zip_file_count} files)."
    )
    zip_name_input = st.text_input(
        "ZIP file name",
        placeholder=f"Challans-{zip_file_count}",
        help="The file count is appended automatically, e.g. MyBatch-6.zip",
    ).strip()
elif mmmyy_values:
    auto_zip = zip_name_for_batch(mmmyy_values, zip_file_count)
    st.caption(f"ZIP will download as `{auto_zip}`")

rename_label = "Rename and download" if CLOUD_MODE or not supports_native_picker() else "Rename files"
if st.button(rename_label, type="primary", disabled=not can_rename):
    merged = dict(store["sku_mappings"])
    merged.update({key: sku for key, sku in sku_by_key.items() if sku})
    store = save_sku_mappings(merged)
    rows, zip_bytes, updated = _write_renamed(
        parsed,
        sku_by_key,
        store,
        rename_in_place=supports_native_picker() and not CLOUD_MODE,
    )
    zip_count = sum(1 for row in rows if row["status"] == "Renamed")
    st.session_state.zip_filename = zip_name_for_batch(mmmyy_values, zip_count, zip_name_input)
    st.session_state.rename_rows = rows
    st.session_state.zip_bytes = zip_bytes
    _store_parsed(updated)
    if supports_native_picker() and not CLOUD_MODE:
        st.session_state.selected_paths = [
            str(path) for _, _, _, path in updated if path is not None
        ]
        st.session_state.file_ids = [
            _file_id(path) for _, _, _, path in updated if path is not None
        ]

if st.session_state.get("rename_rows"):
    saved = sum(1 for row in st.session_state.rename_rows if row["status"] == "Renamed")
    if CLOUD_MODE or not supports_native_picker():
        st.success(f"Prepared {saved} renamed file(s) for download.")
    else:
        folders = sorted({str(path.parent) for _, _, _, path in parsed if path is not None})
        st.success(f"Renamed {saved} file(s) in {', '.join(folders)}")
    st.dataframe(st.session_state.rename_rows, width="stretch", hide_index=True)
    if st.session_state.get("zip_bytes"):
        zip_count = sum(
            1 for row in st.session_state.rename_rows if row["status"] == "Renamed"
        )
        zip_filename = st.session_state.get("zip_filename") or zip_name_for_batch(
            mmmyy_values, zip_count, zip_name_input
        )
        st.download_button(
            "Download ZIP",
            data=st.session_state.zip_bytes,
            file_name=zip_filename or "Challans.zip",
            mime="application/zip",
            disabled=zip_filename is None,
        )
        if zip_filename is None:
            st.caption("Enter a ZIP file name above to enable download.")
