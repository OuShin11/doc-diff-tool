# diff_engine.py
from __future__ import annotations

import difflib
import fitz
import re # 増やす部分：スペースの問題を解決するため 
from dataclasses import dataclass  # まだ使ってない
from typing import Any, Dict, List, Tuple, Optional  # Type hint


BBox = Tuple[float, float, float, float]
Word = Dict[str, Any]

# 260202 AI処理のための準備　_safe_get_line　_context_around
def _safe_get_line(lines, idx: int) -> str:
    if 0 <= idx < len(lines):
        return (lines[idx].get("text") or "").strip()
    return ""

def _context_around(
    old_lines, new_lines,
    i1: int, i2: int, j1: int, j2: int,
    k: int = 1
) -> Tuple[str, str, str, str]:
    """
    (old_before, old_after, new_before, new_after) を戻る
    - old_before: old span 前 k 行
    - old_after : old span 後ろの k 行
    - new_before/new_after 同じように
    """
    old_before = "\n".join(
        _safe_get_line(old_lines, t) for t in range(i1 - k, i1)
        if _safe_get_line(old_lines, t)
    )
    old_after = "\n".join(
        _safe_get_line(old_lines, t) for t in range(i2, i2 + k)
        if _safe_get_line(old_lines, t)
    )
    new_before = "\n".join(
        _safe_get_line(new_lines, t) for t in range(j1 - k, j1)
        if _safe_get_line(new_lines, t)
    )
    new_after = "\n".join(
        _safe_get_line(new_lines, t) for t in range(j2, j2 + k)
        if _safe_get_line(new_lines, t)
    )
    return old_before, old_after, new_before, new_after




# 日本語文字
_JP = r"\u3040-\u30FF\u4E00-\u9FFF"  # ひらがな/カタカナ/漢字

# 「日本語文字 + スペース + 日本語文字」の中でのスペースを消去
_RE_JP_SPACE = re.compile(rf"([{_JP}])\s+([{_JP}])")

def _normalize_token(t: str) -> str:
    s = (t or "").strip()  # stringの首尾のスペースや\nなどを消去する
    # 連続のスペースを一つにする
    s = re.sub(r"\s+", " ", s)
    # 　日本語文字の間のスペースを消去
    while True: # 用while 是因为一次只能消去一个
        s2 = _RE_JP_SPACE.sub(r"\1\2", s)
        if s2 == s:
            break
        s = s2
    return s



def _page_tokens(page_words: List[Word]) -> List[str]:
    # return [
    #     _normalize_token(w["text"]) 
    #     for w in page_words 
    #     if _normalize_token(w["text"]) != ""
    # ]
    # 新版
    out = []
    for w in page_words:
        t = _normalize_token(w["text"])
        # index の対応関係を維持するため、空要素も\n をいれて保持する
        # 因为切是按token切，所以这里word的index要跟token保持一致
        out.append(t if t != "" else "\n")
    return out


def _slice_words(words: List[Word], start: int, end: int) -> List[Word]:
    #  difflib の start/end はtoken配列のindexに基づくため、同一のindexでスライスを行う
    return words[start:end]


def diff_pages_words(
    old_pages: List[List[Word]],
    new_pages: List[List[Word]],
) -> List[Dict[str, Any]]:
    """
    ページ単位で文字レベルの diff を行い、差分ブロックを返す。
    各差分ブロックには bbox の情報を含め、
    後続処理でハイライト画像を生成しやすい構造とする。
    """
    # 大量字符移动/换行会导致 SequenceMatcher 匹配“错位”
    # 输出会变成巨量碎片，难读，也难喂 AI
    diffs: List[Dict[str, Any]] = []

    max_pages = max(len(old_pages), len(new_pages))
    for p in range(max_pages):
        old_words = old_pages[p] if p < len(old_pages) else []
        new_words = new_pages[p] if p < len(new_pages) else []

        # 1-based page
        page_no = old_words[0]["page"] if old_words else (new_words[0]["page"] if new_words else (p + 1))

        old_tokens = _page_tokens(old_words)
        new_tokens = _page_tokens(new_words)

        sm = difflib.SequenceMatcher(a=old_tokens, b=new_tokens,autojunk=False)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            

            old_span_words = _slice_words(old_words, i1, i2)
            new_span_words = _slice_words(new_words, j1, j2)

            diffs.append({
                "page": page_no,
                "tag": tag,  # 'insert' | 'delete' | 'replace'
                "old_text": " ".join([w["text"] for w in old_span_words]).strip(),
                "new_text": " ".join([w["text"] for w in new_span_words]).strip(),
                "old_bboxes": [w["bbox"] for w in old_span_words],
                "new_bboxes": [w["bbox"] for w in new_span_words],
                # 構造情報を保留しておくことで、同一行のハイライトを統合しやすくする
                "old_words": old_span_words,
                "new_words": new_span_words,
            })

    return diffs

def _flatten_chars(lines):
    # lines: List[LineToken], 每个 line 里有 "chars"
    out = []
    for ln in lines:
        out.extend(ln.get("chars", []))
    return out

def diff_pages_lines_then_words(
    old_pages: List[List[Word]],
    new_pages: List[List[Word]],
) -> List[Dict[str, Any]]:
    """
    第1段階：行レベルの diff
    第2段階：変更行に対して diff_pages_words を用いた
    行内の文字レベル diff を行う。
    """
    all_diffs: List[Dict[str, Any]] = []

    max_pages = max(len(old_pages), len(new_pages))
    for p in range(max_pages):
        old_lines = old_pages[p] if p < len(old_pages) else []
        new_lines = new_pages[p] if p < len(new_pages) else []

        old_texts = [ln["text"] for ln in old_lines]
        new_texts = [ln["text"] for ln in new_lines]

        sm = difflib.SequenceMatcher(a=old_texts, b=new_texts, autojunk=False)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue

            # 260202 AI処理のため
            old_before, old_after, new_before, new_after = _context_around(
                old_lines, new_lines, i1, i2, j1, j2, k=1
            )

            # insert / delete / replace ここで判定
            old_span = old_lines[i1:i2]
            new_span = new_lines[j1:j2]


            # 行级 insert / delete：直接记录（是否要逐字 diff 你可选）
            if tag in ("insert", "delete"):
                all_diffs.append({
                    "page": p + 1,
                    "tag": tag,
                    "old_text": "\n".join(ln["text"] for ln in old_span),
                    "new_text": "\n".join(ln["text"] for ln in new_span),
                    "old_bboxes": [ln["bbox"] for ln in old_span],
                    "new_bboxes": [ln["bbox"] for ln in new_span],
                    "old_before": old_before,
                    "old_after": old_after,
                    "new_before": new_before,
                    "new_after": new_after,
                })
                continue

            # replace：各行に対して行内の文字単位 diff を実施
            # tag == "replace" の分岐内で処理を行う
            old_chars = _flatten_chars(old_span)
            new_chars = _flatten_chars(new_span)

            #　行全体を対象に、一度だけ行内の文字単位 diff を行う
            inner_diffs = diff_pages_words(
                [old_chars],   # 注意：这里是一页（只有一个“块”）
                [new_chars],
            )

            # 260202 AIに読み込みのため
            span_old_text = "\n".join(ln["text"] for ln in old_span)
            span_new_text = "\n".join(ln["text"] for ln in new_span)
            # ページ数を注意： diff_pages_words を p+1 にする
            for d in inner_diffs:
                d["page"] = p + 1
                d["old_before"] = old_before
                d["old_after"] = old_after
                d["new_before"] = new_before
                d["new_after"] = new_after
                # 260202 AIに読み込みのため
                d["span_old_text"] = span_old_text  # char がいるline
                d["span_new_text"] = span_new_text  # char がいるline

            all_diffs.extend(inner_diffs)

    return all_diffs



# debug
# from pdf import extract_pdf_lines

# before = extract_pdf_lines("data/before.pdf")
# after  = extract_pdf_lines("data/after.pdf")

# diffs = diff_pages_lines_then_words(before, after)
# print(len(diffs))
# for d in diffs:
#     print(d["page"], d["tag"], d["old_text"], "=>", d["new_text"])
   

# debug
# print("========== debug ==========")
# def debug_pages(pages, name="old_pages", max_pages=1, max_lines=25):
#     print(f"\n=== {name}: pages={len(pages)} ===")
#     for p in range(min(max_pages, len(pages))):
#         lines = pages[p]
#         print(f"--- page {p+1}: items={len(lines)} ---")
#         for i, ln in enumerate(lines[:max_lines]):
#             t = (ln.get("text") or "")
#             print(i, len(t), t)

# debug_pages(before, "old_pages")
# debug_pages(after, "new_pages")