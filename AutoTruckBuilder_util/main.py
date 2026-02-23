from __future__ import annotations
try:
    import certifi_win32  # Correct package name - must run first to patch certifi to Windows store
except ImportError:
    pass  # Not installed - will use default certificate handling
except Exception:
    pass

import asyncio
import logging
import os
import time
from tqdm import tqdm

from pathlib import Path
import httpx

from core.auth_edge import AsyncAuth
from core.excel import pick_excel_files_in_xml_bucket
from config import _log_tls_setting
from pipeline import run_pipeline
from summary import print_summary


# ---------------- LOGGING ------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
for name in ("httpx", "httpcore", "hpack", "h11"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ---------------- Main ----------------

def main():
    _log_tls_setting()  # Log verification mode at startup

    files = pick_excel_files_in_xml_bucket()
    if not files:
        print("No Excel files found in xml_bucket.")
        return
    
    failures, durations, total_time = asyncio.run(run_pipeline(files))
    print_summary(len(files), failures, durations, total_time)
    
    if failures:
        print(f"\n⚠ {failures} job(s) failed. Check logs above.")


if __name__ == "__main__":
    main()