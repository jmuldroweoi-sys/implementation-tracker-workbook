"""Render the README screenshots from the bundled synthetic workbook.

The images in docs/images/ are pictures of the real workbook, not mock-ups: this script
copies the workbook, sets a print area on two tabs, has headless LibreOffice print the
copy to PDF (which calculates every formula), and turns the two pages into trimmed PNG
files. The committed workbook is never modified.

Requires LibreOffice (soffice), poppler (pdftoppm), and ImageMagick (convert).

Usage:
    python tools/render_screenshots.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["OPENPYXL_LXML"] = "False"

from openpyxl import load_workbook  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "workbook" / "implementation-tracker-workbook.xlsx"
OUT = ROOT / "docs" / "images"
# Tab, print area, output file. Sheets print in workbook order, so the page number of
# each tab is its position among the tabs that print.
SHOTS = (("Tasks", "A1:S34", "tasks-tab.png"), ("KPI Summary", "A1:S40", "kpi-summary.png"))


def main() -> int:
    for tool in ("soffice", "pdftoppm", "convert"):
        if not shutil.which(tool):
            print(f"{tool} is not installed", file=sys.stderr)
            return 2
    areas = {tab: area for tab, area, _ in SHOTS}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wb = load_workbook(WORKBOOK)
        printed = []
        for ws in wb.worksheets:
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 1
            ws.page_setup.paperSize = ws.PAPERSIZE_A3
            for side in ("left", "right", "top", "bottom"):
                setattr(ws.page_margins, side, 0.2)
            if ws.title in areas:
                ws.print_area = areas[ws.title]
                printed.append(ws.title)
            else:
                ws.sheet_state = "hidden"
        wb.save(tmp_path / "render.xlsx")
        profile = (tmp_path / "profile").as_uri()
        subprocess.run(["soffice", f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                        "--outdir", str(tmp_path), str(tmp_path / "render.xlsx")], check=True, capture_output=True)
        OUT.mkdir(parents=True, exist_ok=True)
        for tab, _area, name in SHOTS:
            page = printed.index(tab) + 1
            stem = tmp_path / f"page-{page}"
            subprocess.run(["pdftoppm", "-r", "130", "-png", "-singlefile", "-f", str(page), "-l", str(page),
                            str(tmp_path / "render.pdf"), str(stem)], check=True)
            subprocess.run(["convert", f"{stem}.png", "-trim", "+repage", "-bordercolor", "white", "-border", "14",
                            "-strip", str(OUT / name)], check=True)
            print(f"wrote docs/images/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
