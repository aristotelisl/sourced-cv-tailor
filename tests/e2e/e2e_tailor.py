"""The main flow, with real API calls: paste -> analyse -> tailor -> edit -> export -> reload."""
import time

from playwright.sync_api import expect

from common import APP, OUT, ROOT, browser_page

job_text = (ROOT / "tests/fixtures/jobs/uk_backend_gbp.txt").read_text(encoding="utf-8")

with browser_page(1600, 1000) as page:
    page.goto(APP)
    page.get_by_label("Job listing").fill(job_text)
    page.screenshot(path=OUT / "1-paste.png")

    started = time.time()
    page.get_by_role("button", name="Analyse").click()
    expect(page.get_by_role("button", name="Tailor CV")).to_be_visible(timeout=90_000)
    print(f"analysed in {time.time() - started:.0f}s")

    started = time.time()
    page.get_by_role("button", name="Tailor CV").click()
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=240_000)
    print(f"tailored in {time.time() - started:.0f}s")
    expect(page.get_by_text("1 page")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(1000)
    page.screenshot(path=OUT / "2-tailored.png", full_page=True)

    # Edit the first bullet and check the preview follows.
    page.get_by_label("Bullet 1", exact=True).first.fill("EDITED BULLET TEXT for the end-to-end test")
    frame = page.frame_locator("iframe[title='CV preview']")
    expect(frame.get_by_text("EDITED BULLET TEXT")).to_be_visible(timeout=10_000)
    print("preview follows edits: ok")

    # Tick the suggested UK header line and check it reaches the preview.
    page.get_by_text("UK Pre-Settled Status").first.click()
    expect(frame.get_by_text("UK Pre-Settled Status")).to_be_visible(timeout=10_000)
    print("header extra reaches preview: ok")

    page.get_by_role("button", name="Remove bullet").first.click()
    expect(page.get_by_text("checking fit…")).to_be_hidden(timeout=30_000)
    with page.expect_download(timeout=60_000) as dl:
        page.get_by_role("button", name="Download PDF").click()
    path = OUT / dl.value.suggested_filename
    dl.value.save_as(path)
    print(f"downloaded {path.name} ({path.stat().st_size} bytes)")

    page.reload()
    expect(page.get_by_role("button", name="Download PDF")).to_be_visible(timeout=10_000)
    print("state survives reload: ok")
