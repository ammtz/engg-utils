# auth_edge.py
try:
    import certifi_win32
except Exception:
    pass

import os, pathlib, requests, threading, asyncio
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait

import httpx
from httpx import Cookies
from core.util import combined_ca_bundle
from pathlib import Path
import tempfile, shutil
from selenium.common.exceptions import SessionNotCreatedException
from typing import Optional

BASE_URL = "https://companygroup.sharepoint.com/"
SYSTEM_URL = "https://system.company.net"

# ----------------- small helpers -----------------
def _wait_cookie(driver, names, timeout=600):
    WebDriverWait(driver, timeout).until(
        lambda d: any(c.get("name") in names for c in d.get_cookies())
    )

def _wait_domain(driver, domain, timeout=120):
    WebDriverWait(driver, timeout).until(lambda d: domain in d.current_url.lower())

def _verify():
    v = combined_ca_bundle()
    if v is False: return False
    if isinstance(v, str) and v: return v
    return None  # system store

def _new_system_session():
    s = requests.Session()
    v = _verify()
    if v is not None: s.verify = v
    return s

# ----------------- Edge launch robustness -----------------
def _edge_binary():
    env = os.getenv("EDGE_BINARY")
    if env and os.path.exists(env):
        return env
    cand = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in cand:
        if os.path.exists(p):
            return p
    return None

def _edge_user_data_root():
    return os.getenv("EDGE_USER_DATA_DIR") or os.path.expanduser(
        r"~\AppData\Local\Microsoft\Edge\User Data"
    )

def _edge_profile():
    return os.getenv("EDGE_PROFILE", "Default")

def _profile_in_use(user_data_root, profile_name):
    p = pathlib.Path(user_data_root) / profile_name / "SingletonLock"
    return p.exists()

def _build_opts(
    user_data_dir: Optional[str] = None,
    profile_dir: Optional[str] = None,
    silent: bool = False,
):
    opts = EdgeOptions()
    # Let Selenium pick correct driver/binary. Don't set binary_location unless you truly need to.
    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        opts.add_argument(f"--profile-directory={profile_dir}")

    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--remote-allow-origins=*")
    # Keep GPU enabled in headed mode; disable only if you see GPU init errors in headless.
    # opts.add_argument("--disable-gpu")

    if silent:
        opts.add_argument("--start-minimized")
        opts.add_argument("--window-position=-32000,-32000")
        opts.add_argument("--window-size=1200,800")
        opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    return opts

# --- new: clean temp-profile launcher ---
def _start_edge_clean(silent: bool = False):
    tmp_dir = Path(tempfile.mkdtemp(prefix="edge_autologin_"))
    try:
        opts = _build_opts(user_data_dir=str(tmp_dir), silent=silent)
        drv = webdriver.Edge(options=opts)  # Selenium Manager resolves the driver
        # Attach temp path so we can delete later in finally
        drv._tmp_user_data_dir = tmp_dir
        return drv
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

# --- replace _start_edge_with_profile with robust fallback logic ---
def _start_edge_with_profile(silent: bool = False):
    """
    Prefer a clean temp profile (most stable). If you *require* a real profile,
    set EDGE_PROFILE=Profile 2 and EDGE_USER_DATA_DIR to your Edge user data path,
    and ensure Edge is fully closed before running.
    """
    # 1) Try clean temp profile first
    try:
        return _start_edge_clean(silent=silent)
    except SessionNotCreatedException:
        pass  # fall through
    except Exception:
        pass

    # 2) Optional: use user profile if explicitly requested
    root = _edge_user_data_root()
    prof = _edge_profile()
    if root and prof:
        if _profile_in_use(root, prof):
            raise RuntimeError(
                f"Edge profile '{prof}' is in use. Close all Edge windows. Path: {Path(root)/prof}"
            )
        opts = _build_opts(user_data_dir=root, profile_dir=prof, silent=silent)
        return webdriver.Edge(options=opts)

    # 3) Last resort: clean again (will raise if it fails)
    return _start_edge_clean(silent=silent)

# ----------------- Public API -----------------
def login_sharepoint_then_system() -> requests.Session:
    driver = _start_edge_with_profile(silent=True)
    try:
        org = os.getenv("AAD_TENANT_DOMAIN", "companygroup.com")
        upn = os.getenv("AAD_LOGIN_HINT")
        warm = f"https://login.microsoftonline.com/common/oauth2/authorize?whr={org}"
        if upn: warm += f"&login_hint={upn}"

        driver.get(warm)
        driver.get(BASE_URL)
        _wait_cookie(driver, {"FedAuth", "rtFa"})
        _wait_domain(driver, "sharepoint.com")

        driver.get(SYSTEM_URL)
        _wait_domain(driver, "system.company.net")
        WebDriverWait(driver, 300).until(
            lambda d: any("system.company.net" in (c.get("domain") or "") for c in d.get_cookies())
        )

        s = _new_system_session()
        for c in driver.get_cookies():
            dom = c.get("domain", "")
            if "system.company.net" in dom or ".company.net" in dom:
                s.cookies.set(c["name"], c["value"], domain=dom or None)
        return s
    finally:
        try:
            driver.quit()
        finally:
            # delete temp user-data-dir if we created one
            tmp = getattr(driver, "_tmp_user_data_dir", None)
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)


def is_system_authenticated(session: requests.Session) -> bool:
    try:
        r = session.get(SYSTEM_URL + "/", allow_redirects=False, timeout=20)
        if r.status_code == 200:
            return True
        if r.status_code in (301, 302, 303, 307, 308):
            loc = (r.headers.get("Location") or "").lower()
            return not any(k in loc for k in ("login", "adfs", "sharepoint"))
        return False
    except Exception:
        return False

def get_system_session() -> requests.Session:
    s = login_sharepoint_then_system()
    if not is_system_authenticated(s):
        s = login_sharepoint_then_system()
    return s



# ----------------- AsyncAuth for async httpx clients -----------------
class AsyncAuth:
    """Manages authentication for async httpx clients with automatic refresh."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._cookies: dict | None = None
        self._headers: dict | None = None

    async def refresh(self):
        """Refresh authentication credentials using sync login in thread."""
        def _login():
            s = get_system_session()
            return dict(s.cookies.get_dict()), dict(s.headers)
        
        cookies, headers = await asyncio.to_thread(_login)
        with self._lock:
            self._cookies, self._headers = cookies, headers

    def new_client(self) -> httpx.AsyncClient:
        """Create new httpx client with current auth and dynamic SSL verification."""
        v = _verify()
        return httpx.AsyncClient(
            headers=self._headers or {},
            cookies=Cookies(self._cookies or {}),
            timeout=httpx.Timeout(30.0, read=300.0),
            follow_redirects=True,
            http2=False,
            verify=v,
        )