#!/usr/bin/env python3
"""產生 8 週 C++ & 資料結構課表 → data/coding/curriculum.json

教材：https://github.com/MaureenYang/coding_classes
每週 6 天新進度 + 第 7 天複習 / 補進度；每晚 3 小時（180 分鐘）。
要調整課表就改下面的 PLAN，再執行一次：python3 scripts/build_curriculum.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CONFIG, DATA, write_json  # noqa: E402

REPO = CONFIG["coding_repo"]

LESSONS = {
    "ds00": ("lessons/00_how_to_use.md", "00. 如何使用這個平台"),
    "ds01": ("lessons/01_cpp_basics_and_complexity.md", "01. C++ 基礎與時間複雜度"),
    "ds01b": ("lessons/01b_complexity_exam.md", "01b. 時間複雜度考題（40 題）"),
    "ds02": ("lessons/02_recursion.md", "02. 遞迴：河內塔與回溯法"),
    "ds03": ("lessons/03_dynamic_array.md", "03. 動態陣列 (vector)"),
    "ds04": ("lessons/04_linked_list.md", "04. 鏈結串列"),
    "ds05": ("lessons/05_stack_queue.md", "05. 堆疊、佇列、雙端佇列"),
    "ds06": ("lessons/06_hash_table.md", "06. 雜湊表"),
    "ds07": ("lessons/07_heap.md", "07. 堆積與優先佇列"),
    "ds08": ("lessons/08_bst.md", "08. 二元搜尋樹"),
    "ds09": ("lessons/09_graph.md", "09. 圖：BFS、DFS 與拓撲排序"),
    "ds10": ("lessons/10_union_find.md", "10. 併查集"),
    "ds11": ("lessons/11_testing_and_corner_cases.md", "11. Corner Case、產生測資、對拍"),
    "cpp00": ("cpp/lessons/00_roadmap.md", "C++ 00. 學習路線圖"),
    "cpp01": ("cpp/lessons/01_types_variables.md", "C++ 01. 型別、變數與型別轉換"),
    "cpp02": ("cpp/lessons/02_expressions.md", "C++ 02. 運算式"),
    "cpp03": ("cpp/lessons/03_statements.md", "C++ 03. 敘述與控制流程"),
    "cpp04": ("cpp/lessons/04_functions.md", "C++ 04. 函式"),
    "cpp05": ("cpp/lessons/05_pointers_references.md", "C++ 05. 指標與參考"),
    "cpp06": ("cpp/lessons/06_memory_raii.md", "C++ 06. 記憶體管理、RAII 與移動語意"),
    "cpp07": ("cpp/lessons/07_classes_oop.md", "C++ 07. 類別與物件導向"),
    "cpp08": ("cpp/lessons/08_inheritance_polymorphism.md", "C++ 08. 繼承與多型"),
    "cpp09": ("cpp/lessons/09_adt_design.md", "C++ 09. 抽象資料型別與設計"),
    "cpp10": ("cpp/lessons/10_templates.md", "C++ 10. 模板與泛型程式設計"),
    "cpp11": ("cpp/lessons/11_stl.md", "C++ 11. STL 深入"),
    "cpp12": ("cpp/lessons/12_strings_io.md", "C++ 12. 字串與輸入輸出"),
    "cpp13": ("cpp/lessons/13_exceptions.md", "C++ 13. 例外處理"),
    "cpp14": ("cpp/lessons/14_compilation_model.md", "C++ 14. 編譯模型"),
    "cpp15": ("cpp/lessons/15_modern_cpp.md", "C++ 15. 現代 C++ 與未定義行為"),
}

# 題目代號 → (資料夾, 標題, 難度, judge 指令用的代號)
PROBLEMS = {
    "p01": ("problems/01_hanoi", "河內塔", "★☆☆", "1"),
    "p02": ("problems/02_hanoi_kth", "河內塔的第 k 步", "★★☆", "2"),
    "p03": ("problems/03_my_vector", "自己做一個 vector", "★☆☆", "3"),
    "p04": ("problems/04_linked_list", "單向鏈結串列", "★★☆", "4"),
    "p05": ("problems/05_brackets", "括號配對", "★☆☆", "5"),
    "p06": ("problems/06_min_stack", "最小值堆疊", "★★☆", "6"),
    "p07": ("problems/07_circular_queue", "環狀佇列", "★★☆", "7"),
    "p08": ("problems/08_next_greater", "下一個更大的元素", "★★☆", "8"),
    "p09": ("problems/09_sliding_window_max", "滑動視窗最大值", "★★★", "9"),
    "p10": ("problems/10_hash_table", "自己做一個雜湊表", "★★☆", "10"),
    "p11": ("problems/11_lru_cache", "LRU 快取", "★★★", "11"),
    "p12": ("problems/12_binary_heap", "二元堆積", "★★☆", "12"),
    "p13": ("problems/13_bst", "二元搜尋樹", "★★★", "13"),
    "p14": ("problems/14_union_find", "併查集", "★★☆", "14"),
    "p15": ("problems/15_maze_bfs", "迷宮最短路徑", "★★☆", "15"),
    "p16": ("problems/16_topo_sort", "拓撲排序", "★★★", "16"),
    "p17": ("problems/17_n_queens", "N 皇后", "★★☆", "17"),
    "c01": ("cpp/problems/c01_expression_eval", "運算式求值", "★★☆", "c1"),
    "c02": ("cpp/problems/c02_bit_ops", "位元運算", "★★☆", "c2"),
    "c03": ("cpp/problems/c03_date_calc", "日期計算", "★★☆", "c3"),
    "c04": ("cpp/problems/c04_custom_sort", "多條件排序", "★★☆", "c4"),
    "c05": ("cpp/problems/c05_matrix_pointers", "用指標做矩陣", "★★☆", "c5"),
    "c06": ("cpp/problems/c06_my_string", "自己做一個字串類別", "★★★", "c6"),
    "c07": ("cpp/problems/c07_fraction", "分數類別", "★★☆", "c7"),
    "c08": ("cpp/problems/c08_shapes", "圖形與多型", "★★☆", "c8"),
    "c09": ("cpp/problems/c09_bank_adt", "銀行帳戶系統", "★★★", "c9"),
    "c10": ("cpp/problems/c10_templates", "泛型堆疊", "★★☆", "c10"),
    "c11": ("cpp/problems/c11_word_freq", "單字頻率統計", "★★☆", "c11"),
    "c12": ("cpp/problems/c12_csv_grades", "成績單解析", "★★☆", "c12"),
    "c13": ("cpp/problems/c13_exceptions", "安全的計算機", "★★★", "c13"),
    "c14": ("cpp/problems/c14_unique_ptr_list", "智慧指標串列", "★★★", "c14"),
}

# 每天一個 list：("L", 教學代號, 分鐘) / ("P", 題目代號, 分鐘) / ("T", 自訂任務, 分鐘)
# 每天另外固定加 30 分鐘「評測、對拍、debug、寫筆記」→ 合計 180 分鐘
PLAN = [
    ("第 1 週：C++ 語言基礎", [
        [("T", "環境設定：安裝 g++ (C++17)、clone coding_classes、執行 python3 judge.py serve", 30),
         ("L", "ds00", 20), ("L", "cpp00", 20), ("L", "cpp01", 80)],
        [("L", "cpp02", 90), ("P", "c01", 60)],
        [("P", "c02", 90), ("T", "完成 C++ 02 課後習題（預測輸出、找 bug）", 60)],
        [("L", "cpp03", 75), ("P", "c03", 75)],
        [("L", "cpp04", 110), ("T", "C++ 04 課後習題", 40)],
        [("P", "c04", 90), ("T", "回頭重寫本週卡最久的一題，不看解答", 60)],
    ]),
    ("第 2 週：指標、記憶體、類別", [
        [("L", "cpp05", 120), ("T", "C++ 05 課後習題", 30)],
        [("P", "c05", 120), ("T", "用 --debug (AddressSanitizer) 跑一次 c05，理解每個警告", 30)],
        [("L", "cpp06", 150)],
        [("P", "c06", 150)],
        [("L", "cpp07", 120), ("T", "C++ 07 課後習題", 30)],
        [("P", "c07", 120), ("T", "整理筆記：三/五/零法則、RAII、const 成員函式", 30)],
    ]),
    ("第 3 週：複雜度與遞迴", [
        [("L", "ds01", 150)],
        [("L", "ds01b", 150)],
        [("L", "ds02", 90), ("P", "p01", 60)],
        [("P", "p02", 150)],
        [("P", "p17", 150)],
        [("T", "複習 C++ 06 移動語意與 unique_ptr", 45), ("P", "c14", 105)],
    ]),
    ("第 4 週：vector、鏈結串列、多型", [
        [("L", "ds03", 60), ("P", "p03", 90)],
        [("L", "ds04", 150)],
        [("P", "p04", 150)],
        [("L", "cpp08", 150)],
        [("P", "c08", 150)],
        [("L", "ds05", 90), ("P", "p05", 60)],
    ]),
    ("第 5 週：Stack / Queue / Hash", [
        [("P", "p06", 150)],
        [("P", "p07", 150)],
        [("P", "p08", 150)],
        [("P", "p09", 150)],
        [("L", "ds06", 75), ("P", "p10", 75)],
        [("P", "p11", 150)],
    ]),
    ("第 6 週：ADT、模板、STL、Heap", [
        [("L", "cpp09", 150)],
        [("P", "c09", 150)],
        [("L", "cpp10", 75), ("P", "c10", 75)],
        [("L", "cpp11", 75), ("P", "c11", 75)],
        [("L", "ds07", 60), ("P", "p12", 90)],
        [("L", "ds08", 150)],
    ]),
    ("第 7 週：BST、併查集、圖、字串 IO", [
        [("P", "p13", 150)],
        [("L", "ds10", 60), ("P", "p14", 90)],
        [("L", "ds09", 150)],
        [("P", "p15", 150)],
        [("P", "p16", 150)],
        [("L", "cpp12", 75), ("P", "c12", 75)],
    ]),
    ("第 8 週：例外、編譯模型、總複習", [
        [("L", "cpp13", 75), ("P", "c13", 75)],
        [("L", "cpp14", 150)],
        [("L", "cpp15", 150)],
        [("L", "ds11", 90), ("T", "挑一題自己寫測資產生器，用 judge.py stress 對拍", 60)],
        [("T", "計時重寫（90 分鐘內、不看解答）：09 滑動視窗最大值", 75),
         ("T", "計時重寫：11 LRU 快取", 75)],
        [("T", "計時重寫：13 二元搜尋樹", 75), ("T", "計時重寫：16 拓撲排序；寫下 8 週總結與下一步", 75)],
    ]),
]

DAILY_WRAPUP = ("T", "評測、對拍 (stress)、debug，寫今天的筆記", 30)


def item(kind, ref, minutes, task_id):
    base = {"id": f"{kind.lower()}-{ref}" if kind != "T" else task_id, "minutes": minutes}
    if kind == "L":
        path, title = LESSONS[ref]
        return {**base, "type": "lesson", "title": title, "url": f"{REPO}/blob/HEAD/{path}"}
    if kind == "P":
        path, title, diff, short = PROBLEMS[ref]
        return {**base, "type": "problem", "title": f"{ref.upper()} {title}", "difficulty": diff,
                "url": f"{REPO}/blob/HEAD/{path}/problem.md",
                "commands": [f"python3 judge.py start {short}", f"python3 judge.py test {short}",
                             f"python3 judge.py stress {short}"]}
    return {**base, "type": "task", "title": ref}


def main():
    weeks, day_no = [], 0
    for w, (title, days) in enumerate(PLAN, 1):
        wk = {"week": w, "title": title, "days": []}
        week_items = []
        for d, tasks in enumerate(days, 1):
            day_no += 1
            items = []
            for kind, ref, mins in tasks + [DAILY_WRAPUP]:
                items.append(item(kind, ref, mins, f"t-d{day_no}-{len(items)}"))
            week_items += [i for i in items if i["type"] == "problem"]
            wk["days"].append({"day": day_no, "weekday": d, "items": items})
        # 第 7 天：複習 / 補進度
        day_no += 1
        hardest = sorted(week_items, key=lambda i: -len(i["difficulty"].replace("☆", "")))[:1]
        review = [{"id": f"t-d{day_no}-0", "type": "task", "minutes": 60,
                   "title": "補完本週還沒打勾的項目（沒有落後就跳過）"}]
        if hardest:
            review.append({"id": f"t-d{day_no}-1", "type": "task", "minutes": 90,
                           "title": f"不看解答重寫本週最難的一題：{hardest[0]['title']}"})
        review.append({"id": f"t-d{day_no}-2", "type": "task", "minutes": 30,
                       "title": "整理本週筆記：名詞、踩過的坑、複雜度"})
        wk["days"].append({"day": day_no, "weekday": 7, "review": True, "items": review})
        weeks.append(wk)

    total = sum(len(d["items"]) for w in weeks for d in w["days"])
    write_json(os.path.join(DATA, "coding", "curriculum.json"),
               {"repo": REPO, "minutes_per_day": 180, "weeks": weeks})
    used_l = {i["id"] for w in weeks for d in w["days"] for i in d["items"] if i["type"] == "lesson"}
    used_p = {i["id"] for w in weeks for d in w["days"] for i in d["items"] if i["type"] == "problem"}
    print(f"{len(weeks)} 週 / {day_no} 天 / {total} 項；教學 {len(used_l)}/{len(LESSONS)}、題目 {len(used_p)}/{len(PROBLEMS)}")
    for w in weeks:
        for d in w["days"]:
            m = sum(i["minutes"] for i in d["items"])
            if m != 180:
                print(f"  注意：第 {d['day']} 天合計 {m} 分鐘")


if __name__ == "__main__":
    main()
