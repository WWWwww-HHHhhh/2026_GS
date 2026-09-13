# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pypdf import PdfReader
import pandas as pd
from pathlib import Path

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\Data\raw\CUMCM2026_C")

print("########## C题.pdf page 1 ##########")
pdf = PdfReader(str(ROOT / "C题.pdf"))
print((pdf.pages[0].extract_text() or "").strip())

print("\n\n########## 附件4.xlsx ##########")
xl = pd.ExcelFile(ROOT / "附件/附件4.xlsx")
print("sheets:", xl.sheet_names)
for sh in xl.sheet_names:
    d = xl.parse(sh, header=None)
    print(f"\n--- {sh}: shape={d.shape} ---")
    print("head 5 rows x 8 cols:")
    print(d.iloc[:5, :8].to_string())
    print("tail 3 rows x 8 cols:")
    print(d.iloc[-3:, :8].to_string())
    num = d.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce')
    print("numeric stats: min=%.4f max=%.4f mean=%.4f  NaN=%d" % (num.min().min(), num.max().max(), num.mean().mean(), int(num.isna().sum().sum())))
