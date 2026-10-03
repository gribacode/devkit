"""Общие помощники хуков devkit. Только стандартная библиотека, совместимо с Python 3.9."""
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional

STATE_TTL_SECONDS = 7 * 24 * 3600
_ENV_ALLOWED_SUFFIXES = (".example", ".sample", ".template")
_SECRET_EXTENSIONS = (".pem", ".key", ".p12", ".pfx")


def read_input() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def enabled(name: str) -> bool:
    return os.environ.get("DEVKIT_" + name, "1") != "0"


def claude_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".claude")


def worklog_dir() -> str:
    return os.path.join(claude_dir(), "worklog")


def state_path(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return os.path.join(claude_dir(), "devkit", "state", safe + ".json")


@contextmanager
def session_state(session_id: str) -> Iterator[Dict[str, Any]]:
    # Блокировка нужна, потому что PostToolUse на параллельные правки пишут одновременно
    path = state_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read()
        try:
            state = json.loads(raw) if raw.strip() else {}
        except ValueError:
            state = {}
        if not isinstance(state, dict):
            state = {}
        yield state
        f.seek(0)
        f.truncate()
        json.dump(state, f)


def cleanup_state(now: Optional[float] = None) -> None:
    folder = os.path.dirname(state_path("x"))
    if not os.path.isdir(folder):
        return
    limit = (now or time.time()) - STATE_TTL_SECONDS
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        try:
            if os.path.getmtime(path) < limit:
                os.remove(path)
        except OSError:
            pass


def find_up(start: str, names: List[str]) -> Optional[str]:
    current = os.path.abspath(start)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        for name in names:
            candidate = os.path.join(current, name)
            if os.path.exists(candidate):
                return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def find_bin(start: str, name: str) -> Optional[str]:
    found = find_up(start, [os.path.join("node_modules", ".bin", name)])
    return found if found and os.access(found, os.X_OK) else None


def node_env() -> Dict[str, str]:
    # Хук может стартовать без инициализации fnm, тогда node берем из алиаса default
    env = dict(os.environ)
    if shutil.which("node", path=env.get("PATH")):
        return env
    fnm_dir = env.get("FNM_DIR") or os.path.join(os.path.expanduser("~"), ".local", "share", "fnm")
    fallback = os.path.join(fnm_dir, "aliases", "default", "bin")
    if os.path.isdir(fallback):
        env["PATH"] = fallback + os.pathsep + env.get("PATH", "")
    return env


def is_secret_path(path: str) -> bool:
    if not path:
        return False
    full = os.path.abspath(os.path.expanduser(path))
    home = os.path.expanduser("~")
    for folder in (".ssh", ".aws"):
        root = os.path.join(home, folder)
        if full == root or full.startswith(root + os.sep):
            return True
    name = os.path.basename(full)
    if name == ".env":
        return True
    if name.startswith(".env."):
        return not name.endswith(_ENV_ALLOWED_SUFFIXES)
    if name.endswith(_SECRET_EXTENSIONS):
        return True
    if name.startswith(("id_rsa", "id_ed25519")) and not name.endswith(".pub"):
        return True
    if name.startswith("credentials") and name.endswith(".json"):
        return True
    return name == ".npmrc"


def read_jsonc(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out: List[str] = []
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    return json.loads(cleaned)


def _git(args: List[str], cwd: str) -> str:
    try:
        proc = subprocess.run(["git", "-C", cwd] + args, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def repo_root(cwd: str) -> str:
    return _git(["rev-parse", "--show-toplevel"], cwd) if cwd and os.path.isdir(cwd) else ""


def git_branch(repo: str) -> str:
    # symbolic-ref работает и на ветке без коммитов, для detached HEAD берем короткий хеш
    if not repo:
        return ""
    return _git(["symbolic-ref", "--short", "HEAD"], repo) or _git(["rev-parse", "--short", "HEAD"], repo)


def project_title(cwd: Optional[str]) -> str:
    cwd = cwd or os.getcwd()
    return os.path.basename(repo_root(cwd) or cwd.rstrip(os.sep)) or "Claude"


def notify_mac(title: str, message: str) -> None:
    if os.environ.get("DEVKIT_NOTIFY_DRYRUN") == "1":
        sys.stderr.write("NOTIFY|%s|%s\n" % (title, message))
        return

    def quote(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    script = 'display notification %s with title %s sound name "Glass"' % (quote(message), quote(title))
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def shorten(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def run(main: Callable[[], Optional[int]]) -> None:
    try:
        code = main() or 0
    except Exception:
        code = 0
    sys.exit(code)
