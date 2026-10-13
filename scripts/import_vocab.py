#!/usr/bin/env python3
"""把單字表（CSV/TSV/XLSX）匯入並平均分配到 N 天。

用法：
    python3 scripts/import_vocab.py data/vocab/words.csv

欄位（大小寫、中英文欄名都可）：
    word / 單字 （必要）
    zh / 中文 / 解釋 / meaning （必要）
    pos / 詞性 （選填）
    no / 編號 （選填）

輸出：
    data/vocab/words.json      全部單字（含 id）
    data/vocab/schedule.json   {"days": [[id, id, ...], ...]} 第 1 天到第 N 天
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONFIG, DATA, write_json  # noqa: E402

ALIASES = {
    "word": ["word", "單字", "英文", "vocabulary", "vocab"],
    "zh": ["zh", "中文", "解釋", "meaning", "中文解釋", "translation"],
    "pos": ["pos", "詞性", "part of speech"],
    "no": ["no", "編號", "id", "#"],
}


def read_rows(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl

        ws = openpyxl.load_workbook(path, read_only=True).active
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip() for h in next(it)]
        return [dict(zip(header, ["" if v is None else str(v) for v in r])) for r in it]
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        return list(csv.DictReader(f, dialect=dialect))


def map_columns(header):
    lower = {h.strip().lower(): h for h in header}
    out = {}
    for key, names in ALIASES.items():
        for n in names:
            if n.lower() in lower:
                out[key] = lower[n.lower()]
                break
    missing = [k for k in ("word", "zh") if k not in out]
    if missing:
        sys.exit(f"找不到必要欄位 {missing}；現有欄位：{header}")
    return out


def split_days(n_items, n_days):
    """把 n_items 平均切成 n_days 份，回傳每份的 (start, end)。"""
    base, extra = divmod(n_items, n_days)
    out, start = [], 0
    for d in range(n_days):
        size = base + (1 if d < extra else 0)
        out.append((start, start + size))
        start += size
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--days", type=int, default=CONFIG["english_days"])
    args = ap.parse_args()

    rows = read_rows(args.file)
    if not rows:
        sys.exit("檔案是空的")
    cols = map_columns(rows[0].keys())

    words, seen = [], set()
    for r in rows:
        w = (r.get(cols["word"]) or "").strip()
        if not w or w.lower() in seen:
            continue
        seen.add(w.lower())
        words.append({
            "id": len(words) + 1,
            "word": w,
            "pos": (r.get(cols.get("pos", ""), "") or "").strip(),
            "zh": (r.get(cols["zh"]) or "").strip(),
        })

    days = [[w["id"] for w in words[a:b]] for a, b in split_days(len(words), args.days)]
    write_json(os.path.join(DATA, "vocab", "words.json"), words)
    write_json(os.path.join(DATA, "vocab", "schedule.json"), {"days": days})
    sizes = [len(d) for d in days]
    print(f"匯入 {len(words)} 個單字，分成 {args.days} 天（每天 {min(sizes)}–{max(sizes)} 個）")


if __name__ == "__main__":
    main()
