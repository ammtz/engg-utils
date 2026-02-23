# util.py
from __future__ import annotations
import os, sys, pathlib, tempfile, re
from importlib import resources
from typing import Union, Optional

PathLike = Union[str, os.PathLike[str]]

JOBID_RE = re.compile(r'(?<!\d)(\d{13,20})(?!\d)')

_CONFIG_CACHE: dict[str, str] | None = None

def config_clear_cache() -> None:
    """Clear cached config so tests or callers can reload after FS/env changes."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    
    
def _parse_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"\s*([^=:#]+)\s*[:=]\s*(.*)\s*$", line)
        if not m:
            continue
        k, v = m.group(1).strip(), m.group(2).strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        out[k] = v
    return out

def load_config() -> dict[str, str]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    root = get_project_root()
    for name in ("config.txt", "config", "app.config"):
        p = root / name
        if p.exists():
            try:
                _CONFIG_CACHE = _parse_kv(p.read_text(encoding="utf-8"))
                break
            except Exception:
                _CONFIG_CACHE = {}
                break
    else:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE

def config_get(key: str, default: str = "") -> str:
    """ENV > config file > default. Also expands %VARS% and ~."""
    val = os.getenv(key, load_config().get(key, default)).strip()
    # expand %LOCALAPPDATA% etc and ~
    val = os.path.expandvars(os.path.expanduser(val))
    return val

def get_system_cert_path() -> str:
    env_path = os.path.expandvars(os.path.expanduser(os.getenv("SYSTEM_CERT_PATH", "") or ""))
    if env_path and os.path.exists(env_path):
        return env_path

    # packaged resource (works in dev and frozen)
    try:
        with resources.files("core").joinpath("system_cert.pem").open("rb") as f:
            tmp = os.path.join(tempfile.gettempdir(), "system_cert.pem")
            with open(tmp, "wb") as out: out.write(f.read())
        return tmp
    except Exception:
        return ""

def combined_ca_bundle(env_skip: str = "SYSTEM_SKIP_VERIFY") -> str | bool | None:
    """
    Compute CA policy at runtime (user-agnostic):
      - False  → disable verification (debug only if SYSTEM_SKIP_VERIFY=1)
      - str    → path to merged PEM (certifi + corporate PEM) when corp PEM is present
      - None   → use library default (Requests/httpx). With python-certifi-win32 imported first,
                 this means Windows trust store on Windows.
    Never returns True; callers treat None as “use default”.
    """
    if os.getenv(env_skip) == "1":
        return False

    corp = get_system_cert_path()

    # Get certifi bundle if available (may be Windows store proxy when python-certifi-win32 is active)
    certifi_path: Optional[str]
    try:
        import certifi
        certifi_path = certifi.where()
        if not os.path.exists(certifi_path):
            certifi_path = None
    except Exception:
        certifi_path = None

    # If a corporate PEM exists, merge it with certifi (if present) into a temp file
    if corp and os.path.exists(corp):
        merged = os.path.join(tempfile.gettempdir(), "system_merged_ca.pem")
        with open(merged, "wb") as out:
            if certifi_path:
                with open(certifi_path, "rb") as a: out.write(a.read()); out.write(b"\n")
            with open(corp, "rb") as b: out.write(b.read())
        return merged

    # No corporate PEM → let clients use their default behavior
    # (requests/httpx default verify uses certifi; on Windows, if python-certifi-win32 is imported
    # before requests/httpx, that default is the Windows certificate store)
    return None


def get_project_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    if getattr(sys, "frozen", False):
        # when bundled, keep buckets beside the EXE
        return pathlib.Path(sys.executable).resolve().parent
    return here.parents[1]  # parent of 'core/' in source tree

def unique_filename(path: PathLike) -> pathlib.Path:
    p = pathlib.Path(path)
    folder = p.parent
    stem = p.stem
    ext = p.suffix
    candidate = folder / p.name
    i = 1
    while candidate.exists():
        candidate = folder / f"{stem}({i}){ext}"
        i += 1
    return candidate

def extract_job_id_from_response(resp) -> str:
    loc = resp.headers.get("Location") or resp.headers.get("location")
    if loc:
        m = JOBID_RE.search(loc)
        if m:
            return m.group(1)
    ct = (resp.headers.get("content-type") or "").lower()
    if "json" in ct:
        try:
            j = resp.json()
            for k in ("jobId","job_id","id","resultId","result_id"):
                if k in j and isinstance(j[k], (str,int)):
                    return str(j[k])
        except Exception:
            pass
    m = JOBID_RE.search(getattr(resp, "text", "") or "")
    if m:
        return m.group(1)
    raise ValueError("Could not extract jobId.")