import fitz
from typing import List, Dict, Tuple, Any, Optional

Token = Dict[str, Any]  # {"page": int, "text": str, "bbox": (x0,y0,x1,y1)}

def _is_jp_like(ch: str) -> bool:
    """日本語で一般的に使用される文字かどうかを大まかに判定する
（仮名・漢字・全角記号を含む）。"""
    if not ch:  # 空白の対応
        return False
    o = ord(ch) # 字を数字に転換する
    return(      
        0x3040 <= o <= 0x30FF   # ひらがな/カタカナ
        or 0x4E00 <= o <= 0x9FFF  # 漢字
        or 0x3000 <= o <= 0x303F  # 全角記号
    )

def _is_noise_digit(
        ch: str, 
        prev_ch: Optional[str], 
        next_ch: Optional[str], 
        idx: int, 
        n: int
    ) -> bool:
    
    """'業1務' / '以下1「' みたいな数字を消去する。"""
    if not ch.isdigit():  # 数字かどうかを判定
        return False

    # 1：日本語文字に挟まれた孤立した数字 → ノイズ
    if prev_ch and next_ch and _is_jp_like(prev_ch) and _is_jp_like(next_ch):
        return True

    # 2：行末付近に現れる孤立した数字（ページ番号・脚注番号のずれ）→ 噪音
    if idx >= n - 2:  # 最后1~2个字符
        return True

    # 括弧・引用符・全角記号の直前直後にある数字は、脚注番号などの位置ずれである可能性が高い
    if next_ch and next_ch in "（「『【】』」）":  
        return True

    return False

def extract_page_tokens_by_line(page: fitz.Page, page_no_1based: int) -> List[Token]:
    """
    1ページ分の内容を「行単位のトークン列」として抽出する。（テキスト + bbox）。
    また、行内の文字に対してノイズ除去処理を行う。
    """
    rd = page.get_text("rawdict")
    line_tokens: List[Token] = []

    for block in rd.get("blocks", []):
        for line in block.get("lines", []):
            raw_chars: List[Token] = []

            for span in line.get("spans", []):
                if "chars" in span:
                    for c in span["chars"]:
                        ch = c.get("c", "")
                        bbox = c.get("bbox", None)
                        if ch and bbox:
                            raw_chars.append({
                                "page": page_no_1based,
                                "text": ch,
                                "bbox": tuple(bbox),
                            })
                else:
                    # chars がないとき，span text に戻る（bboxはspanのにする）
                    text = span.get("text", "")
                    bbox = span.get("bbox", None)
                    if text and bbox:
                        for ch in text:
                            raw_chars.append({
                                "page": page_no_1based,
                                "text": ch,
                                "bbox": tuple(bbox),
                            })

            if not raw_chars:
                continue

            # 行内の文字を x 座標順にソート
            raw_chars.sort(key=lambda t: t["bbox"][0])

            # 数字を処理する
            cleaned_chars: List[Token] = []
            n = len(raw_chars)
            for i, tok in enumerate(raw_chars):
                ch = tok["text"]
                prev_ch = raw_chars[i-1]["text"] if i > 0 else None
                next_ch = raw_chars[i+1]["text"] if i+1 < n else None
                if _is_noise_digit(ch, prev_ch, next_ch, i, n):
                    continue
                cleaned_chars.append(tok)

            if not cleaned_chars:
                continue

            line_text = "".join(t["text"] for t in cleaned_chars).strip()
            if not line_text:
                continue

            # 行ごとに bbox 合併する
            x0 = min(t["bbox"][0] for t in cleaned_chars)
            y0 = min(t["bbox"][1] for t in cleaned_chars)
            x1 = max(t["bbox"][2] for t in cleaned_chars)
            y1 = max(t["bbox"][3] for t in cleaned_chars)

            line_tokens.append({
                "page": page_no_1based,
                "text": line_text,
                "bbox": (x0, y0, x1, y1),
                # highlightのために charsを保留する
                "chars": cleaned_chars,
            })

    #  y の順にソート（ rawdict はもう読める順番になっているけど）
    line_tokens.sort(key=lambda t: (t["bbox"][1], t["bbox"][0]))
    return line_tokens

def extract_pdf_lines(pdf_path: str) -> List[List[Token]]:
    """ PDFファイル → ページごとの行 token リスト（List[List[Token]])"""
    doc = fitz.open(pdf_path)
    pages: List[List[Token]] = []
    for page_index, page in enumerate(doc):
        pages.append(extract_page_tokens_by_line(page, page_no_1based=page_index + 1))
    return pages


# debug
# before_pages = extract_pdf_lines("data/before.pdf")
# after_pages  = extract_pdf_lines("data/after.pdf")

# print("pages:", len(before_pages))
# print("lines on page1:", len(before_pages[0]))

# for ln in before_pages[0][:15]:
#     print(ln["text"])
#     print()

# for ln in after_pages[0][:15]:
#     print(ln["text"])
#     print()




# 查看第二次コンピュータ出现的位置
# chars_before = extract_pdf_chars("data/before.pdf")
# chars_after = extract_pdf_chars("data/after.pdf")

# old_chars = chars_before[0]   # 第1页
# new_chars = chars_after[0]

# def find_nth(s: str, sub: str, n: int) -> int:
#     start = -1
#     for _ in range(n):
#         start = s.find(sub, start + 1)
#         if start == -1:
#             return -1
#     return start

# # 假设这是第一页，按你项目可能是第1页：chars_before[0], chars_after[0]
# old_text = "".join(c["text"] for c in chars_before[0])
# new_text = "".join(c["text"] for c in chars_after[0])

# i_old = find_nth(old_text, "コンピュータ", 2)
# i_new = find_nth(new_text, "コンピュータ", 2)

# print("old idx2:", i_old)
# print("new idx2:", i_new)

# # 打印第二处附近的窗口（你可以把窗口开大点）
# W = 80
# print("OLD2:", old_text[i_old-W:i_old+W])
# print("NEW2:", new_text[i_new-W:i_new+W])
# print("OLD2 repr:", repr(old_text[i_old-W:i_old+W]))
# print("NEW2 repr:", repr(new_text[i_new-W:i_new+W]))
