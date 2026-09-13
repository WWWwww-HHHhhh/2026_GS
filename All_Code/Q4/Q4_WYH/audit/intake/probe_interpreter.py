# -*- coding: utf-8 -*-
"""探测哪个解释器能反序列化 Q2_yy 的 forecasts.pkl（含 pandas DataFrame）。"""
import sys, pickle, pathlib
print("exe:", sys.executable)
try:
    import pandas, numpy
    print("pandas", pandas.__version__, "numpy", numpy.__version__)
except Exception as e:  # noqa: BLE001
    print("no pandas:", e)
    raise SystemExit(0)

p = pathlib.Path(__file__).resolve().parents[4] / "Q2_yy" / "Data_processing" / "forecasts.pkl"
print("target:", p, p.exists())
try:
    with open(p, "rb") as fh:
        d = pickle.load(fh)
    print("LOAD OK, keys:", list(d.keys()))
    print("Lhat", d["Lhat"].shape, "Ghat", d["Ghat"].shape)
except Exception as e:  # noqa: BLE001
    print("LOAD FAIL:", type(e).__name__, e)

q2 = p.parent / "q2_dataset.pkl"
try:
    with open(q2, "rb") as fh:
        d2 = pickle.load(fh)
    print("q2_dataset LOAD OK, keys:", list(d2.keys())[:12])
    print("kappa2_base:", d2.get("kappa2_base"))
except Exception as e:  # noqa: BLE001
    print("q2_dataset LOAD FAIL:", type(e).__name__, e)
