#!/usr/bin/env python3
"""產生每天的 TOEIC 英文內容 → data/english/day-NN.json

每天的單字來自 data/vocab/schedule.json（由 import_vocab.py 產生）。
有 ANTHROPIC_API_KEY 時，用 Claude 產生：音標、商務例句、搭配詞、片語、考題、短篇閱讀。
沒有金鑰或生成失敗時，先存「只有單字卡」的版本，下次執行會再補生成。

用法：
    python3 scripts/gen_english.py            # 今天和明天（已生成的會跳過）
    python3 scripts/gen_english.py --day 5    # 指定第 5 天
    python3 scripts/gen_english.py --all      # 一次生成全部 30 天
    python3 scripts/gen_english.py --day 5 --force   # 重新生成
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONFIG, DATA, claude_json, day_number, log, read_json, start_date, today, write_json  # noqa: E402

import datetime as dt  # noqa: E402

EN_DIR = os.path.join(DATA, "english")

SYSTEM = (
    "你是專業的 TOEIC 多益老師，學生的目標是金色證書（860 分以上），母語是繁體中文（台灣）。"
    "所有中文請用台灣繁體中文。例句與文章要貼近多益的職場與日常商務情境"
    "（辦公室、會議、人資、行銷、出差、採購、客服、財務、製造），自然、道地、難度接近真實考題。"
)


def _obj(props, required=None):
    return {
        "type": "object",
        "properties": props,
        "required": required or list(props),
        "additionalProperties": False,
    }


S = {"type": "string"}
MCQ = _obj({
    "question": S,
    "options": {"type": "array", "items": S},
    "answer": {"type": "integer"},
    "explanation_zh": S,
})

SCHEMA = _obj({
    "words": {"type": "array", "items": _obj({
        "word": S,
        "kk": S,
        "example_en": S,
        "example_zh": S,
        "collocation": S,
    })},
    "phrases": {"type": "array", "items": _obj({
        "phrase": S,
        "zh": S,
        "example_en": S,
        "example_zh": S,
    })},
    "quiz": {"type": "array", "items": _obj({
        "kind": {"type": "string", "enum": ["part5", "vocab", "phrase"]},
        "question": S,
        "options": {"type": "array", "items": S},
        "answer": {"type": "integer"},
        "explanation_zh": S,
    })},
    "reading": _obj({
        "title": S,
        "genre": S,
        "text": S,
        "translation_zh": S,
        "questions": {"type": "array", "items": MCQ},
    }),
})


def build_prompt(day, words):
    lines = "\n".join(f"- {w['word']} ({w['pos']}) {w['zh']}" for w in words)
    return f"""這是 30 天背完 3000 個多益必考單字計畫的第 {day} 天，今天的 {len(words)} 個單字如下（含書上的詞性與中文）：

{lines}

請產生今天的學習內容：

1. words：上面「每一個」單字都要有一筆，順序相同，word 欄位與上面完全一致。
   - kk：KK 音標（例如 /əˈbændən/）
   - example_en：一句多益情境的英文例句（15–25 字，一定要包含該單字或其變化形）
   - example_zh：例句的中文翻譯
   - collocation：常見搭配詞或同義字，例如「abandon a plan / 同 give up」
2. phrases：從今天的單字延伸出 8 個多益常考片語或固定用法（例如 be accountable for），附中文、例句與翻譯。
3. quiz：15 題四選一，options 恰好 4 個（不要加 A/B/C/D 前綴），answer 是正確選項的索引（0–3）：
   - 10 題 kind="part5"：多益 Part 5 句子填空（空格用 ____），考詞性變化、搭配、語意，正解要是今天的單字
   - 3 題 kind="vocab"：近義字或語意辨析
   - 2 題 kind="phrase"：考今天的片語
   - explanation_zh：中文解析，說明為何正確、其他選項為何錯
   - 正確答案的位置要平均分散，不要集中在同一個選項
4. reading：一篇多益 Part 7 風格的短文（email、公告、廣告、備忘錄或文章擇一，寫在 genre），
   180–250 字，盡量自然地用到今天 10 個以上的單字和 2 個以上的片語；
   附 translation_zh（全文中文翻譯）與 3 題閱讀測驗（questions，格式同上）。
"""


def validate(content, words):
    if len(content["words"]) != len(words):
        return f"words 數量 {len(content['words'])} ≠ {len(words)}"
    for q in content["quiz"] + content["reading"]["questions"]:
        if len(q["options"]) != 4 or not 0 <= q["answer"] < 4:
            return "選項或答案格式錯誤"
    if len(content["quiz"]) < 10:
        return "考題太少"
    return None


def generate_day(day, force=False):
    path = os.path.join(EN_DIR, f"day-{day:02d}.json")
    existing = read_json(path)
    if existing and existing.get("generated") and not force:
        log(f"Day {day}: 已存在，略過")
        return existing

    schedule = read_json(os.path.join(DATA, "vocab", "schedule.json"))
    words_all = read_json(os.path.join(DATA, "vocab", "words.json"))
    if not schedule or not words_all:
        sys.exit("找不到單字表，請先執行 scripts/import_vocab.py")
    by_id = {w["id"]: w for w in words_all}
    words = [by_id[i] for i in schedule["days"][day - 1]]

    log(f"Day {day}: 生成 {len(words)} 個單字的內容 …")
    content = None
    for attempt in range(2):
        content = claude_json(build_prompt(day, words), SCHEMA, system=SYSTEM, max_tokens=48000)
        if content is None:
            break
        err = validate(content, words)
        if not err:
            break
        log(f"  第 {attempt + 1} 次生成格式不符：{err}")
        content = None

    date = start_date() + dt.timedelta(days=day - 1)
    out = {"day": day, "date": date.isoformat(), "generated": content is not None}
    if content:
        merged = []
        for w, extra in zip(words, content["words"]):
            item = dict(w)
            item.update({k: v for k, v in extra.items() if k != "word"})
            merged.append(item)
        out.update(words=merged, phrases=content["phrases"], quiz=content["quiz"], reading=content["reading"])
    else:
        out.update(words=words, phrases=[], quiz=[], reading=None)
    write_json(path, out)
    log(f"  → {os.path.relpath(path)}（{'完整' if out['generated'] else '只有單字卡'}）")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    n = CONFIG["english_days"]
    if args.all:
        days = range(1, n + 1)
    elif args.day:
        days = [args.day]
    else:
        d = day_number(today())
        # 開始前先準備第 1 天；30 天後進入複習，不再生成新內容
        days = [x for x in (max(d, 1), max(d, 1) + 1) if 1 <= x <= n]
    for d in days:
        generate_day(d, force=args.force)


if __name__ == "__main__":
    main()
