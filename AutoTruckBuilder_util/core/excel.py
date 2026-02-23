# excel.py
from __future__ import annotations
import pandas as pd
import re
import logging
from .util import get_project_root
from pathlib import Path

# ---------- logger ----------
logger = logging.getLogger(__name__)

# ---------- Globals ----------
_BASE_HEADERS = ("from", "specification", "effectivityweek", "configname")
_REQUIRED_HEADERS = ("gg", "from", "specification", "effectivityweek", "configname")
_TRUTHY = {"1", "y", "yes", "true", "t", "x", "✓", "✔", "ok"}

# ---------- Helpers ----------
def _norm(s: str) -> str:
    """Normalize header names: lowercase, remove spaces/underscores."""
    return re.sub(r"[\s_]+", "", str(s or "").lower())

def _to_bool(x) -> bool:
    """Convert various truthy values to boolean."""
    return str(x).strip().lower() in _TRUTHY

def _dedupe_preserve_order(values):
    """Remove duplicates, preserve order, skip empty values."""
    return [v for v in dict.fromkeys(values) if v]

# ---------- Excel Pipeline ----------

def read_excel_df(path, sheet=0) -> pd.DataFrame:
    """Read Excel file into DataFrame, fill NaN with empty string."""
    return pd.read_excel(path, sheet_name=sheet, dtype=str, header=0).fillna("")

def normalize_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize DataFrame column headers, return new DataFrame and original headers."""
    original = [str(c).strip() for c in df.columns]
    df = df.copy()
    df.columns = [_norm(c) for c in original]
    return df, original

def validate_headers(df: pd.DataFrame, original_cols: list[str]) -> None:
    """Allow with-gg or no-gg layouts."""
    cols = list(df.columns)
    has_gg = len(cols) >= 1 and cols[0] == "gg"

    if has_gg:
        need = _REQUIRED_HEADERS
        got = tuple(cols[:len(need)])
        ok = (got == need)
    else:
        need = _BASE_HEADERS
        got = tuple(cols[:len(need)])
        ok = (got == need)

    if not ok:
        raise ValueError(
            "Invalid headers.\n"
            f"Expected first {len(need)}: {list(need)}\n"
            f"Got: {original_cols[:len(need)]}"
        )

def rows_from_df(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame rows to list of dicts with normalized fields."""
    cols = list(df.columns)
    has_gg = len(cols) >= 1 and cols[0] == "gg"
    cv_start = len(_REQUIRED_HEADERS) if has_gg else len(_BASE_HEADERS)
    cv_cols = list(cols[cv_start:])

    rows = []
    for _, r in df.iterrows():
        spec_id = str(r.get("specification", "")).strip()
        if not spec_id:
            continue
        gg = _to_bool(r.get("gg", True))  # default True when gg missing
        from_name = str(r.get("from", "")).strip()
        spec_week = str(r.get("effectivityweek", "")).strip()
        config_name = (str(r.get("configname", "")).strip() or from_name or spec_id)
        change_variants = _dedupe_preserve_order([str(r.get(c, "")).strip() for c in cv_cols])

        rows.append({
            "from_name": from_name,
            "spec_id": spec_id,
            "config_name": config_name,
            "spec_week": spec_week,
            "gg": gg,
            "change_variants": change_variants,
        })
    return rows


# ---------- Public API ----------

def read_rows_from_excel(xlsx_path, sheet_name=0):
    """
    Read and validate Excel file, return list of row dicts.
    """
    df = read_excel_df(xlsx_path, sheet_name)
    df, orig = normalize_headers(df)
    validate_headers(df, orig)
    return rows_from_df(df)


def pick_excel_files_in_xml_bucket():
    folder = get_project_root() / "xml_bucket"
    if not folder.is_dir():
        logger.warning(f"Folder not found: {folder}")
        return []

    # Only .xlsx (pandas 2.x + openpyxl). Exclude temp/aux files.
    def is_real_xlsx(p: Path) -> bool:
        name = p.name.lower()
        return (
            p.is_file()
            and p.suffix.lower() == ".xlsx"
            and not name.startswith("~$")
            and not name.startswith("vms_filter")
            and name != "vms_filter.txt"
        )

    files = sorted(str(p) for p in folder.iterdir() if is_real_xlsx(p))
    logger.info(f"Found {len(files)} Excel file(s) in '{folder}'.")
    return files

def count_excel_files_in_xml_bucket():
    folder = get_project_root() / "xml_bucket"
    if not folder.is_dir():
        logger.warning(f"Folder '{folder}' does not exist.")
        return 0
    return sum(1 for p in folder.iterdir()
               if p.is_file()
               and p.suffix.lower() == ".xlsx"
               and not p.name.lower().startswith(("~$", "vms_filter"))
               and p.name.lower() != "vms_filter.txt")
