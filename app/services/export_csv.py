# csv_export.py

import csv
from typing import Any, Dict, List

Diff = Dict[str, Any]


def export_diffs_to_csv_user(
    diffs: List[Diff],
    csv_path: str,
) -> str:
    fieldnames = [
        "no",
        "page",
        "before_text",
        "after_text",
        "change_action",
        "change_summary",
        "change_category",
        "change_risk",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, d in enumerate(diffs, start=1):
            writer.writerow({
                "no": idx,
                "page": d.get("page", ""),
                "before_text": d.get("old_text", "") or "",
                "after_text": d.get("new_text", "") or "",
                "change_action": d.get("ai_action", "") or "",
                "change_summary": d.get("ai_summary", "") or "",
                "change_category": d.get("ai_category", "") or "",
                "change_risk": d.get("ai_risk", "") or "",
            })

    return csv_path
