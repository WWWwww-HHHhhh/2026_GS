# -*- coding: utf-8 -*-
"""尝试用 pandas 兼容补丁读取 Q2_yy 的 forecasts.pkl（仅取 numpy 数组 Lhat/Ghat）。"""
import sys, pickle, pathlib

p = pathlib.Path(__file__).resolve().parents[4] / "Q2_yy" / "Data_processing" / "forecasts.pkl"

import pandas as pd
from pandas.core.internals import blocks as _blocks
from pandas.core.internals.blocks import BlockPlacement

_orig_new_block = _blocks.new_block


def _patched_new_block(values, placement, ndim=2, refs=None):
    if isinstance(placement, slice):
        placement = BlockPlacement(placement)
    elif isinstance(placement, (list, tuple, range)) or hasattr(placement, "__iter__"):
        try:
            placement = BlockPlacement(list(placement))
        except Exception:
            placement = BlockPlacement(slice(0, len(values)))
    return _orig_new_block(values, placement, ndim=ndim, refs=refs)


_blocks.new_block = _patched_new_block
try:
    import pandas.core.internals.managers as _mgr
    if hasattr(_mgr, "new_block"):
        _mgr.new_block = _patched_new_block
except Exception as e:  # noqa: BLE001
    print("managers patch skipped:", e)

try:
    with open(p, "rb") as fh:
        d = pickle.load(fh)
    print("LOAD OK, keys:", list(d.keys()))
    for k, v in d.items():
        print("  ", k, type(v).__name__, getattr(v, "shape", ""))
except Exception as e:  # noqa: BLE001
    print("STILL FAIL:", type(e).__name__, e)
    print("--- 退化方案：只提取 numpy 数组 ---")
    import io
    import numpy as np

    class OnlyArrays(pickle.Unpickler):
        def find_class(self, module, name):
            if module.startswith("pandas") or module.startswith("numpy._core") or module.startswith("numpy.core"):
                if module.startswith("numpy"):
                    return super().find_class(module, name)
                class _Stub:
                    def __init__(self, *a, **k):
                        pass
                    def __setstate__(self, state):
                        pass
                    def __reduce__(self):
                        return (_Stub, ())
                return _Stub
            return super().find_class(module, name)

    try:
        with open(p, "rb") as fh:
            d2 = OnlyArrays(fh).load()
        print("stub LOAD keys:", list(d2.keys()) if isinstance(d2, dict) else type(d2))
    except Exception as e2:  # noqa: BLE001
        print("stub FAIL:", type(e2).__name__, e2)
