from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from sample_pdf import CLOCK_DESCRIPTION, build_sample_challan


def test_app_upload_sku_and_rename(tmp_path: Path) -> None:
    sample = build_sample_challan(tmp_path / "clock_mh.pdf")
    at = AppTest.from_file("app.py", default_timeout=15)
    at.session_state["selected_paths"] = [str(sample)]
    at.session_state["file_ids"] = None
    at.run()

    sku_inputs = [widget for widget in at.text_input if widget.label == CLOCK_DESCRIPTION]
    assert sku_inputs, [widget.label for widget in at.text_input]
    sku_inputs[0].set_value("DG1").run()

    rename = [button for button in at.button if "Rename" in button.label]
    assert rename
    rename[0].click().run()

    assert any("Renamed" in el.value for el in at.success)
    assert not sample.exists()
    written = list(tmp_path.glob("Challan-*.pdf"))
    assert written
    assert written[0].name == "Challan-DG1-BDV2-MH-AUG26.pdf"


if __name__ == "__main__":
    out = Path("sample_pdfs") / "apptest"
    out.mkdir(parents=True, exist_ok=True)
    for leftover in out.glob("*.pdf"):
        leftover.unlink()
    test_app_upload_sku_and_rename(out)
    print("app test ok")
