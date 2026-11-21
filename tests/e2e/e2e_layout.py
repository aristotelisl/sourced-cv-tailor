"""Split view: the editor and the preview scroll independently (no LLM calls)."""
from playwright.sync_api import expect

from common import OUT, browser_page, open_in_editor, seed_application

seed_application()

SCROLL_INFO = """el => {
  let n = el;
  while (n && getComputedStyle(n).overflowY !== 'auto') n = n.parentElement;
  return n && { top: n.scrollTop, max: n.scrollHeight - n.clientHeight };
}"""

with browser_page(1400, 800) as page:
    open_in_editor(page)
    left = page.get_by_role("button", name="Remove bullet").first
    right = page.get_by_title("CV preview")
    expect(right).to_be_visible()

    assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight"), "page itself still scrolls"
    page.screenshot(path=OUT / "l1-split-top.png")

    # Scroll the preview column to its bottom: the editor column must not move.
    right.hover()
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(300)
    r = right.evaluate(SCROLL_INFO)
    l = left.evaluate(SCROLL_INFO)
    assert r["max"] > 0 and r["top"] == r["max"], r
    assert l["top"] == 0, l
    print("preview scrolls to the bottom on its own: ok")
    page.screenshot(path=OUT / "l2-preview-bottom.png")

    # And the editor scrolls without moving the preview.
    page.mouse.move(300, 400)
    page.mouse.wheel(0, 800)
    page.wait_for_timeout(300)
    assert left.evaluate(SCROLL_INFO)["top"] > 0
    assert right.evaluate(SCROLL_INFO)["top"] == r["top"]
    print("editor scrolls on its own: ok")
    page.screenshot(path=OUT / "l3-editor-scrolled.png")
