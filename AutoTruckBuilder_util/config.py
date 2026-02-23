import asyncio
import logging

SEMA = asyncio.Semaphore(5)


def _fmt(s: float) -> str:
    return f"{s:.1f}s" if s < 120 else f"{s/60:.1f}m"


def _log_tls_setting():
    from core.util import combined_ca_bundle
    ca = combined_ca_bundle()
    if ca is False:
        logging.getLogger(__name__).info("TLS verify: DISABLED (debug)")
    elif ca is None:
        logging.getLogger(__name__).info("TLS verify: System default (Windows store via certifi_win32)")
    else:
        logging.getLogger(__name__).info(f"TLS verify: Custom bundle at {ca}")