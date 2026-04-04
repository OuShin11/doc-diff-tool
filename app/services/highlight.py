# highlight.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable, Optional
from collections import defaultdict

import fitz  # PyMuPDF
from PIL import Image, ImageDraw  # pillow


BBox = Tuple[float, float, float, float]
Diff = Dict[str, Any]


# 把所有差异块，按“页码”分组
def _group_diffs_by_page(diffs: List[Diff]) -> Dict[int, List[Diff]]:
    by_page: Dict[int, List[Diff]] = defaultdict(list)
    for d in diffs:
        by_page[int(d["page"])].append(d)
    return by_page


def _pick_bboxes_for_mode(d: Diff, mode: str) -> List[BBox]:
    """
    mode:
      - 'before': 画 old_bboxes（delete/replace 更直观）
      - 'after' : 画 new_bboxes（insert/replace 更直观）
    """
    tag = d["tag"]
    if mode == "before":
        if tag in ("delete", "replace"):
            return list(d.get("old_bboxes", []))
        return []  # insert 在 before 上没意义（可改成画空）
    elif mode == "after":
        if tag in ("insert", "replace"):
            return list(d.get("new_bboxes", []))
        return []  # delete 在 after 上没意义
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _color_for_tag(tag: str) -> Tuple[int, int, int, int]:
    """
    RGBA 颜色（可按需调整）
    insert  : green
    delete  : red
    replace : yellow
    """
    if tag == "insert":
        return (0, 180, 0, 80)  # 緑
    if tag == "delete":
        return (220, 0, 0, 80)  # 赤
    # replace
    return (240, 200, 0, 80)  # 黄色


def _draw_bboxes_on_pixmap(pix: fitz.Pixmap, rects: List[Tuple[BBox, Tuple[int, int, int, int]]]) -> Image.Image:
    """
    在页面渲染图上画半透明矩形。
    rects: [(bbox, rgba), ...]
    """
    # Pixmap -> PIL Image
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for (x0, y0, x1, y1), rgba in rects:
        # bbox 坐标与渲染图像一致（都是以页面左上为原点、y向下）
        draw.rectangle([x0, y0, x1, y1], outline=rgba[:3] + (180,), width=2, fill=rgba)

    out = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return out


def export_highlight_images(
    pdf_path: str,
    diffs: List[Diff],
    out_dir: str,
    mode: str = "after",
    zoom: float = 2.0,
    only_changed_pages: bool = True,
) -> List[str]:
    """
    指定一个 PDF（before 或 after），把 diffs 对应页渲染成 PNG 并高亮差异。

    mode='before' or 'after'：决定用 old_bboxes 还是 new_bboxes 来画。
    zoom：渲染清晰度（2.0 推荐；越大越清晰但越慢）
    only_changed_pages：只输出发生变化的页（推荐 True）

    返回：生成的文件路径列表
    """
    
    # 创建输出目录
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    # 打开 PDF + 按页整理差异
    doc = fitz.open(pdf_path)
    by_page = _group_diffs_by_page(diffs)

    # 决定要渲染那些页
    changed_pages = sorted(by_page.keys())

    outputs: List[str] = []

    pages_to_render: Iterable[int]
    
    # 只画变化页还是全画
    if only_changed_pages:
        pages_to_render = changed_pages
    else:
        pages_to_render = range(1, doc.page_count + 1)

    # 设置渲染倍率
    mat = fitz.Matrix(zoom, zoom)


    # 核心：开始逐页渲染 + 画高亮
    for page_no in pages_to_render:
        if page_no < 1 or page_no > doc.page_count:
            continue

        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=mat, alpha=False) # 渲染

        # 开始画矩形框
        rects: List[Tuple[BBox, Tuple[int, int, int, int]]] = []
        for d in by_page.get(page_no, []):
            tag = d["tag"] # tag就是删除/添加等类型
            rgba = _color_for_tag(tag)

            bboxes = _pick_bboxes_for_mode(d, mode=mode)
            # 注意：zoom 后 bbox 也要缩放
            for (x0, y0, x1, y1) in bboxes:
                rects.append(((x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom), rgba))

        # 如果这一页没有要画的 rect，且 only_changed_pages=True，理论上不会发生
        img = _draw_bboxes_on_pixmap(pix, rects)

        out_file = outp / f"{Path(pdf_path).stem}_p{page_no:03d}_{mode}.png"
        img.save(out_file)
        outputs.append(str(out_file))

    doc.close()
    return outputs


def export_highlight_images_both(
    before_pdf: str,
    after_pdf: str,
    diffs: List[Diff],
    out_dir: str,
    zoom: float = 2.0,
    only_changed_pages: bool = True,
) -> Dict[str, List[str]]:
    """
    before/after 两套都输出：
      - before: delete/replace 的 old_bboxes
      - after : insert/replace 的 new_bboxes
    """
    out_before = export_highlight_images(
        before_pdf, diffs, out_dir=out_dir, mode="before", zoom=zoom, only_changed_pages=only_changed_pages
    )
    out_after = export_highlight_images(
        after_pdf, diffs, out_dir=out_dir, mode="after", zoom=zoom, only_changed_pages=only_changed_pages
    )
    return {"before": out_before, "after": out_after}

