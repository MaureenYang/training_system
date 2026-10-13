"""共用工具：設定檔、日期換算、JSON 讀寫、Claude API 呼叫。"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load_dotenv():
    """本機測試用：讀取 repo 根目錄的 .env（已在 .gitignore 中排除，不會進 git）。"""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()


def tz(cfg=CONFIG):
    """設定的時區。Windows 的 Python 沒有內建時區資料，找不到時改用台灣時間 UTC+8。"""
    try:
        return ZoneInfo(cfg["timezone"])
    except Exception:
        return dt.timezone(dt.timedelta(hours=8))


def today(cfg=CONFIG):
    """依設定的時區回傳今天日期；可用環境變數 TODAY=YYYY-MM-DD 覆寫（測試用）。"""
    if os.environ.get("TODAY"):
        return dt.date.fromisoformat(os.environ["TODAY"])
    return dt.datetime.now(tz(cfg)).date()


def start_date(cfg=CONFIG):
    return dt.date.fromisoformat(cfg["start_date"])


def day_number(date, cfg=CONFIG):
    """開始日為第 1 天；開始前回傳 0 以下。"""
    return (date - start_date(cfg)).days + 1


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


# Windows 終端機的編碼可能印不出某些字元，印不出來的改成 ? 而不是讓程式中斷
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass


def log(*args):
    print(*args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Claude API

_client = None


def has_api_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def claude_json(prompt, schema, system=None, max_tokens=16000, cfg=CONFIG):
    """呼叫 Claude 並要求依 JSON schema 回傳；沒有金鑰或失敗時回傳 None。

    金鑰只從環境變數 ANTHROPIC_API_KEY 讀取（GitHub Actions secret 或本機 .env），
    這裡不會印出或寫入金鑰。
    """
    if not has_api_key():
        log("  (沒有 ANTHROPIC_API_KEY，略過 Claude 生成)")
        return None
    import anthropic

    client = _get_client()
    params = dict(
        model=cfg["model"],
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "effort": cfg.get("effort", "medium"),
            "format": {"type": "json_schema", "schema": schema},
        },
    )
    if system:
        params["system"] = system
    try:
        # 被安全分類器擋下時，由伺服器自動改用建議的備援模型
        with client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        ) as stream:
            resp = stream.get_final_message()
    except anthropic.BadRequestError as e:
        log(f"  fallback 參數不被接受，改用一般請求：{e.message}")
        try:
            with client.messages.stream(**params) as stream:
                resp = stream.get_final_message()
        except anthropic.APIError as e2:
            log(f"  Claude API 錯誤：{e2}")
            return None
    except anthropic.APIError as e:
        log(f"  Claude API 錯誤：{e}")
        return None

    if resp.stop_reason == "refusal":
        log("  Claude 拒絕了這個請求")
        return None
    if resp.stop_reason == "max_tokens":
        log("  輸出被 max_tokens 截斷")
        return None
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log("  回傳的 JSON 無法解析")
        return None
