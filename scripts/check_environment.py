#!/usr/bin/env python3
"""SMY Agent - hosting environment check for hostmaster.uz cPanel.

Run ONCE in cPanel Terminal and paste the full output back into the
Claude Code session:

    python3 scripts/check_environment.py

Options:
    --offline     skip network checks (outbound HTTPS, PyPI)
    --no-redact   do not mask the account username / home path

What it does: read-only inspection. It changes nothing on the account
(a throw-away virtualenv is created in a temp dir and deleted), sends no
credentials anywhere, and never prints environment variable values.

Compatibility: Python 3.5+ standard library only, because the host's
default ``python3`` may be old. Do not use f-strings or newer syntax here.
"""

import argparse
import getpass
import json
import os
import platform
import resource
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time

try:  # Python 3 only; the script refuses to run on Python 2 below.
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    HTTPError = URLError = Exception  # type: ignore
    Request = urlopen = None  # type: ignore

SCRIPT_VERSION = "1.0.0"

# Endpoints are only contacted with an unauthenticated GET/HEAD to learn
# whether the host can reach them. Any HTTP status (even 401/404) = reachable.
NETWORK_TARGETS = [
    ("Anthropic API", "https://api.anthropic.com/"),
    ("Telegram Bot API", "https://api.telegram.org/"),
    ("2GIS API", "https://catalog.api.2gis.com/"),
    ("Google Places API", "https://places.googleapis.com/"),
    ("Yandex Search API", "https://search-maps.yandex.ru/"),
    ("PyPI", "https://pypi.org/simple/a2wsgi/"),
    ("GitHub", "https://github.com/"),
]

TOOLS = [
    "git",
    "pip3",
    "gcc",
    "make",
    "mysql",
    "mysqldump",
    "mariadb",
    "psql",
    "redis-cli",
    "node",
    "npm",
    "docker",
    "crontab",
    "curl",
    "tar",
    "gzip",
    "passenger",
    "passenger-config",
    "cloudlinux-selector",
    "selectorctl",
    "lveinfo",
    "quota",
]

# Only the NAMES of these variables are reported (set / not set), never values.
INTERESTING_ENV_NAMES = [
    "VIRTUAL_ENV",
    "PASSENGER_APP_ENV",
    "PASSENGER_BASE_URI",
    "PYTHONPATH",
    "LANG",
    "LC_ALL",
    "TZ",
    "HTTPS_PROXY",
    "HTTP_PROXY",
]

_REDACTIONS = []  # list of (secret_text, replacement)


def redact(text):
    """Replace configured sensitive substrings (home path, username)."""
    if not isinstance(text, str):
        text = str(text)
    for needle, replacement in _REDACTIONS:
        if needle:
            text = text.replace(needle, replacement)
    return text


def setup_redaction(enabled):
    del _REDACTIONS[:]
    if not enabled:
        return
    home = os.path.expanduser("~")
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    # Longest first so the home path is replaced before the bare username.
    if home and home not in ("/", "~"):
        _REDACTIONS.append((home, "~"))
    if user and len(user) >= 3 and user != "root":
        _REDACTIONS.append((user, "<user>"))


def out(line=""):
    print(redact(line))
    sys.stdout.flush()


def section(title):
    out("")
    out("=" * 70)
    out("## " + title)
    out("=" * 70)


def item(label, value):
    out("{:<34} {}".format(label + ":", value))


def run(cmd, timeout=20):
    """Run a command, return (returncode, combined output). Never raises."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            universal_newlines=True,
        )
        return proc.returncode, (proc.stdout or "").strip()
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out after {}s".format(timeout)
    except Exception as exc:  # pragma: no cover - defensive
        return 1, "error: {}".format(exc.__class__.__name__)


def first_line(text, limit=120):
    line = (text or "").splitlines()[0] if text else ""
    return line[:limit]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check_system():
    section("1. System")
    item("Script version", SCRIPT_VERSION)
    item("Checked at (UTC)", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
    item("Platform", platform.platform())
    item("Machine", platform.machine())
    item("Hostname", socket.gethostname())
    for path in ("/etc/os-release", "/etc/redhat-release", "/etc/cloudlinux-release"):
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    content = fh.read()
                pretty = ""
                for line in content.splitlines():
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip('"')
                item(path, pretty or first_line(content))
            except Exception:
                item(path, "unreadable")
    item("CloudLinux", "yes" if os.path.exists("/etc/cloudlinux-release") else "no / unknown")
    item("Home directory", os.path.expanduser("~"))
    item("Current directory", os.getcwd())
    item("umask", oct(_current_umask()))


def _current_umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def check_python():
    section("2. Python")
    item("Running interpreter", sys.executable)
    item("Version", sys.version.replace("\n", " "))
    item("OpenSSL", ssl.OPENSSL_VERSION)
    try:
        import sqlite3

        item("sqlite3", sqlite3.sqlite_version)
    except Exception:
        item("sqlite3", "NOT available")
    for mod in ("venv", "ensurepip", "zoneinfo", "ctypes", "_ssl"):
        try:
            __import__(mod)
            item("module " + mod, "ok")
        except Exception:
            item("module " + mod, "MISSING")

    out("")
    out("Other Python interpreters found:")
    candidates = set()
    for base in ("/opt/alt", "/opt/cpanel", "/usr/local/bin", "/usr/bin"):
        if not os.path.isdir(base):
            continue
        if base.startswith("/opt"):
            for name in sorted(os.listdir(base)):
                if name.startswith(("python", "ea-python")):
                    for binname in ("bin/python3", "root/usr/bin/python3"):
                        path = os.path.join(base, name, binname)
                        if os.path.exists(path):
                            candidates.add(path)
        else:
            for name in os.listdir(base):
                if name.startswith("python3") and not name.endswith("-config"):
                    candidates.add(os.path.join(base, name))
    if not candidates:
        out("  (none)")
    for path in sorted(candidates):
        code, text = run([path, "--version"], timeout=10)
        out("  {:<45} {}".format(path, first_line(text) if code == 0 else "error"))

    selector = shutil.which("cloudlinux-selector")
    if selector:
        out("")
        out("cloudlinux-selector (Setup Python App) versions:")
        code, text = run([selector, "get", "--json", "--interpreter", "python"], timeout=30)
        if code == 0:
            try:
                data = json.loads(text)
                versions = data.get("available_versions", {})
                for ver in sorted(versions):
                    info = versions[ver] or {}
                    out("  {:<8} enabled={} status={}".format(ver, info.get("enabled"), info.get("status")))
                if not versions:
                    out("  " + first_line(text, 300))
            except ValueError:
                out("  " + first_line(text, 300))
        else:
            out("  failed: " + first_line(text, 300))
        code, text = run([selector, "get", "--json", "--interpreter", "python", "--user", getpass.getuser()], 30)
        if code == 0:
            out("  existing Python apps: " + first_line(text, 500))


def check_tools():
    section("3. Command-line tools")
    for tool in TOOLS:
        path = shutil.which(tool)
        if not path:
            item(tool, "-- not found")
            continue
        version = ""
        if tool not in ("crontab", "quota", "selectorctl", "cloudlinux-selector", "lveinfo"):
            code, text = run([path, "--version"], timeout=10)
            version = first_line(text, 80) if code == 0 else ""
        item(tool, "{} {}".format(path, version).strip())


def check_database():
    section("4. MySQL / MariaDB")
    client = shutil.which("mysql") or shutil.which("mariadb")
    if not client:
        out("No mysql client found in PATH.")
        return
    code, text = run([client, "--version"], timeout=10)
    item("Client version", first_line(text))
    # Uses ~/.my.cnf if it exists; otherwise fails harmlessly. Never prompts.
    has_mycnf = os.path.exists(os.path.expanduser("~/.my.cnf"))
    item("~/.my.cnf present", "yes" if has_mycnf else "no")
    code, text = run(
        [client, "--connect-timeout=5", "-N", "-B", "-e", "SELECT VERSION(), @@character_set_server, @@collation_server"],
        timeout=15,
    )
    if code == 0:
        item("Server version / charset", first_line(text))
    else:
        item("Server version", "not queried (no credentials) - check cPanel > MySQL Databases")


def check_network(offline):
    section("5. Outbound HTTPS")
    if offline:
        out("Skipped (--offline).")
        return
    ctx = ssl.create_default_context()
    for label, url in NETWORK_TARGETS:
        started = time.time()
        try:
            req = Request(url, headers={"User-Agent": "SMY-Agent-envcheck/" + SCRIPT_VERSION})
            resp = urlopen(req, timeout=10, context=ctx)
            status = "HTTP {}".format(resp.getcode())
            resp.close()
            result = "OK ({})".format(status)
        except HTTPError as exc:
            result = "OK (HTTP {}, reachable)".format(exc.code)
        except URLError as exc:
            result = "FAIL ({})".format(exc.reason)
        except Exception as exc:
            result = "FAIL ({}: {})".format(exc.__class__.__name__, exc)
        elapsed = int((time.time() - started) * 1000)
        item(label, "{} {} ms".format(result, elapsed))


def check_cron():
    section("6. Cron")
    path = shutil.which("crontab")
    item("crontab binary", path or "not found")
    if path:
        code, text = run([path, "-l"], timeout=10)
        if code == 0:
            lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
            # Count only: cron lines may contain credentials.
            item("Existing cron entries", str(len(lines)))
        else:
            item("crontab -l", first_line(text))
    out("Minimum interval: check cPanel > Cron Jobs (shared hosts often allow 1 or 5 min).")


def check_limits():
    section("7. Resource limits")
    names = [
        ("RLIMIT_NPROC", "max processes"),
        ("RLIMIT_AS", "max address space (bytes)"),
        ("RLIMIT_DATA", "max data segment (bytes)"),
        ("RLIMIT_CPU", "max CPU time (s)"),
        ("RLIMIT_NOFILE", "max open files"),
        ("RLIMIT_FSIZE", "max file size (bytes)"),
    ]
    for const, label in names:
        if hasattr(resource, const):
            soft, hard = resource.getrlimit(getattr(resource, const))
            item(label, "soft={} hard={}".format(_fmt_limit(soft), _fmt_limit(hard)))
    item("CPU count (visible)", str(os.cpu_count()))
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith(("MemTotal", "MemAvailable")):
                    out("  " + line.strip())
    except Exception:
        pass
    if os.path.exists("/proc/lve/list") or shutil.which("lveinfo"):
        out("CloudLinux LVE detected: exact RAM/CPU/EP/NPROC limits are shown in")
        out("cPanel > Resource Usage. Please copy them here manually.")
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
        item("Disk (home fs) total/free GB", "{:.1f} / {:.1f}".format(usage.total / 1e9, usage.free / 1e9))
    except Exception:
        pass
    quota = shutil.which("quota")
    if quota:
        code, text = run([quota, "-s"], timeout=10)
        out("quota -s:")
        for line in text.splitlines()[:6]:
            out("  " + line)


def _fmt_limit(value):
    return "unlimited" if value == resource.RLIM_INFINITY else str(value)


def check_pip_venv(offline):
    section("8. Virtualenv + pip install")
    tmp = tempfile.mkdtemp(prefix="smy-envcheck-")
    try:
        venv_dir = os.path.join(tmp, "venv")
        code, text = run([sys.executable, "-m", "venv", venv_dir], timeout=120)
        if code != 0:
            item("python -m venv", "FAIL: " + first_line(text, 200))
            return
        item("python -m venv", "ok")
        pip = os.path.join(venv_dir, "bin", "pip")
        code, text = run([pip, "--version"], timeout=30)
        item("pip in venv", first_line(text) if code == 0 else "FAIL")
        if offline:
            out("Package download test skipped (--offline).")
            return
        dl = os.path.join(tmp, "dl")
        code, text = run([pip, "download", "--no-deps", "--disable-pip-version-check", "-d", dl, "a2wsgi"], 120)
        item("pip download a2wsgi", "ok" if code == 0 else "FAIL: " + first_line(text.splitlines()[-1] if text else ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_hosting_layout():
    section("9. cPanel layout, logs, Passenger, git")
    home = os.path.expanduser("~")
    for name in ("public_html", "logs", "virtualenv", "repositories", "tmp", ".my.cnf", ".cpanel"):
        path = os.path.join(home, name)
        if os.path.exists(path):
            mode = oct(os.stat(path).st_mode & 0o777)
            item("~/" + name, "exists, mode " + mode)
        else:
            item("~/" + name, "-- missing")
    logs = os.path.join(home, "logs")
    if os.path.isdir(logs):
        entries = sorted(os.listdir(logs))[:15]
        item("~/logs entries (first 15)", ", ".join(entries) or "(empty)")
    venvs = os.path.join(home, "virtualenv")
    if os.path.isdir(venvs):
        found = []
        for root, dirs, _files in os.walk(venvs):
            depth = root[len(venvs) :].count(os.sep)
            if depth >= 2:
                dirs[:] = []
            if os.path.exists(os.path.join(root, "bin", "activate")):
                found.append(os.path.relpath(root, venvs))
        item("Existing app virtualenvs", ", ".join(found) or "(none)")
    out("Passenger is configured per app via .htaccess by Setup Python App;")
    out("existing Passenger directives in ~/public_html/.htaccess:")
    htaccess = os.path.join(home, "public_html", ".htaccess")
    if os.path.exists(htaccess):
        try:
            with open(htaccess) as fh:
                lines = [ln.strip() for ln in fh if ln.strip().lower().startswith("passenger")]
            for ln in lines[:10]:
                out("  " + ln)
            if not lines:
                out("  (none)")
        except Exception:
            out("  (unreadable)")
    else:
        out("  (no .htaccess)")


def check_env_names():
    section("10. Environment variable names (values never shown)")
    for name in INTERESTING_ENV_NAMES:
        item(name, "set" if os.environ.get(name) else "not set")


def manual_steps():
    section("11. Please also report manually")
    out("- cPanel > Setup Python App: list of Python versions in the dropdown.")
    out("- Does the 'Application startup file' field accept a nested path")
    out("  (deployment/cpanel/passenger_wsgi.py)?")
    out("- Can you add Environment variables in the Python App page?")
    out("- cPanel > Resource Usage: limits for CPU, RAM (PMEM), EP, NPROC, IO.")
    out("- cPanel > Cron Jobs: smallest allowed interval.")
    out("- cPanel > MySQL Databases: server version shown on the page.")
    out("- cPanel > Git Version Control: is it present?")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SMY Agent hosting environment check (read-only).")
    parser.add_argument("--offline", action="store_true", help="skip network checks")
    parser.add_argument("--no-redact", action="store_true", help="do not mask username / home path")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 5):
        print("Python 3.5+ required to run this check; found " + sys.version.split()[0])
        return 2

    setup_redaction(not args.no_redact)
    out("SMY Agent - environment check (read-only). Paste ALL output back to Claude Code.")
    checks = [
        check_system,
        check_python,
        check_tools,
        check_database,
        lambda: check_network(args.offline),
        check_cron,
        check_limits,
        lambda: check_pip_venv(args.offline),
        check_hosting_layout,
        check_env_names,
        manual_steps,
    ]
    failures = 0
    for check in checks:
        try:
            check()
        except Exception as exc:  # one broken check must not hide the others
            failures += 1
            out("!! check failed: {}: {}".format(exc.__class__.__name__, exc))
    section("Done")
    out("Checks with internal errors: {}".format(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
