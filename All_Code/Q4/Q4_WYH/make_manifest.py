"""生成 Q4_WYH 的全目录清单 MANIFEST.md（大小与 sha256 前 12 位）。"""

import io
import os
import hashlib

NEW = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {"MANIFEST.md"}


def sha(path, n=12):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def main():
    rows = []
    for r, ds, fs in os.walk(NEW):
        ds[:] = [d for d in ds if d not in SKIP_DIRS]
        for f in fs:
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            fp = os.path.join(r, f)
            rows.append((os.path.relpath(fp, NEW).replace(os.sep, "/"), os.path.getsize(fp), sha(fp)))
    rows.sort()

    L = ["# Q4_WYH 文件清单", "",
         "共 %d 个文件，合计 %.2f MB。" % (len(rows), sum(s for _p, s, _h in rows) / 1048576), "",
         "| 文件 | 大小(B) | sha256[:12] |", "| --- | --- | --- |"]
    for p, s, h in rows:
        L.append("| `%s` | %d | `%s` |" % (p, s, h))
    io.open(os.path.join(NEW, "MANIFEST.md"), "w", encoding="utf-8", newline="").write("\n".join(L) + "\n")
    print("manifest:", len(rows), "files, %.2f MB" % (sum(s for _p, s, _h in rows) / 1048576))


if __name__ == "__main__":
    main()
