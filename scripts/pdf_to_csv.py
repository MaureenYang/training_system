#!/usr/bin/env python3
"""把《全新制 TOEIC 多益必考單字 3,000》PDF 轉成 data/vocab/words.csv

PDF 版面：每頁兩欄，每個條目長這樣（中文可能斷行接到下一行）：
    31. accent n 口音，腔調 v 強調，著重

用法：
    python3 scripts/pdf_to_csv.py data/vocab/source/toeic3000.pdf [-o data/vocab/words.csv]

輸出欄位：no, word, pos, zh
    pos: 詞性以 / 串接，例如 n/v
    zh : 依詞性分段，例如 「n. 口音，腔調｜v. 強調，著重」
同時把可疑條目（編號跳號、詞性缺漏、單字疑似錯字）印出來，方便人工檢查。
"""
import argparse
import csv
import os
import re
import sys

import pdfplumber

POS = ["prep", "conj", "pron", "aux", "art", "num", "int", "adv", "ad", "ph", "Ph", "n", "v", "a"]
POS_NORMALIZE = {"adv": "ad", "Ph": "ph"}
POS_RE = "|".join(POS)
ENTRY_RE = re.compile(r"^(\d{1,4})\.\s+(.*)$")
LETTER_RE = re.compile(r"^[A-Z]$")
# 中文解釋的開頭：非英文字元，或「X光」這種大寫字母緊接中文
ZH_START = r"(?:[^\sA-Za-z]|[A-Z][^\x00-\x7f])"
# 單字：英文字母開頭，可含空白、連字號、撇號、點（例如 a.m.）
SPLIT_RE = re.compile(rf"^(?P<word>[A-Za-zé][A-Za-zé.'’()\- ]*?)\s+(?P<rest>(?:{POS_RE})\s*{ZH_START}.*)$")
# 詞性標記：前面不是英文字母（可能緊貼中文標點，如「）prep 在」），後面接中文
SEG_RE = re.compile(rf"(?<![A-Za-z])({POS_RE})\s*(?={ZH_START})")

# 原書詞性標錯的條目：編號 → 修正後的欄位
ROW_FIXES = {
    949: {"word": "devise", "pos": "v", "zh": "v. 設計；發明"},
    1922: {"pos": "n/v", "zh": "n. 木材；木料｜v. 採伐"},
    2106: {"word": "outbound", "pos": "a", "zh": "a. 向外去的；駛向外國的"},
}

# 原書漏標詞性的條目
MISSING_POS = {"financial": "a", "lasting": "a"}

# 原書排版錯字的修正（人工檢查後加入）
CORRECTIONS = {
    "wo": "woo",
    "oom-out": "zoom-out",
    "vita": "vital",
}


def column_lines(page):
    """把一頁切成左右兩欄，依序回傳文字行。"""
    mid = page.width / 2
    out = []
    for bbox in ((0, 0, mid, page.height), (mid, 0, page.width, page.height)):
        text = page.crop(bbox).extract_text() or ""
        out.extend(l.strip() for l in text.splitlines() if l.strip())
    return out


def parse_entry(no, body):
    m = SPLIT_RE.match(body)
    if not m:
        word = body.split(" ", 1)[0]
        if word in MISSING_POS:
            m = SPLIT_RE.match(f"{word} {MISSING_POS[word]} {body.split(' ', 1)[1]}")
    if not m:
        return None
    word = m.group("word").strip()
    rest = m.group("rest")
    parts = SEG_RE.split(rest)
    # parts = ['', pos1, meaning1, pos2, meaning2, ...]
    segs = []
    for i in range(1, len(parts) - 1, 2):
        # 斷行造成的空白：中文旁邊的去掉，英文單字之間的保留一個
        meaning = re.sub(r"\s+", " ", parts[i + 1])
        meaning = re.sub(r"\s*([^\x00-\x7f])\s*", r"\1", meaning).strip("；;，, ")
        if meaning:
            segs.append((POS_NORMALIZE.get(parts[i], parts[i]), meaning))
    if not segs:
        return None
    word = CORRECTIONS.get(word, word)
    return {
        "no": no,
        "word": word,
        "pos": "/".join(p for p, _ in segs),
        "zh": "｜".join(f"{p}. {mean}" for p, mean in segs),
    }


def extract(pdf_path):
    raw = []  # [(no, body)]
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in column_lines(page):
                if LETTER_RE.match(line):
                    continue
                m = ENTRY_RE.match(line)
                if m:
                    raw.append([int(m.group(1)), m.group(2)])
                elif raw:
                    # 中文斷行接到上一條；若下一行是英文詞性開頭（如 prep / n），前面補空白
                    sep = " " if re.match(rf"^({POS_RE})\s", line) else ""
                    raw[-1][1] += sep + line
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "vocab", "words.csv"))
    args = ap.parse_args()

    raw = extract(args.pdf)
    rows, problems = [], []
    expected = 1
    for no, body in raw:
        if no != expected:
            problems.append(f"編號不連續：預期 {expected}，實際 {no}")
        expected = no + 1
        row = parse_entry(no, body)
        if row is None:
            problems.append(f"無法解析 #{no}: {body}")
            continue
        row.update(ROW_FIXES.get(no, {}))
        rows.append(row)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["no", "word", "pos", "zh"])
        w.writeheader()
        w.writerows(rows)

    print(f"寫入 {len(rows)} 個單字 → {os.path.normpath(args.out)}")
    if problems:
        print(f"\n需要人工檢查的條目（{len(problems)}）：")
        for p in problems:
            print("  -", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
