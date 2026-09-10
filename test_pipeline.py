from __future__ import annotations

import shutil
from pathlib import Path

from extractor import extract_challan
from namer import build_filename, unique_filename
from sample_pdf import CLOCK_DESCRIPTION, LAMP_DESCRIPTION, build_sample_challan
from sku_store import load_store, lookup_place_code, save_sku_mappings

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "sample_pdfs"
OUT_DIR = ROOT / "renamed_challans"


def main() -> None:
    if SAMPLE_DIR.exists():
        shutil.rmtree(SAMPLE_DIR)
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    SAMPLE_DIR.mkdir()
    OUT_DIR.mkdir()

    files = [
        build_sample_challan(
            SAMPLE_DIR / "clock_mh.pdf",
            document_number="FBA15M3SBDV2",
            document_date="08/25/2026",
            place_name="Maharashtra",
            gst_code="27",
            products=[(CLOCK_DESCRIPTION, 20)],
        ),
        build_sample_challan(
            SAMPLE_DIR / "clock_tn.pdf",
            document_number="FBA99X7QWER9",
            document_date="09/02/2026",
            place_name="Tamil Nadu",
            gst_code="33",
            products=[(CLOCK_DESCRIPTION, 5)],
        ),
        build_sample_challan(
            SAMPLE_DIR / "combo_ka.pdf",
            document_number="FBA22AB99ZZ",
            document_date="08/10/2026",
            place_name="Karnataka",
            gst_code="29",
            products=[(CLOCK_DESCRIPTION, 2), (LAMP_DESCRIPTION, 3)],
        ),
        build_sample_challan(
            SAMPLE_DIR / "lamp_typo.pdf",
            document_number="FBA33CD12AB",
            document_date="08/18/2026",
            place_name="Maharastha",
            gst_code="27",
            products=[(LAMP_DESCRIPTION, 1)],
        ),
    ]

    store = load_store()
    extracted = []
    for path in files:
        result = extract_challan(path.read_bytes(), path.name)
        assert result.ok, f"{path.name}: {result.error}"
        place = lookup_place_code(result.place_name, result.gst_code, store)
        assert place, f"No place code for {path.name}: {result.place_name}"
        extracted.append((path, result, place))
        print(path.name, result.last4, place, result.mmmyy, result.products)

    clock_mh, clock_result, clock_place = extracted[0]
    assert clock_result.last4 == "BDV2"
    assert clock_place == "MH"
    assert clock_result.mmmyy == "AUG26"
    assert any("ACCORD CLOCKS" in product for product in clock_result.products)

    sku_by_desc = {
        CLOCK_DESCRIPTION: "DG1",
        LAMP_DESCRIPTION: "NL2",
    }

    used: set[str] = set()
    expected = [
        "Challan-DG1-BDV2-MH-AUG26.pdf",
        "Challan-DG1-WER9-TN-SEP26.pdf",
        "Challan-DG1-NL2-99ZZ-KA-AUG26.pdf",
        "Challan-NL2-12AB-MH-AUG26.pdf",
    ]
    for (path, result, place), want in zip(extracted, expected):
        skus = [sku_by_desc[product] for product in result.products]
        name = unique_filename(
            build_filename(skus, result.last4, place, result.mmmyy),
            OUT_DIR,
            used,
        )
        dest = OUT_DIR / name
        dest.write_bytes(path.read_bytes())
        print("wrote", name)
        assert name == want, f"{name} != {want}"

    clash = unique_filename("Challan-DG1-BDV2-MH-AUG26.pdf", OUT_DIR, used)
    assert clash == "Challan-DG1-BDV2-MH-AUG26-2.pdf"

    from namer import zip_name_for_batch

    assert zip_name_for_batch({"AUG26"}, 6) == "AUG26-6.zip"
    assert zip_name_for_batch({"AUG26", "SEP26"}, 6) is None
    assert zip_name_for_batch({"AUG26", "SEP26"}, 6, "Challans") == "Challans-6.zip"

    tmp_store = ROOT / "sample_pdfs" / "sku_mappings.json"
    save_sku_mappings({clock_result.products[0].lower(): "DG1"}, tmp_store)
    print("pipeline ok")


if __name__ == "__main__":
    main()
