from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


CLOCK_DESCRIPTION = (
    "ACCORD CLOCKS Large Digital Wall Clock 14 Inch - Battery Operated (No Wires), "
    "Big Display with Alarms, Day & Date (Indian Format), Room Temperature -Plastic,"
    "White (with Backlight)"
)

LAMP_DESCRIPTION = (
    "NIGHT LAMP LED Bedside Lamp with Touch Control, Warm White Light, USB Rechargeable"
)


def build_sample_challan(
    path: Path,
    *,
    document_number: str = "FBA15M3SBDV2",
    document_date: str = "08/25/2026",
    place_name: str = "Maharashtra",
    gst_code: str = "27",
    products: list[tuple[str, int]] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    products = products or [(CLOCK_DESCRIPTION, 20)]
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>DELIVERY CHALLAN/ TAX INVOICE</b>", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            f"<b>Place of supply :</b> {place_name} (State/UT Code: {gst_code})",
            styles["Normal"],
        ),
        Paragraph(f"<b>Document Number</b>    {document_number}", styles["Normal"]),
        Paragraph(f"<b>FBA Shipment ID</b>    {document_number}", styles["Normal"]),
        Paragraph(f"<b>Document Date</b>    {document_date}", styles["Normal"]),
        Paragraph("<b>Purpose of transfer</b>    Stock Transfer", styles["Normal"]),
        Spacer(1, 16),
    ]

    table_data = [
        [
            "Sno",
            "Product Description",
            "Qty",
            "Unit Value (INR)",
            "HSN / SAC Code",
        ]
    ]
    for index, (description, qty) in enumerate(products, start=1):
        table_data.append(
            [str(index), Paragraph(description, styles["Normal"]), str(qty), "1,779.66", "9105"]
        )
    table_data.append(["", "Total", str(sum(qty for _, qty in products)), "1,779.66", ""])

    table = Table(table_data, colWidths=[40, 280, 40, 90, 80])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Total Value of Goods Incl. Tax : 42,000.00", styles["Normal"]))
    story.append(Spacer(1, 18))
    story.append(Paragraph("<b>Declaration</b>", styles["Heading2"]))
    story.append(Paragraph("We declare that the above mentioned details are true.", styles["Normal"]))

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    doc.build(story)
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "sample_pdfs"
    build_sample_challan(out / "clock_mh.pdf")
    print(f"Wrote sample PDFs to {out}")
