"""Each application has its own URL; unsaved edits are kept per application (no LLM calls)."""
import httpx
from playwright.sync_api import Page, expect

from common import API, APP, JOB_TITLE, browser_page, seed_application

a = seed_application()["id"]
b = seed_application()["id"]


def bullets(page: Page) -> int:
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=15_000)
    return page.get_by_role("button", name="Remove bullet").count()


def remove_one(page: Page) -> None:
    before = bullets(page)
    page.get_by_role("button", name="Remove bullet").first.click()
    expect(page.get_by_role("button", name="Remove bullet")).to_have_count(before - 1)


with browser_page(1500, 1000, expected_errors=1) as page:  # 1: the missing application's 404
    page.goto(f"{APP}/#/applications/{a}")
    full = bullets(page)
    remove_one(page)
    page.reload()
    assert bullets(page) == full - 1
    print("unsaved edit survives a reload: ok")

    other = page.context.new_page()
    other.goto(f"{APP}/#/applications/{b}")
    assert bullets(other) == full
    remove_one(other)
    remove_one(other)
    page.reload()
    assert bullets(page) == full - 1
    other.reload()
    assert bullets(other) == full - 2
    other.close()
    print("two tabs on two applications keep their own edits: ok")

    with page.expect_download():
        page.get_by_role("button", name="Download PDF").click()
    newest = httpx.get(f"{API}/api/applications/{a}").json()["versions"][0]["id"]
    expect(page).to_have_url(f"{APP}/#/applications/{a}/versions/{newest}")
    page.reload()
    assert bullets(page) == full - 1
    print("export saves a version and the URL points at it: ok")

    page.get_by_role("link", name="Tracker").click()
    # Newest activity first: application a was just exported.
    page.get_by_role("row").filter(has_text=JOB_TITLE).first.get_by_text(JOB_TITLE).click()
    page.get_by_role("link", name="Open", exact=True).last.click()  # the oldest version of the expanded row
    expect(page).to_have_url(f"{APP}/#/applications/{a}/versions/"
                             f"{httpx.get(f'{API}/api/applications/{a}').json()['versions'][-1]['id']}")
    assert bullets(page) == full
    page.go_back()
    expect(page).to_have_url(f"{APP}/#/tracker")
    print("tracker opens a version by URL; back returns to the tracker: ok")

    page.get_by_role("link", name="Tailor").click()
    expect(page).to_have_url(f"{APP}/#/applications/{a}/versions/"
                             f"{httpx.get(f'{API}/api/applications/{a}').json()['versions'][-1]['id']}")
    page.get_by_role("button", name="New application").click()
    expect(page).to_have_url(f"{APP}/#/new")
    expect(page.get_by_label("Job listing")).to_have_value("")
    print("Tailor goes back to the open application; New application starts empty: ok")

    page.goto(f"{APP}/#/applications/99999")
    expect(page).to_have_url(f"{APP}/#/new")
    expect(page.get_by_text("Application 99999 not found")).to_be_visible()
    print("a missing application says so: ok")
