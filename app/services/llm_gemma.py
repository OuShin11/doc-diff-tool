from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from ollama import chat

Diff = Dict[str, Any]


SYSTEM_JA = (
    "あなたは契約書・業務文書の差分を解析するアシスタントです。"
    "入力は『旧テキスト』『新テキスト』の差分ブロックです。"
    "必ずJSONのみで回答してください。余計な文章は出力しないでください。"
)

USER_TEMPLATE_JA = """
次の差分について、変更点把握のためにJSONで出力してください。

【条件】
- 出力は必ずJSONのみ（コードブロック不可、説明不可）
- action は次のいずれか: "追加" / "削除" / "変更" / "不明"
- summary は日本語で1〜2文、簡潔に（何がどう変わったか）
- 可能なら category を短く（例: "契約期間", "金額", "納期", "責任範囲", "定義", "表現調整" など）
- 可能なら risk を1文（重要変更・解釈差の恐れ等）。なければ空文字。

【入力】
page: {page}
diff_tag: {tag}

旧テキスト:
{old_text}

新テキスト:
{new_text}

【出力JSON形式】
{{
  "action": "...",
  "summary": "...",
  "category": "...",
  "risk": "..."
}}
""".strip()


def _infer_action_from_tag(tag: str) -> str:
    # LLMが迷ったときの保険（基本はLLMに任せるが、fallbackで使う）
    if tag == "insert":
        return "追加"
    if tag == "delete":
        return "削除"
    if tag == "replace":
        return "変更"
    return "不明"


def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Gemmaがたまに前後に余計な文字を付ける場合があるので、
    最初の { と最後の } を探してそこだけJSONとして解析する。
    """

    # JSON对象：用 {} 包起来的一组键值对 
    # 外层必须是{ }
    # key 必须是用 "" 包起来的字符串
    # 不能有多余文字！

    # 如果AI返回的不是 JSON：
    # 1. json.loads() 报错
    # 2. 返回的是 raw 文段，不太好导出成 csv

    # 这个函数的几个风险
    # 1. 模型输出了多个 JSON 对象：{...}{...} → 截取会变成一个非法拼接
    # 2. 模型输出里包含 { } 的其它内容（比如引用条文/模板/代码）→ 可能截错范围
    # 3. 输出是 JSON array [...]（不是 dict）→ 你这里会返回 None（因为要求 dict）
    
    # 修改提案
    # 用更严格的抽取：比如说正则找第一个JSON对象（re)那种
    text = (text or "").strip()
    if not text:
        return None

    # まず素直にparse
    try:
        obj = json.loads(text)  # 如果gemma返回的值不是json,这里就会直接报错。
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 前後に余計な文字があるケースの救済
    l = text.find("{")
    r = text.rfind("}")
    if l != -1 and r != -1 and r > l:
        chunk = text[l : r + 1]
        try:
            obj = json.loads(chunk)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    return None


def analyze_diff_with_gemma(
    diff: Diff,
    model: str = "gemma3",
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    1つの差分ブロックをGemma3で要約・分類する。
    戻り値は {"ai_action","ai_summary","ai_category","ai_risk","ai_raw"} などを含むdict。
    """
    page = diff.get("page", "")
    tag = diff.get("tag", "")
    old_text = diff.get("span_old_text") or diff.get("old_text", "") or ""
    new_text = diff.get("span_new_text") or diff.get("new_text", "") or ""
    # 这里优先用span_old_text，因为是整段文本，语意更长


    # 260202 変更点前後の内容も渡す
    old_before = diff.get("old_before", "") or ""
    old_after  = diff.get("old_after", "") or ""
    new_before = diff.get("new_before", "") or ""
    new_after  = diff.get("new_after", "") or ""

    prompt = USER_TEMPLATE_JA.format(
        page=page,
        tag=tag,
        old_text=old_text,
        new_text=new_text,
        # 260202 変更点前後の内容も渡す
        old_before=old_before, old_after=old_after,
        new_before=new_before, new_after=new_after,
    )

    resp = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_JA},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": temperature},
    )

    content = (resp.get("message", {}) or {}).get("content", "").strip()
    parsed = _safe_parse_json(content)

    # fallback（解析失敗時でもCSVに載せられる形で返す）
    if not parsed:
        return {
            "ai_action": _infer_action_from_tag(tag),
            "ai_summary": content[:500] if content else "",
            "ai_category": "",
            "ai_risk": "",
            "ai_raw": content,
            "ai_parse_ok": False,
        }

    action = parsed.get("action") or _infer_action_from_tag(tag)
    summary = parsed.get("summary", "")
    category = parsed.get("category", "")
    risk = parsed.get("risk", "")

    return {
        "ai_action": action,
        "ai_summary": summary,
        "ai_category": category,
        "ai_risk": risk,
        "ai_raw": content,
        "ai_parse_ok": True,
    }


def annotate_diffs_with_gemma(
    diffs: List[Diff],
    model: str = "gemma3",
    temperature: float = 0.2,
    sleep_sec: float = 0.0,
    max_items: Optional[int] = None,
) -> List[Diff]:
    """
    diffs全体にGemma解析結果を付与して返す（破壊的変更はしないでコピーを返す）。
    sleep_sec: 連続呼び出しが重い場合に少し待つ用
    max_items: デバッグ用に最初のN件だけ処理
    """
    out: List[Diff] = []
    n = len(diffs) if max_items is None else min(len(diffs), max_items)

    for i in range(n):
        d = diffs[i]
        ai = analyze_diff_with_gemma(d, model=model, temperature=temperature)

        d2 = dict(d)  # shallow copy
        # shallow copy的好处：占内存少，只复制最外层的dict的键值引用。
        # 如果后续代码修改更内层的内容，原始d也会受影响
        d2.update(ai)
        out.append(d2)

        if sleep_sec > 0:
            time.sleep(sleep_sec)

    # max_items指定時、残りは未処理のまま返したいならここで結合も可。
    if max_items is not None and n < len(diffs):
        out.extend(diffs[n:])

    return out

