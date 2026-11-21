"""Run the browser end-to-end scripts against fresh servers.

    .venv\\Scripts\\python tests/e2e/run.py                 # all e2e_*.py
    .venv\\Scripts\\python tests/e2e/run.py e2e_tracker.py  # one script

Starts the backend (:8100) and Vite (:5273) with a temp SQLite file and a temp copy of
profile.yaml, so your real tracker and profile are never touched. They use their own ports, so the
app you normally run (:8000 and :5173) can stay open. Screenshots and PDFs go to
out/e2e/. e2e_tailor, e2e_extras and e2e_polish call the real Claude API (a few cents each).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = sys.executable


def wait_for(url: str, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise SystemExit(f"{url} didn't come up")


def stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":  # npm starts node as a child: kill the whole tree
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    proc.wait()


API_PORT, APP_PORT = 8100, 5273
API, APP = f"http://127.0.0.1:{API_PORT}", f"http://localhost:{APP_PORT}"


def main(names: list[str]) -> int:
    for url in (f"{API}/api/health", APP):
        try:
            httpx.get(url, timeout=1)
            raise SystemExit(f"Something is already running at {url}; stop it first.")
        except httpx.HTTPError:
            pass

    scripts = [HERE / n for n in names] or sorted(HERE.glob("e2e_*.py"))
    tmp = Path(tempfile.mkdtemp(prefix="cv-tailor-e2e-"))
    profile = tmp / "profile.yaml"
    shutil.copy(ROOT / "examples/profile.example.yaml", profile)
    env = os.environ | {"CV_TAILOR_DB": str(tmp / "e2e.db"), "CV_TAILOR_PROFILE": str(profile),
                        "CV_TAILOR_API_PORT": str(API_PORT), "CV_TAILOR_E2E_API": API, "CV_TAILOR_E2E_APP": APP}

    servers = [
        subprocess.Popen([PYTHON, "-m", "uvicorn", "backend.main:app", "--port", str(API_PORT)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        subprocess.Popen(f"npm run dev -- --port {APP_PORT} --strictPort", cwd=ROOT / "frontend", env=env, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    ]
    failed = []
    try:
        wait_for(f"{API}/api/health")
        wait_for(APP)
        out = ROOT / "out" / "e2e"
        for script in scripts:
            print(f"\n=== {script.name}", flush=True)
            started = time.time()
            # Each script starts with an empty tracker.
            for path in tmp.glob("e2e.db*"):
                path.unlink(missing_ok=True)
            if subprocess.run([PYTHON, str(script), str(out)], cwd=HERE, env=env).returncode:
                failed.append(script.name)
            print(f"--- {script.name}: {'FAILED' if script.name in failed else 'ok'} ({time.time() - started:.0f}s)")
    finally:
        for proc in servers:
            stop(proc)
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(scripts) - len(failed)}/{len(scripts)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
