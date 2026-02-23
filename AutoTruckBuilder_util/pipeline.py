import asyncio
import logging
import time
from pathlib import Path
import httpx

from core.auth_edge import AsyncAuth
from core.excel import read_rows_from_excel
from core.async_ops import (
    post_search_async,
    poll_until_done_async,
    download_out_async,
    fetch_singlespec_cache_by_specid_async,
    build_single_spec_items_from_original_rows,
    read_vms_filter,
)
from core.console_board import ConsoleBoard
from config import SEMA, _fmt

logger = logging.getLogger(__name__)


async def process_file(xlsx: str, auth: AsyncAuth, line_idx: int, board: ConsoleBoard) -> float:
    tag = f"[{Path(xlsx).stem}]"
    t0 = time.perf_counter()

    async with SEMA:
        board.set_progress(line_idx, f"{tag} Reading specs", 5)
        rows = await asyncio.to_thread(read_rows_from_excel, xlsx)
        if not rows:
            board.fail(line_idx, f"{tag} No rows found")
            raise ValueError("No rows found in Excel")
        vms = read_vms_filter()

        # retry helper: only swaps the client on 401/403/419
        async def with_auth_retry(call, **kw):
            assert "client" in kw, "with_auth_retry requires 'client' kw"
            try:
                return await call(**kw)
            except httpx.HTTPStatusError as e:
                if not (e.response and e.response.status_code in (401, 403, 419)):
                    raise
                board.set_progress(line_idx, f"{tag} Refreshing auth…", 20)
                await auth.refresh()
                async with auth.new_client() as c2:
                    kw["client"] = c2
                    return await call(**kw)

        board.set_progress(line_idx, f"{tag} Authenticating", 15)
        async with auth.new_client() as client:
            # 1) singlespec cache
            board.set_progress(line_idx, f"{tag} Fetching single spec", 25)
            ss_cache = await with_auth_retry(
                fetch_singlespec_cache_by_specid_async, client=client, rows=rows
            )

            # 2) build & /search
            board.set_progress(line_idx, f"{tag} Building DCT", 40)
            items = build_single_spec_items_from_original_rows(rows, ss_cache)

            board.set_progress(line_idx, f"{tag} Posting /search", 45)
            job_id = await with_auth_retry(
                post_search_async, client=client, single_spec_items=items, vms=vms, ansa_dlfs=False
            )

            # 3) poll
            board.set_progress(line_idx, f"{tag} Polling", 55)
            done_url = await with_auth_retry(
                poll_until_done_async, client=client, job_id=job_id
            )

            # 4) download
            board.set_progress(line_idx, f"{tag} Downloading", 80)
            out_name = f"{Path(xlsx).stem}.dctzip"
            await with_auth_retry(
                download_out_async, client=client, done_url=done_url, filename=out_name
            )

        dt = time.perf_counter() - t0
        board.complete(line_idx, f"{tag} DONE ✓ ({_fmt(dt)})")
        return dt


async def run_pipeline(files: list[str]) -> tuple[int, list[float], float]:
    auth = AsyncAuth()
    from tqdm import tqdm
    tqdm.write("Initial authentication…")
    await auth.refresh()

    board = ConsoleBoard(len(files))
    board.set_progress(0, "Initial authentication", 10)

    t_start = time.perf_counter()
    tasks = [process_file(f, auth, i, board) for i, f in enumerate(files)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.perf_counter() - t_start

    board.close_all()

    failures, durations = 0, []
    for filepath, res in zip(files, results):
        if isinstance(res, Exception):
            failures += 1
            logger.error(f"[{Path(filepath).stem}] {res}")
        else:
            durations.append(float(res))

    return failures, durations, total_time