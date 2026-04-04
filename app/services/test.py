from pathlib import Path
from comparator import compare_documents

BASE_DIR = Path(__file__).resolve().parent.parent.parent

before = BASE_DIR / "upload" / "before.pdf"
after = BASE_DIR / "upload" / "after.pdf"

result = compare_documents(
    before_pdf=str(before),
    after_pdf=str(after),
)

print(result["diff_count"])
print(result["csv_path"])