# -*- coding: utf-8 -*-
"""Intake check: read C题.pdf + 附件2/附件4 + 附件5/result4-2.xlsx (read-only)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pypdf import PdfReader
import pandas as pd
from pathlib import Path

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\Data\raw\CUMCM2026_C")

print("=" * 80)
print("PDF: C题.pdf")
print("=" * 80)
pdf = PdfReader(str(ROOT / "C题.pdf"))
print("pages:", len(pdf.pages))
for i, p in enumerate(pdf.pages):
    t = p.extract_text() or ""
    print(f"\n----- page {i+1} -----")
    print(t.strip())


def dump_xlsx(path: Path, max_rows=8):
    print("\n" + "=" * 80)
    print("XLSX:", path.name)
    print("=" * 80)
    xl = pd.ExcelFile(path)
    print("sheets:", xl.sheet_names)
    for sh in xl.sheet_names:
        df = xl.parse(sh, header=None, nrows=20)
        full = xl.parse(sh, header=None)
        print(f"\n--- sheet [{sh}] shape={full.shape} ---")
        with pd.option_context('display.max_columns', 30, 'display.width', 250):
            print(df.head(max_rows).to_string())


for f in ["附件/附件2.xlsx", "附件/附件4.xlsx", "附件/附件5/result4-2.xlsx"]:
    dump_xlsx(ROOT / f)
