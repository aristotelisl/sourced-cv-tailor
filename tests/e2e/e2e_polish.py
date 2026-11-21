"""M7 in the browser: drag to reorder, swap/add bullets from the profile, rewrite a bullet and answer
a gap question into profile.yaml (the last two call the real API; the profile is a temp copy)."""
import os
from pathlib import Path

import httpx
import yaml
from playwright.sync_api import expect

from common import API, OUT, ROOT, browser_page, golden_cv, open_in_editor, seed_application

PROFILE = Path(os.environ["CV_TAILOR_PROFILE"])
assert PROFILE.resolve() != (ROOT / "data/profile.yaml").resolve(), "run through tests/e2e/run.py"
QUESTION = "Did you use Docker at Lumora?"

cv = golden_cv()
cv["gap_report"]["questions"].insert(0, QUESTION)
seed_application(cv)
bank = httpx.get(f"{API}/api/profile/bank").json()
cited = {part for s in cv["sections"] for e in s.get("entries", []) for b in e["bullets"]
         for part in b["source"].split("+")}
unused = [item for item in bank["lumora"] if item["id"] not in cited]

with browser_page() as page:
    open_in_editor(page)
    bullet = lambda n: page.get_by_label(f"Bullet {n}", exact=True).first  # noqa: E731 (Lumora is the first entry)
    titles = lambda: page.locator("section h3").all_inner_texts()  # noqa: E731

    # Drag Lumora's third bullet onto the first.
    third = bullet(3).input_value()
    page.get_by_label("Drag bullet 3").first.drag_to(bullet(1))
    expect(bullet(1)).to_have_value(third)
    print("drag bullet: ok")

    # Drag the Skills section (last) onto the Awards section just above it.
    before = titles()
    awards = page.locator("section").filter(has=page.locator("h3", has_text="Awards"))
    page.get_by_label("Drag Skills section").drag_to(awards, target_position={"x": 60, "y": 8})
    i = before.index("Awards")
    assert titles() == before[:i] + ["Skills", "Awards"] + before[i + 2:], titles()
    print("drag section: ok")
    page.get_by_role("button", name="Move Skills down").click()

    # Swap bullet 1 for a profile fact that isn't on the CV yet: the profile's own words.
    page.get_by_role("button", name="Swap").first.click()
    page.get_by_role("button", name=unused[0]["text"]).click()
    expect(bullet(1)).to_have_value(unused[0]["text"])
    expect(page.get_by_text(f"source: {unused[0]['id']}")).to_be_visible()
    print("swap from profile: ok")

    # Add an unverified Kestrel bullet: it's flagged in the editor and the gap report.
    golden = page.locator("[data-drag-item]").filter(has_text="Kestrel Software").last  # the entry, not its section
    golden.get_by_role("button", name="Add from profile").click()
    page.get_by_role("button", name="kestrel_rampup").click()
    expect(page.get_by_text("unverified: kestrel_rampup").first).to_be_visible()
    expect(page.get_by_text("Unverified facts used")).to_be_visible()
    print("add from profile + unverified flag: ok")

    # Rewrite bullet 1 with Claude and use the first suggestion.
    old = bullet(1).input_value()
    page.get_by_role("button", name="Rewrite").first.click()
    page.get_by_label("Rewrite hint").fill("make it about the backend side")
    page.get_by_role("button", name="Suggest rewrites").click()
    use = page.get_by_role("button", name="Use", exact=True)
    expect(use.first).to_be_visible(timeout=120_000)
    print(f"rewrite: {use.count()} options")
    use.first.click()
    expect(bullet(1)).not_to_have_value(old)
    print("rewrite:", bullet(1).input_value())

    # Answer a gap question; check the diff; save into the (temp) profile.
    page.get_by_role("listitem").filter(has_text=QUESTION).get_by_role("button", name="Answer").click()
    page.get_by_label(f"Answer: {QUESTION}").fill("Yes, at Lumora we ran the Python microservices in Docker containers.")
    page.get_by_role("button", name="Preview profile changes").click()
    expect(page.get_by_label("Profile diff")).to_be_visible(timeout=120_000)
    print(page.get_by_label("Profile diff").inner_text())
    page.get_by_label("Profile diff").scroll_into_view_if_needed()
    page.screenshot(path=OUT / "p1-answer-diff.png", full_page=True)
    page.get_by_role("button", name="Save to profile.yaml").click()
    expect(page.get_by_text("Saved to profile.yaml")).to_be_visible(timeout=15_000)
    saved = PROFILE.read_text(encoding="utf-8")
    assert "Docker" in yaml.safe_dump(yaml.safe_load(saved)["experience"][0]), "Docker not saved under Lumora"
    print("answer saved to profile copy: ok")

    page.get_by_label("Bullet 1", exact=True).first.scroll_into_view_if_needed()
    page.get_by_role("button", name="Rewrite").first.click()
    page.screenshot(path=OUT / "p2-editor.png", full_page=True)
