"""Extras in the browser: write a referral request (real API call) -> edit -> reopen from the tracker."""
import httpx
from playwright.sync_api import expect

from common import API, APP, OUT, browser_page, open_in_editor, seed_application

app = seed_application()

with browser_page() as page:
    open_in_editor(page)
    page.get_by_role("button", name="Referral request").click()
    page.get_by_label("Recipient").fill("Sam")
    page.get_by_label("Notes for the writer").fill("Sam and I studied together at Fernhill; Sam is on the team.")
    page.get_by_role("button", name="Write referral request").click()
    box = page.get_by_label("Referral request text")
    expect(box).to_be_visible(timeout=180_000)
    text = box.input_value()
    print("--- generated ---\n" + text + "\n---")

    box.fill(text + "\n\nP.S. Happy to buy you a coffee.")
    box.blur()
    page.wait_for_timeout(700)
    saved = httpx.get(f"{API}/api/applications/{app['id']}").json()["extras"]
    assert saved[0]["text"].endswith("Happy to buy you a coffee."), saved
    print("edit saved on blur: ok")
    box.scroll_into_view_if_needed()
    page.screenshot(path=OUT / "x1-extras.png", full_page=True)

    # Clear local state and reopen from the tracker: the saved text comes back from the database.
    page.evaluate("localStorage.clear()")
    open_in_editor(page)
    expect(page.get_by_label("Referral request text")).to_have_value(saved[0]["text"], timeout=15_000)
    print("reopened from tracker with saved text: ok")
