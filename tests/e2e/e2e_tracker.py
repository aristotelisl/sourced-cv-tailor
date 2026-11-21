"""Tracker flow in the browser, seeded through the API (no LLM calls)."""
import sys
from datetime import date

import httpx
from playwright.sync_api import expect

from common import API, APP, JOB_TITLE, OUT, browser_page, seed_application

app = seed_application()
today = date.today().strftime("%#d %b %Y" if sys.platform == "win32" else "%-d %b %Y")

with browser_page(1400, 900) as page:
    page.goto(f"{APP}/#/tracker")
    row = page.get_by_role("row").filter(has_text=JOB_TITLE)
    expect(row).to_be_visible()
    row.get_by_label("Status").select_option("applied")
    expect(row.get_by_text(today)).to_be_visible()
    print("status -> applied records today's date: ok")

    row.get_by_text(JOB_TITLE).click()
    notes = page.get_by_label("Notes")
    notes.fill("Referral from a friend on the team")
    notes.blur()
    page.wait_for_timeout(500)
    assert httpx.get(f"{API}/api/applications/{app['id']}").json()["notes"] == "Referral from a friend on the team"
    print("notes saved on blur: ok")
    page.screenshot(path=OUT / "t1-tracker.png", full_page=True)

    page.get_by_role("button", name="Open").first.click()
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=15_000)
    assert page.url.endswith("#/")
    print("open version in editor: ok")

    page.get_by_role("button", name="Remove bullet").first.click()
    expect(page.get_by_text("1 page")).to_be_visible(timeout=30_000)
    expect(page.get_by_text("checking fit…")).to_be_hidden(timeout=30_000)
    with page.expect_download(timeout=60_000) as dl:
        page.get_by_role("button", name="Download PDF").click()
    print("exported", dl.value.suggested_filename)

    detail = httpx.get(f"{API}/api/applications/{app['id']}").json()
    assert [v["label"] for v in detail["versions"]] == ["Exported", "Tailored"], detail["versions"]
    assert detail["cv_version_id"] == detail["versions"][0]["id"]
    print("export saved a new version and marked it sent: ok")

    page.get_by_role("link", name="Tracker").click()
    row = page.get_by_role("row").filter(has_text=JOB_TITLE)
    expect(row.get_by_role("cell", name="2", exact=True)).to_be_visible()
    row.get_by_text(JOB_TITLE).click()
    expect(page.get_by_text("sent")).to_be_visible()
    with page.expect_download() as dl:
        page.get_by_role("link", name="PDF").last.click()  # the older "Tailored" version
    path = OUT / ("old-" + dl.value.suggested_filename)
    dl.value.save_as(path)
    print(f"re-rendered old version: {path.name} ({path.stat().st_size} bytes)")
    page.screenshot(path=OUT / "t2-tracker-versions.png", full_page=True)

    page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name="Delete").click()
    expect(page.get_by_text("No applications yet.")).to_be_visible()
    print("delete: ok")
