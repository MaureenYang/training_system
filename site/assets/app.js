/* 轉職讀書系統：共用工具（資料載入、日期、進度儲存、匯出匯入） */
"use strict";

const TS = (() => {
  const KEY = "training-system-progress-v1";
  const PAGES = [
    ["index.html", "🏠 進度"],
    ["english.html", "🕛 英文"],
    ["coding.html", "🌙 程式"],
    ["news.html", "📰 AI 新聞"],
  ];

  // ---------------------------------------------------------------- 資料
  const cache = {};
  async function getJSON(path, fallback = null) {
    if (path in cache) return cache[path];
    try {
      const r = await fetch(`data/${path}`, { cache: "no-cache" });
      if (!r.ok) throw new Error(r.status);
      cache[path] = await r.json();
    } catch (e) {
      cache[path] = fallback;
    }
    return cache[path];
  }

  // ---------------------------------------------------------------- 日期（以設定的時區為準）
  function isoInTz(tz, d = new Date()) {
    return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  }
  function daysBetween(a, b) {
    return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
  }
  function addDays(iso, n) {
    const d = new Date(Date.parse(iso + "T00:00:00Z") + n * 86400000);
    return d.toISOString().slice(0, 10);
  }
  async function meta() {
    const m = await getJSON("meta.json");
    if (!m) throw new Error("找不到 data/meta.json");
    const today = new URLSearchParams(location.search).get("today") || isoInTz(m.timezone);
    const dayNum = daysBetween(m.start_date, today) + 1; // 開始日 = 第 1 天
    return { ...m, today, dayNum };
  }
  // 英文：1..N 為新進度；超過 N 進入複習循環
  function englishDay(m, dayNum = m.dayNum) {
    const n = m.english_days;
    if (dayNum < 1) return { day: 1, review: false, before: true };
    if (dayNum <= n) return { day: dayNum, review: false };
    return { day: ((dayNum - n - 1) % n) + 1, review: true };
  }
  function codingDay(m, dayNum = m.dayNum) {
    const total = m.coding_weeks * 7;
    const d = Math.min(Math.max(dayNum, 1), total);
    return { day: d, week: Math.ceil(d / 7), weekday: ((d - 1) % 7) + 1, finished: dayNum > total, before: dayNum < 1 };
  }

  // ---------------------------------------------------------------- 進度（localStorage）
  function empty() {
    return { v: 1, en_days: {}, words: {}, code: {}, news: {}, log: {} };
  }
  let state = null;
  function load() {
    if (state) return state;
    try {
      state = Object.assign(empty(), JSON.parse(localStorage.getItem(KEY) || "{}"));
    } catch (e) {
      state = empty();
    }
    return state;
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      toast("無法儲存進度（瀏覽器封鎖了本機儲存）");
    }
  }
  function now() {
    return Date.now();
  }
  function set(section, id, record) {
    load();
    if (record === null) {
      // 用 tombstone 記錄「取消」，匯入合併時才不會被舊資料蓋回來
      state[section][id] = { del: true, ts: now() };
    } else {
      state[section][id] = { ...record, ts: now() };
    }
    save();
  }
  function get(section, id) {
    const r = load()[section][id];
    return r && !r.del ? r : null;
  }
  function all(section) {
    const out = {};
    for (const [k, r] of Object.entries(load()[section] || {})) if (!r.del) out[k] = r;
    return out;
  }
  async function markActivity(kind) {
    const m = await meta();
    const day = m.today;
    const r = get("log", day) || {};
    if (!r[kind]) set("log", day, { ...r, [kind]: true });
  }

  function merge(a, b) {
    const out = empty();
    for (const sec of Object.keys(out)) {
      const A = a[sec] || {}, B = b[sec] || {};
      for (const k of new Set([...Object.keys(A), ...Object.keys(B)])) {
        const x = A[k], y = B[k];
        if (!x || !y) out[sec][k] = x || y;
        else if (sec === "log") out[sec][k] = { en: !!(x.en || y.en), code: !!(x.code || y.code), ts: Math.max(x.ts, y.ts) };
        else out[sec][k] = (x.ts || 0) >= (y.ts || 0) ? x : y;
      }
    }
    return out;
  }
  function exportFile() {
    load();
    const blob = new Blob([JSON.stringify(state, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `training-progress-${isoInTz("Asia/Taipei")}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function importFile(file) {
    return file.text().then((txt) => {
      const data = JSON.parse(txt);
      if (!data || data.v !== 1) throw new Error("不是這個系統的進度檔");
      state = merge(load(), data);
      save();
    });
  }
  function reset() {
    state = empty();
    save();
  }

  // ---------------------------------------------------------------- UI 小工具
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "html") el.innerHTML = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  function toast(msg) {
    let t = document.getElementById("toast");
    if (!t) {
      t = h("div", { id: "toast", role: "status" });
      document.body.append(t);
    }
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), 2200);
  }
  function nav() {
    const here = location.pathname.split("/").pop() || "index.html";
    const bar = h("nav", { class: "topnav" },
      h("a", { class: "brand", href: "index.html" }, "轉職讀書計畫"),
      h("div", { class: "links" },
        PAGES.map(([href, label]) => h("a", { href, class: here === href ? "active" : null }, label))));
    document.body.prepend(bar);
  }
  function bar(value, max, cls = "") {
    const pct = max ? Math.min(100, Math.round((value / max) * 100)) : 0;
    return h("div", { class: `bar ${cls}`, role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100 },
      h("span", { style: `width:${pct}%` }));
  }

  return {
    getJSON, meta, englishDay, codingDay, isoInTz, daysBetween, addDays,
    load, set, get, all, markActivity, exportFile, importFile, reset,
    h, esc, toast, nav, bar,
  };
})();
