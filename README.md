# 轉職讀書計畫系統

每天自動更新的個人讀書網站（GitHub Pages），三個部分：

| 時段 | 內容 | 頁面 |
|---|---|---|
| 🕛 中午 1 小時 | TOEIC：30 天背完《多益必考單字 3,000》，每天約 101 字＋例句、片語、15 題測驗、短篇閱讀 | `english.html` |
| 🌙 晚上 3 小時 | C++ & 資料結構：依 [coding_classes](https://github.com/MaureenYang/coding_classes) 排的 8 週課表 | `coding.html` |
| 📰 隨時 | OpenAI、Anthropic、DeepSeek、Qwen、GLM 的最新消息，中文摘要＋技術演變時間軸 | `news.html` |

首頁 `index.html` 是進度追蹤主頁：今日待辦、超前/落後天數、單字熟記數、測驗正確率、8 週完成度、打卡日曆。

## 先在自己電腦上看看（不需要 API 金鑰）

1. 下載這個 repo（GitHub 頁面綠色「Code」→「Download ZIP」，解壓縮），在終端機 `cd` 到資料夾
2. 依序執行（Windows 把 `python3` 換成 `python`）：

```bash
python3 scripts/gen_english.py --all        # 準備 30 天單字卡（沒有金鑰時只有單字與中文）
python3 scripts/build_site.py               # 組合網站
python3 -m http.server -d _site 8080        # 啟動，按 Ctrl+C 結束
```

3. 瀏覽器打開 http://127.0.0.1:8080

沒有金鑰時看不到例句、考題、閱讀與新聞摘要，其他功能（進度追蹤、單字卡、程式課表）都能用。

## 第一次設定

1. **設定 API 金鑰**：GitHub repo → Settings → Secrets and variables → Actions → New repository secret，
   名稱 `ANTHROPIC_API_KEY`。金鑰只存在 GitHub 的加密 secret 裡，不會出現在程式碼、git 紀錄或網站上；
   建議在 Anthropic Console 幫這把金鑰設每月花費上限。
2. **開啟 Pages**：Settings → Pages → Source 選「GitHub Actions」。
3. **設定開始日**：改 `config.json` 的 `start_date`（開始日是第 1 天）。
4. 把這個分支合併到 `main`，到 Actions → Daily update → Run workflow 手動跑第一次。
   想一次生成全部 30 天英文內容，勾選 `english_all`。

之後每天台灣時間 05:30 自動：抓新聞 → 生成今天和明天的英文內容 → commit 資料 → 部署網站。

## 進度儲存

打勾、單字熟悉度、測驗分數都存在瀏覽器的 localStorage。換裝置時在首頁「匯出進度」→ 新裝置「匯入進度」，
會依時間戳自動合併兩邊的紀錄。

## 單字庫

- 原始 PDF 放在 `data/vocab/source/`（已在 `.gitignore` 排除，不會進 git）。
- `scripts/pdf_to_csv.py` 把 PDF（兩欄排版）轉成 `data/vocab/words.csv`，並修正原書幾個排版錯字與詞性錯誤
  （見腳本裡的 `CORRECTIONS`、`ROW_FIXES`）。
- `scripts/import_vocab.py` 把 CSV 依原書順序平均切成 30 天 → `words.json`、`schedule.json`。

```bash
python3 scripts/pdf_to_csv.py data/vocab/source/toeic3000.pdf
python3 scripts/import_vocab.py data/vocab/words.csv
```

## 指令

```bash
pip install -r requirements.txt
python3 scripts/fetch_news.py               # 抓新聞、更新時間軸
python3 scripts/gen_english.py              # 今天和明天的英文內容（--day N / --all / --force）
python3 scripts/build_curriculum.py         # 改了課表（PLAN）後重新產生 curriculum.json
python3 scripts/build_site.py               # 組合網站到 _site/
python3 -m http.server -d _site 8080        # 本機預覽；網址加 ?today=2026-10-20 可模擬日期
```

本機要用 Claude 生成內容時，在 repo 根目錄建立 `.env`（已被 git 忽略）：`ANTHROPIC_API_KEY=...`。

## 設定（config.json）

- `model` / `effort`：Claude 模型與思考強度
- `news.sources`：新聞來源，可增減。`type` 支援 `rss`、`sitemap`、`hf_models`（Hugging Face 組織新權重）、`page_diff`（沒有 feed 的頁面，和前一天快照比對）
- `news.max_new_summaries_per_run`：每天最多摘要幾則（控制 API 成本）

## 目錄

```
config.json                 設定
scripts/                    資料腳本（Python 3.10+，只需 anthropic 套件）
data/vocab/                 單字庫與 30 天分配
data/english/day-NN.json    每日英文內容
data/coding/curriculum.json 8 週課表
data/news/                  新聞、時間軸、頁面快照
site/                       靜態網站（HTML + vanilla JS）
.github/workflows/daily.yml 每日排程與部署
```
