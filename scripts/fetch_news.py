#!/usr/bin/env python3
"""抓 OpenAI / Anthropic / DeepSeek / Qwen / GLM 的最新消息，整理成中文摘要與技術演變時間軸。

來源設定在 config.json 的 news.sources，type 支援：
    rss        RSS / Atom feed
    sitemap    網站 sitemap.xml，用 include 篩選路徑（例如 /news/）
    hf_models  Hugging Face 某組織新上架的模型（開源權重）
    page_diff  沒有 feed 的頁面：和上次快照比對，有新增內容就當成一則更新

輸出：
    data/news/items.json      所有已整理的消息（新的在前）＋各來源已看過的網址
    data/news/timeline.json   最近 N 天各家公司的技術演變整理
    data/news/snapshots/      page_diff 的頁面快照

用法：
    python3 scripts/fetch_news.py
    python3 scripts/fetch_news.py --no-timeline
"""
import argparse
import datetime as dt
import email.utils
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONFIG, DATA, claude_json, has_api_key, log, read_json, today, write_json  # noqa: E402

NEWS_DIR = os.path.join(DATA, "news")
ITEMS_PATH = os.path.join(NEWS_DIR, "items.json")
TIMELINE_PATH = os.path.join(NEWS_DIR, "timeline.json")
SNAP_DIR = os.path.join(NEWS_DIR, "snapshots")
UA = "Mozilla/5.0 (compatible; training-system-news/1.0; +https://github.com/MaureenYang/training_system)"
MAX_ITEMS_KEPT = 600


# ------------------------------------------------------------------ HTTP / HTML

def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,zh-TW;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "section", "article", "time"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
        self.meta = {}
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta[key.lower()] = a["content"]
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def parse_html(html):
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:  # 壞掉的 HTML 也盡量拿到部分內容
        pass
    text = "".join(p.parts)
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    title = p.meta.get("og:title") or p.title.strip()
    date = p.meta.get("article:published_time") or p.meta.get("og:published_time") or ""
    desc = p.meta.get("og:description") or p.meta.get("description") or ""
    return {"title": title, "date": date[:10], "description": desc, "lines": lines}


def page_text(url, limit=5000):
    try:
        info = parse_html(http_get(url))
    except Exception as e:
        log(f"    讀取內文失敗 {url}: {e}")
        return None
    info["text"] = "\n".join(info["lines"])[:limit]
    return info


def norm_date(s):
    if not s:
        return ""
    s = s.strip()
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        pass
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else ""


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------------------------------------------------------------- 各種來源

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def fetch_rss(src):
    root = ET.fromstring(http_get(src["url"]))
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            name = _local(c.tag)
            if name == "link":
                f.setdefault("link", c.get("href") or (c.text or "").strip())
            else:
                f.setdefault(name, (c.text or "").strip())
        link = f.get("link")
        if not link:
            continue
        out.append({
            "key": link,
            "url": link,
            "title": strip_tags(f.get("title", "")),
            "date": norm_date(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date")),
            "snippet": strip_tags(f.get("description") or f.get("summary") or f.get("content", ""))[:1500],
        })
    return out


def fetch_sitemap(src):
    root = ET.fromstring(http_get(src["url"]))
    out = []
    for url_el in root.iter():
        if _local(url_el.tag) != "url":
            continue
        loc = lastmod = ""
        for c in url_el:
            if _local(c.tag) == "loc":
                loc = (c.text or "").strip()
            elif _local(c.tag) == "lastmod":
                lastmod = (c.text or "").strip()
        path = urllib.parse.urlparse(loc).path
        # 只要文章頁，不要 /news/ 這種列表頁本身
        if not any(path.startswith(p) and len(path) > len(p) for p in src.get("include", [])):
            continue
        out.append({"key": loc, "url": loc, "title": "", "date": lastmod[:10], "snippet": ""})
    # 有 lastmod 的排前面（新到舊）
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


_HF_NOISE = re.compile(
    r"[-_](\d+(\.\d+)?[BbMm](-A\d+(\.\d+)?B)?|Instruct|Chat|Base|GGUF|AWQ|GPTQ|FP8|FP4|INT4|INT8|BF16|"
    r"MLX|Thinking|Distill|\d{4}|bnb|4bit|8bit|MoE)(?=$|[-_])",
    re.I,
)


def _hf_family(model_id):
    name = model_id.split("/", 1)[1]
    prev = None
    while prev != name:
        prev = name
        name = _HF_NOISE.sub("", name)
    return name


def fetch_hf_models(src):
    author = src["author"]
    url = f"https://huggingface.co/api/models?author={urllib.parse.quote(author)}&sort=createdAt&direction=-1&limit=40"
    models = json.loads(http_get(url))
    groups = {}
    for m in models:
        mid = m.get("id") or m.get("modelId")
        created = (m.get("createdAt") or "")[:10]
        key = f"hf:{author}:{_hf_family(mid)}:{created}"
        groups.setdefault(key, {"created": created, "ids": []})["ids"].append(mid)
    out = []
    for key, g in groups.items():
        ids = g["ids"]
        family = _hf_family(ids[0])
        out.append({
            "key": key,
            "url": f"https://huggingface.co/{ids[0]}",
            "title": f"{author} 新權重上架：{family}" + (f"（共 {len(ids)} 個版本）" if len(ids) > 1 else ""),
            "date": g["created"],
            "snippet": "版本：" + "、".join(ids[:12]),
            "hf_ids": ids[:12],
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def hf_details(model_id):
    """取參數量、授權、下載數，並檢查是否有 GGUF 量化版（地端可跑的指標）。"""
    info = {}
    try:
        d = json.loads(http_get(f"https://huggingface.co/api/models/{model_id}"))
        params = (d.get("safetensors") or {}).get("total")
        if params:
            info["params_b"] = round(params / 1e9, 1)
        card = d.get("cardData") or {}
        info["license"] = card.get("license") or ""
        info["downloads"] = d.get("downloads", 0)
        info["pipeline"] = d.get("pipeline_tag") or ""
    except Exception as e:
        log(f"    HF 詳細資料失敗 {model_id}: {e}")
    try:
        name = model_id.split("/", 1)[1]
        q = json.loads(http_get(
            f"https://huggingface.co/api/models?search={urllib.parse.quote(name)}&filter=gguf&limit=5"))
        info["gguf"] = [m.get("id") for m in q][:3]
    except Exception:
        info["gguf"] = []
    return info


def fetch_page_diff(src):
    """和上次快照比對，回傳新增的行組成的一則更新（第一次只存快照）。"""
    info = parse_html(http_get(src["url"]))
    lines = info["lines"]
    snap_path = os.path.join(SNAP_DIR, f"{src['id']}.txt")
    old = None
    if os.path.exists(snap_path):
        with open(snap_path, encoding="utf-8") as f:
            old = set(f.read().splitlines())
    os.makedirs(SNAP_DIR, exist_ok=True)
    with open(snap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if old is None:
        log(f"    {src['id']}: 第一次執行，建立快照")
        return []
    new_lines = [l for l in lines if l not in old and len(l) > 3]
    if sum(len(l) for l in new_lines) < 80:
        return []
    d = today().isoformat()
    return [{
        "key": f"{src['url']}#{d}",
        "url": src["url"],
        "title": src.get("title") or info["title"],
        "date": d,
        "snippet": "\n".join(new_lines)[:4000],
        "is_diff": True,
    }]


FETCHERS = {"rss": fetch_rss, "sitemap": fetch_sitemap, "hf_models": fetch_hf_models, "page_diff": fetch_page_diff}


# ---------------------------------------------------------------- Claude 整理

TAGS = ["模型發表", "開源權重", "API與工具", "Agent", "安全與對齊", "產品", "研究", "基礎設施", "商業合作"]

ITEM_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "title_zh": {"type": "string"},
            "points": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
            "trend": {"type": "string"},
            "importance": {"type": "integer"},
            "local": {"type": "object", "properties": {
                "runnable": {"type": "string"},
                "vram": {"type": "string"},
                "note": {"type": "string"},
            }, "required": ["runnable", "vram", "note"], "additionalProperties": False},
        },
        "required": ["key", "title_zh", "points", "tags", "trend", "importance", "local"],
        "additionalProperties": False,
    }}},
    "required": ["items"],
    "additionalProperties": False,
}

ITEM_SYSTEM = (
    "你是 AI 產業分析師，幫一位正在轉職、學 C++ 與資料結構的工程師追蹤大型語言模型公司的技術演變。"
    "用台灣繁體中文、精準、不誇大；技術名詞保留英文（例如 MoE、context window、tool use）。"
    "只根據提供的內容整理，內容不足時就寫得保守，不要編造數字。"
)


def summarize(new_items):
    blocks = []
    for it in new_items:
        extra = ""
        if it.get("hf"):
            extra = f"\nHF 資訊：{json.dumps(it['hf'], ensure_ascii=False)}"
        blocks.append(
            f"<item key=\"{it['key']}\" company=\"{it['company']}\" open_weights=\"{it.get('open_weights', False)}\">\n"
            f"標題：{it['title']}\n日期：{it['date']}\n網址：{it['url']}{extra}\n內容：\n{it.get('content') or it.get('snippet') or '(無內文)'}\n</item>"
        )
    prompt = (
        "以下是今天抓到的新消息。請逐則整理（key 原樣帶回）：\n"
        "- title_zh：中文標題（20 字內）\n"
        "- points：3–5 點重點，每點一句\n"
        "- tags：從給定分類選 1–3 個\n"
        "- trend：一句話說明這代表什麼技術趨勢或演變（例如：從聊天走向 agent、推理模型成本下降）\n"
        "- importance：1–5，對了解 LLM 技術演變的重要程度（新模型/重大能力=4–5，小更新=1–2）\n"
        "- local：只有開源權重模型才填，runnable 填「可」「需高階 GPU」「僅伺服器級」之一，"
        "vram 估計（例如 4-bit 約 20GB），note 補充 GGUF/Ollama 等地端資訊；非開源權重三個欄位都填空字串\n"
        "- 若內容只是無關緊要的頁面變動（例如導覽、徵才、法律條款），importance 填 0\n\n"
        + "\n\n".join(blocks)
    )
    res = claude_json(prompt, ITEM_SCHEMA, system=ITEM_SYSTEM, max_tokens=32000)
    return {r["key"]: r for r in (res or {}).get("items", [])}


TIMELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "companies": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "summary": {"type": "string"},
                "themes": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"theme": {"type": "string"}, "evolution": {"type": "string"}},
                    "required": ["theme", "evolution"], "additionalProperties": False,
                }},
            },
            "required": ["company", "summary", "themes"], "additionalProperties": False,
        }},
        "open_vs_closed": {"type": "string"},
        "watch_next": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "companies", "open_vs_closed", "watch_next"],
    "additionalProperties": False,
}


def build_timeline(items, days):
    since = (today() - dt.timedelta(days=days)).isoformat()
    recent = [i for i in items if i.get("date", "") >= since and i.get("importance", 1) > 0]
    if not recent:
        return None
    lines = []
    for i in recent[:120]:
        pts = "；".join(i.get("points", [])[:3])
        lines.append(f"- [{i['date']}] {i['company']}｜{i.get('title_zh') or i['title']}｜{pts}｜趨勢：{i.get('trend', '')}")
    companies = sorted({s["company"] for s in CONFIG["news"]["sources"]})
    prompt = (
        f"以下是最近 {days} 天 {', '.join(companies)} 的消息摘要（新到舊）：\n\n" + "\n".join(lines) +
        "\n\n請整理「技術演變」：\n"
        "- headline：一句話總結這段期間最重要的變化\n"
        f"- companies：依序為 {', '.join(companies)}，每家一個 summary（2–3 句）和 2–4 個 themes，"
        "theme 例如「推理模型」「Agent/工具使用」「Context 長度」「多模態」「MoE/小模型」「授權與開放」「開發者平台」，"
        "evolution 寫這段期間在該主題的具體演進（引用日期與產品名）；沒有消息的公司 summary 寫「本期無重大更新」、themes 留空\n"
        "- open_vs_closed：閉源（OpenAI、Anthropic）與開源權重（DeepSeek、Qwen、GLM）之間的差距與互動，3–4 句\n"
        "- watch_next：接下來值得關注的 3 件事\n"
    )
    res = claude_json(prompt, TIMELINE_SCHEMA, system=ITEM_SYSTEM, max_tokens=16000)
    if res:
        res.update(date=today().isoformat(), days=days, count=len(recent))
    return res


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-timeline", action="store_true")
    args = ap.parse_args()

    ncfg = CONFIG["news"]
    store = read_json(ITEMS_PATH, {"seen": {}, "items": []})
    seen = {k: set(v) for k, v in store["seen"].items()}
    candidates = []

    for src in ncfg["sources"]:
        sid = src["id"]
        try:
            found = FETCHERS[src["type"]](src)
        except Exception as e:
            log(f"[{sid}] 抓取失敗：{e}")
            continue
        first_run = sid not in seen
        s = seen.setdefault(sid, set())
        fresh = [f for f in found if f["key"] not in s]
        if first_run and src["type"] != "page_diff":
            fresh = fresh[: ncfg["first_run_backfill_per_source"]]
        log(f"[{sid}] 共 {len(found)} 則，新的 {len(fresh)} 則")
        s.update(f["key"] for f in found)
        for f in fresh:
            f.update(company=src["company"], source=sid, open_weights=src.get("open_weights", False))
            candidates.append(f)

    # 上次沒摘要到的（例如當時沒有金鑰）這次補做
    pending = [i for i in store["items"] if i.get("pending")]
    if pending and has_api_key():
        store["items"] = [i for i in store["items"] if not i.get("pending")]
        for i in pending:
            i["snippet"] = "\n".join(i.get("points", []))
            candidates.append(i)

    # 新到舊，限制每次整理的數量（控制 API 成本）；超過的下次不再補
    candidates.sort(key=lambda x: x.get("date", ""), reverse=True)
    batch = candidates[: ncfg["max_new_summaries_per_run"]]
    for it in batch:
        if it.get("is_diff"):
            continue
        if it.get("hf_ids"):
            it["hf"] = hf_details(it["hf_ids"][0])
            continue
        info = page_text(it["url"])
        if info:
            it["title"] = it["title"] or info["title"]
            it["date"] = it["date"] or info["date"]
            it["content"] = (info["description"] + "\n" + info["text"]).strip()
        if not it["title"]:
            it["title"] = urllib.parse.urlparse(it["url"]).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")

    summaries = summarize(batch) if batch else {}
    new_items = []
    for it in batch:
        s = summaries.get(it["key"], {})
        if s.get("importance") == 0:
            continue
        rec = {k: it.get(k) for k in ("key", "company", "source", "url", "title", "date", "open_weights", "hf_ids")}
        rec = {k: v for k, v in rec.items() if v is not None}
        rec["date"] = rec["date"] or today().isoformat()
        rec["fetched"] = today().isoformat()
        if s:
            rec.update(title_zh=s["title_zh"], points=s["points"], tags=s["tags"],
                       trend=s["trend"], importance=s["importance"])
            if it.get("open_weights") and s["local"]["runnable"]:
                rec["local"] = s["local"]
        else:
            rec["points"] = [it["snippet"][:200]] if it.get("snippet") else []
            rec["pending"] = True
        if it.get("hf"):
            rec["hf"] = it["hf"]
        new_items.append(rec)

    items = new_items + store["items"]
    items.sort(key=lambda x: (x.get("date", ""), x.get("importance", 0)), reverse=True)
    store = {"updated": today().isoformat(), "seen": {k: sorted(v) for k, v in seen.items()},
             "items": items[:MAX_ITEMS_KEPT]}
    write_json(ITEMS_PATH, store)
    log(f"新增 {len(new_items)} 則，共 {len(store['items'])} 則")

    if not args.no_timeline:
        old = read_json(TIMELINE_PATH, {})
        if new_items or old.get("date") != today().isoformat():
            tl = build_timeline(store["items"], ncfg["timeline_days"])
            if tl:
                write_json(TIMELINE_PATH, tl)
                log("已更新技術演變時間軸")


if __name__ == "__main__":
    main()
