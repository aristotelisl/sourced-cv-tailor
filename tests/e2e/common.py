"""Shared bits for the browser scripts: URLs, seeding through the API, and a page that records errors."""
import copy
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8000"
APP = "http://localhost:5173"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "e2e"

sys.path.insert(0, str(ROOT))
from tests.test_analyse import SPEC_EXAMPLE  # noqa: E402  (a frontend new-grad job analysis)

JOB_TITLE = SPEC_EXAMPLE["title"]


def golden_cv() -> dict:
    return json.loads((ROOT / "examples/example_frontend.tailored.json").read_text(encoding="utf-8"))


def seed_application(cv: dict | None = None, label: str = "Tailored") -> dict:
    """An application with one CV version, created through the API (no LLM calls)."""
    app = httpx.post(f"{API}/api/applications", json={"job_text": f"{JOB_TITLE} listing " * 5,
                                                      "analysis": copy.deepcopy(SPEC_EXAMPLE)}).json()
    httpx.post(f"{API}/api/applications/{app['id']}/versions",
               json={"label": label, "cv": cv or golden_cv()}).raise_for_status()
    return app


@contextmanager
def browser_page(width: int = 1500, height: int = 1000):
    """A Chromium page; on exit, fails if the app logged any error."""
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page: Page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=True)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        yield page
        browser.close()
    assert not errors, f"browser errors: {errors}"
    print("browser errors: none")


def open_in_editor(page: Page) -> None:
    from playwright.sync_api import expect
    page.goto(f"{APP}/#/tracker")
    page.get_by_text(JOB_TITLE).first.click()
    page.get_by_role("button", name="Open").first.click()
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=15_000)
