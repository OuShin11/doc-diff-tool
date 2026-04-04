from app.services.diff_engine import diff_pages_lines_then_words
from app.services.highlight import export_highlight_images_both
from app.services.pdf import extract_pdf_lines
from app.services.export_csv import export_diffs_to_csv_user

def compare_documents(
    
    before_pdf: str,
    after_pdf: str,
    highlight_out_dir: str = "outputs/highlight",
    csv_out_path: str = "outputs/new_old_taisyou.csv",
    zoom: float = 2.0,
    only_changed_pages: bool = True,
    model: str = "gemma3",
    temperature: float = 0.2,
    use_llm: bool = False
) -> dict:
    
    before = extract_pdf_lines(before_pdf)
    after  = extract_pdf_lines(after_pdf)

    diffs = diff_pages_lines_then_words(before, after)

    # highlight 部分
    paths = export_highlight_images_both(
        before_pdf=before_pdf,
        after_pdf=after_pdf,
        diffs=diffs,
        out_dir=highlight_out_dir,
        zoom=zoom,
        only_changed_pages=only_changed_pages,
    )


    # AI部分
    if use_llm:
        from app.services.llm_gemma import annotate_diffs_with_gemma
        diffs_ai = annotate_diffs_with_gemma(
            diffs, 
            model=model, 
            temperature=temperature
            )
    
    else:
        diffs_ai = diffs # ⭐关键！直接用原始diff
    
    
    export_diffs_to_csv_user(diffs_ai, csv_out_path)

    preview = diffs_ai[:3]

    return {
        "before_pdf": before_pdf,
        "after_pdf": after_pdf,
        "diff_count": len(diffs_ai),
        "highlight_paths": paths,
        "csv_path": csv_out_path,
        "preview": preview,
        "diffs": diffs_ai,
    }

