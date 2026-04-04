from pathlib import Path
import shutil
import uuid
import traceback

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.comparator import compare_documents

router = APIRouter(prefix="/compare", tags=["compare"])

UPLOAD_DIR = Path("upload")
UPLOAD_DIR.mkdir(exist_ok=True)

# 新增：让compare_document()返回URL，而不是路径
def to_static_url(path_str: str) -> str:
    path = Path(path_str).resolve()
    base = (Path(__file__).resolve().parent.parent.parent / "outputs").resolve()
    rel_path = path.relative_to(base)
    return f"/static/{rel_path.as_posix()}"

@router.post("/")
def compare_files(old_file: UploadFile = File(...), new_file: UploadFile = File(...)):
    try:
        old_suffix = Path(old_file.filename).suffix
        new_suffix = Path(new_file.filename).suffix

        old_path = UPLOAD_DIR / f"{uuid.uuid4()}{old_suffix}"
        new_path = UPLOAD_DIR / f"{uuid.uuid4()}{new_suffix}"

        with old_path.open("wb") as f:
            shutil.copyfileobj(old_file.file, f)

        with new_path.open("wb") as f:
            shutil.copyfileobj(new_file.file, f)

        # 新增：让compare_document()返回URL，而不是路径
        result = compare_documents(str(old_path), str(new_path))
        result["highlight_urls"] = {
            "before": [to_static_url(p) for p in result["highlight_paths"]["before"]],
            "after": [to_static_url(p) for p in result["highlight_paths"]["after"]],
        }

        return result

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))