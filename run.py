#!/usr/bin/env python3
"""Start the local demo on Windows, macOS or Linux with Python 3.12."""
import argparse
import hashlib
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
import re

ROOT = Path(__file__).resolve().parent


def configure_gemini():
    """Local terminal only. Never send a key through the browser or command line."""
    print("Gemini setup: create your key at https://aistudio.google.com/apikey")
    print("The key will be stored on THIS computer in .local/settings.json. Do not share that file.")
    key = getpass.getpass("Gemini API key (hidden): ").strip()
    if not key or any(char.isspace() for char in key):
        raise ValueError("API key must be nonempty and contain no whitespace")
    model = input("Gemini model [gemini-flash-latest]: ").strip() or "gemini-flash-latest"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", model):
        raise ValueError("Use a model ID, not a URL (for example gemini-flash-latest)")
    directory = ROOT / ".local"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError("Existing local settings must be a JSON object; file was not changed")
    settings.update(AI_PROVIDER="gemini", GEMINI_API_KEY=key, GEMINI_MODEL=model)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if os.name != "nt":
        os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(settings, output, indent=2)
        output.write("\n")
    print("Saved local Gemini settings. Connection is verified only after a successful API call.")
    if any(name in os.environ for name in ("AI_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL")):
        print("Note: existing environment variables take precedence over this local file.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000, help="Local web port (default: 8000)")
    parser.add_argument("--install-only", action="store_true", help="Prepare dependencies without starting the server")
    parser.add_argument("--reinstall", action="store_true", help="Recheck dependencies against the pinned lock file")
    parser.add_argument("--configure-gemini", action="store_true", help="Prompt for a Gemini key/model locally, save settings and start the web app")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("Use Python 3.12: Windows: py -3.12 run.py; macOS/Linux: python3.12 run.py")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    if args.configure_gemini:
        configure_gemini()
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating local Python environment (.venv)...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    lock = ROOT / "requirements.lock.txt"
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    stamp = environment / ".db-report-dependencies.sha256"
    if args.reinstall or not stamp.exists() or stamp.read_text().strip() != digest:
        print("Installing dependencies. The first installation needs Internet access...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                        "-r", str(lock)], cwd=ROOT, check=True)
        stamp.write_text(digest + "\n")
    if args.install_only:
        print("Installation complete. Run the same command without --install-only to start.")
        return 0
    print(f"\nOn this computer, open: http://127.0.0.1:{args.port}", flush=True)
    print("Keep this terminal open. Press Ctrl+C to stop. Select Gemini in the web app after configuration.\n", flush=True)
    return subprocess.run([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                           "--port", str(args.port)], cwd=ROOT).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Installation failed (exit {error.returncode}). Check the error above and Internet access.", file=sys.stderr)
        raise SystemExit(error.returncode)
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(130)
    except (ValueError, OSError) as error:
        # Do not print user-entered values, settings contents or credentials.
        print("Setup failed. Check that the model ID is valid and the local settings directory is writable.", file=sys.stderr)
        raise SystemExit(1)
