#!/usr/bin/env python3
"""SMY Agent — hosting capability check (read-only).

Run once in cPanel Terminal:
    python3 check_environment.py

It only reads system information and opens HTTPS connections to a few public
API hosts. It does not install, write or change anything, and it never prints
environment variables, passwords or tokens.

Works with Python 3.6+ and the standard library only.
"""

import glob
import os
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import time

TIMEOUT = 8
HTTPS_TARGETS = [
    "api.telegram.org",
    "api.anthropic.com",
    "api.openai.com",
    "catalog.api.2gis.com",
    "places.googleapis.com",
    "pypi.org",
    "github.com",
]


def run(cmd):
    """Run a command, return first lines of output or a short error."""
    try:
        out = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT,
            universal_newlines=True,
        ).stdout.strip()
        return out if out else "(no output)"
    except Exception as exc:  # noqa: BLE001
        return "ERROR: %s" % type(exc).__name__


def section(title):
    print("\n=== %s ===" % title)


def line(label, value):
    print("%-28s %s" % (label + ":", value))


def check_python():
    section("Python")
    line("python3 running this", sys.version.split()[0])
    alt = sorted(glob.glob("/opt/alt/python*/bin/python3*"))
    alt = [p for p in alt if p.rstrip("0123456789.").endswith("python")]
    line("CloudLinux alt pythons", ", ".join(alt) if alt else "none found")
    if shutil.which("cloudlinux-selector"):
        out = run("cloudlinux-selector get --json --interpreter python 2>/dev/null | head -c 1500")
        line("cloudlinux-selector", out.replace("\n", " ")[:1500])
    else:
        line("cloudlinux-selector", "not available")
    venvs = sorted(glob.glob(os.path.expanduser("~/virtualenv/*/*")))
    line("existing app virtualenvs", ", ".join(venvs) if venvs else "none")
    line("pip3", run("pip3 --version"))


def check_system():
    section("System")
    line("OS", "%s %s" % (platform.system(), platform.release()))
    line("Arch", platform.machine())
    line("CPU count (visible)", str(os.cpu_count()))
    try:
        with open("/proc/meminfo") as fh:
            mem = [x.strip() for x in fh.readlines()[:3]]
        line("meminfo (host view)", " | ".join(mem))
    except Exception:  # noqa: BLE001
        line("meminfo", "unreadable")
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        if os.path.exists(path):
            line("cgroup memory limit", run("cat %s" % path))
    line("ulimit -u (processes)", run("bash -c 'ulimit -u'"))
    line("ulimit -v (virt mem KB)", run("bash -c 'ulimit -v'"))
    if os.path.isdir("/proc/lve"):
        line("CloudLinux LVE", "present")
    line("disk usage home", run("du -sh ~ 2>/dev/null | tail -1"))
    line("quota", run("quota -s 2>/dev/null | tail -2 | tr -s ' '"))


def check_tools():
    section("Tools")
    for tool, cmd in (
        ("git", "git --version"),
        ("mysql client", "mysql --version"),
        ("mysqldump", "mysqldump --version"),
        ("node", "node --version"),
        ("crontab", "crontab -l >/dev/null 2>&1 && echo 'crontab readable' || echo 'no crontab or not permitted'"),
        ("passenger", "ls -d /usr/share/passenger /opt/cpanel/ea-ruby*/root/usr/share/passenger 2>/dev/null | head -2"),
        ("curl", "curl --version | head -1"),
    ):
        exe = cmd.split()[0]
        if exe in ("ls",) or shutil.which(exe):
            line(tool, run(cmd))
        else:
            line(tool, "not found")


def check_https():
    section("Outbound HTTPS (TLS handshake only)")
    ctx = ssl.create_default_context()
    for host in HTTPS_TARGETS:
        start = time.time()
        try:
            with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=host):
                    pass
            line(host, "OK (%d ms)" % ((time.time() - start) * 1000))
        except Exception as exc:  # noqa: BLE001
            line(host, "FAIL %s" % type(exc).__name__)


def check_python_packages():
    section("Python build capability")
    try:
        import sqlite3

        line("sqlite3 module", sqlite3.sqlite_version)
    except Exception:  # noqa: BLE001
        line("sqlite3 module", "missing")
    line("ssl", ssl.OPENSSL_VERSION)
    line("gcc (for native wheels)", run("gcc --version | head -1") if shutil.which("gcc") else "not found")


def main():
    print("SMY Agent hosting check — %s" % time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    print("Home: %s" % os.path.expanduser("~"))
    check_python()
    check_system()
    check_tools()
    check_https()
    check_python_packages()
    section("Done")
    print("Copy everything above into Claude Code. No secrets are printed by this script.")


if __name__ == "__main__":
    main()
