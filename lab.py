#!/usr/bin/env python3
"""Start, collect or stop the isolated local PostgreSQL/MySQL research lab."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".local" / "lab.env"
PROJECT = "dbreport-lab"


def docker(args, capture=False):
    # Docker Desktop may ship an extensionless CLI alongside docker.exe.
    # Resolve the native Windows binary explicitly rather than a POSIX shim.
    executable_name = "docker.exe" if sys.platform == "win32" else "docker"
    executable = shutil.which(executable_name)
    if not executable:
        raise RuntimeError("Install and start Docker Desktop using Linux containers, then retry.")
    try:
        return subprocess.run([executable, *args], cwd=ROOT, check=True, text=True,
                              encoding="utf-8", errors="replace", capture_output=capture)
    except OSError as exc:
        code = getattr(exc, "winerror", None) or exc.errno
        raise RuntimeError(f"Cannot start native Docker CLI (OS code {code}). Check Docker Desktop and the Docker executable in PATH; no credentials were printed.") from exc


def check_local_engine():
    selected_context = os.environ.get("DOCKER_CONTEXT", "")
    selected_host = ""
    if selected_context:
        selected_host = docker(["context", "inspect", selected_context, "--format", "{{.Endpoints.docker.Host}}"], capture=True).stdout.strip()
    else:
        selected_host = os.environ.get("DOCKER_HOST", "")
    if not selected_host:
        selected_host = docker(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture=True).stdout.strip()
    if not selected_host.startswith(("unix://", "npipe://")):
        raise RuntimeError("Select a local Docker Desktop/Unix-socket context; remote Docker engines are not supported for this lab.")
    info = docker(["info", "--format", "{{.OSType}}"], capture=True).stdout.strip()
    if info != "linux":
        raise RuntimeError("Switch Docker Desktop to Linux containers and retry.")
    docker(["compose", "version"], capture=True)


def ensure_environment():
    if ENV_FILE.exists():
        values = {}
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                name, value = line.split("=", 1)
                values[name] = value
        for name in ("LAB_ROOT_PASSWORD", "LAB_DB_PASSWORD"):
            if not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", values.get(name, "")):
                raise RuntimeError("Local lab.env is incomplete. Restore your original .local/lab.env; its values are never printed.")
        return
    volumes = docker(["volume", "ls", "--filter", f"label=com.docker.compose.project={PROJECT}", "--format", "{{.Name}}"], capture=True).stdout.strip()
    if volumes:
        raise RuntimeError("Lab data volumes already exist but .local/lab.env is missing. Restore the original file before starting; do not overwrite existing lab data.")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("# Local database-lab credentials; never share or commit this file.\n")
        output.write("LAB_ROOT_PASSWORD=" + secrets.token_urlsafe(32) + "\n")
        output.write("LAB_DB_PASSWORD=" + secrets.token_urlsafe(32) + "\n")


def compose(args):
    return docker(["compose", "--project-name", PROJECT, "--env-file", str(ENV_FILE),
                   "-f", str(ROOT / "lab" / "compose.yaml"), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "collect", "status", "down"])
    parser.add_argument("--output", help="New directory for collection (existing directories are never overwritten)")
    parser.add_argument("--seed", type=int, default=491, help="Reproducible case-ID assignment seed")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("Use Python 3.12: py -3.12 lab.py up (Windows) or python3.12 lab.py up")
    check_local_engine()
    if args.action == "up":
        ensure_environment()
        print("Starting four database services. No host ports are published; collection runs through Docker exec.", flush=True)
        print("First run downloads official images and may take several minutes. No Gemini API call is made.", flush=True)
        compose(["up", "-d", "--wait", "--wait-timeout", "240"])
        print("Lab ready. Collect with: py -3.12 lab.py collect --output outputs/lab-001")
    else:
        if not ENV_FILE.exists():
            raise RuntimeError("Missing .local/lab.env. Start the lab with lab.py up or restore the original local configuration.")
        if args.action == "collect":
            output = args.output or str(ROOT / "outputs" / ("lab-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
            executable = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if not executable.exists():
                executable = Path(sys.executable)
            return subprocess.run([str(executable), str(ROOT / "lab" / "collect.py"), "--output", output,
                                   "--seed", str(args.seed), "--project", PROJECT, "--env-file", str(ENV_FILE)], cwd=ROOT).returncode
        if args.action == "status":
            compose(["ps"])
        if args.action == "down":
            compose(["down"])
            print("Stopped this lab. Database volumes and .local credentials retained.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print("Lab:", str(exc), file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError:
        print("Lab command failed. Check Docker Desktop and the command output. Do not share .local/lab.env or API keys.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted. Use lab.py status to inspect your lab.")
        raise SystemExit(130)
    except OSError as exc:
        code = getattr(exc, "winerror", None) or exc.errno
        print(f"Lab filesystem/process error (OS code {code}). Check the local directory permissions; credentials are not printed.", file=sys.stderr)
        raise SystemExit(1)
