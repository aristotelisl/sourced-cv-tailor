"""Shared bits for the browser scripts: URLs, seeding through the API, and a page that records errors."""
import copy
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
# run.py starts its servers on their own ports, so the app you use can stay open meanwhile.
API = os.environ.get("CV_TAILOR_E2E_API", "http://127.0.0.1:8100")
APP = os.environ.get("CV_TAILOR_E2E_APP", "http://localhost:5273")
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
def browser_page(width: int = 1500, height: int = 1000, sample_chosen: bool = True, expected_errors: int = 0):
    """A Chromium page; on exit, fails if the app logged any error.

    The e2e servers use the sample profile, so by default the page starts as if "Explore with the
    sample profile" was already clicked (otherwise the app opens on profile setup).
    `expected_errors`: failed requests the script causes on purpose (the browser logs each one).
    """
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # One context, so extra tabs (page.context.new_page()) share localStorage like a real browser.
        context = browser.new_context(viewport={"width": width, "height": height}, accept_downloads=True)
        page: Page = context.new_page()
        if sample_chosen:
            context.add_init_script("if (!localStorage.getItem('cv-tailor')) localStorage.setItem('cv-tailor', "
                                 "JSON.stringify({state: {sampleChosen: true}, version: 0}))")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        yield page
        browser.close()
    assert len(errors) == expected_errors, f"browser errors: {errors}"
    print(f"browser errors: {'none' if not errors else f'{len(errors)}, as expected'}")


def open_in_editor(page: Page) -> None:
    from playwright.sync_api import expect
    page.goto(f"{APP}/#/tracker")
    page.get_by_text(JOB_TITLE).first.click()
    page.get_by_role("link", name="Open", exact=True).first.click()
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=15_000)
