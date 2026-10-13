#!/usr/bin/env python3
"""組合要發佈到 GitHub Pages 的網站 → _site/

    python3 scripts/build_site.py
    python3 -m http.server -d _site 8080     # 本機預覽 http://127.0.0.1:8080
"""
import datetime as dt
import os
import shutil
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONFIG, DATA, ROOT, read_json, write_json  # noqa: E402

OUT = os.path.join(ROOT, "_site")


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "site"), OUT)
    out_data = os.path.join(OUT, "data")
    os.makedirs(out_data)
    # 只發佈網頁會用到的資料（不含單字原始檔、新聞快照）
    for sub in ("english", "coding"):
        src = os.path.join(DATA, sub)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(out_data, sub))
    os.makedirs(os.path.join(out_data, "news"))
    for name in ("items.json", "timeline.json"):
        src = os.path.join(DATA, "news", name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out_data, "news", name))

    words = read_json(os.path.join(DATA, "vocab", "words.json"), [])
    now = dt.datetime.now(ZoneInfo(CONFIG["timezone"]))
    write_json(os.path.join(out_data, "meta.json"), {
        "start_date": CONFIG["start_date"],
        "timezone": CONFIG["timezone"],
        "english_days": CONFIG["english_days"],
        "coding_weeks": CONFIG["coding_weeks"],
        "total_words": len(words),
        "updated": now.strftime("%Y-%m-%d %H:%M"),
    })
    print(f"網站已輸出到 {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
