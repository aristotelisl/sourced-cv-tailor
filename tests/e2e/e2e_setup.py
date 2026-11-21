"""First-run profile setup in the browser. The CV reading step is mocked (no LLM calls); saving is real.

Leaves the servers' profile as it found it (the sample), so the other scripts still work.
"""
import json
import os
from pathlib import Path

import httpx
from playwright.sync_api import Route, expect

from common import API, APP, OUT, ROOT, browser_page

SAMPLE = (ROOT / "examples" / "profile.example.yaml").read_text(encoding="utf-8")
PROFILE = Path(os.environ.get("CV_TAILOR_PROFILE") or ROOT / "data" / "profile.yaml")  # as the servers see it
IMPORTED = SAMPLE.replace("name: Jordan Avery", "name: Sam Example")

assert httpx.get(f"{API}/api/profile/status").json()["state"] == "example"


def fake_import(route: Route) -> None:
    sent = json.loads(route.request.post_data or "{}")
    assert sent["filename"] == "cv.txt" and sent["content_base64"], sent
    route.fulfill(json={"yaml": IMPORTED, "warnings": ["Lumora, bullet 2: the number 40 isn't in the CV. Kept, "
                                                       "marked unverified."],
                        "counts": {"jobs": 2, "bullets": 12, "education": 2, "projects": 1, "awards": 1,
                                   "skills": 30}})


def run() -> None:
    with browser_page(1200, 900, sample_chosen=False, expected_errors=2) as page:  # invalid YAML, stale edit
        steps(page)


def steps(page) -> None:
    page.goto(APP)
    expect(page.get_by_text("Set up your profile")).to_be_visible()
    expect(page.get_by_role("button", name="Read my CV")).to_be_disabled()
    print("first run opens on profile setup: ok")

    page.get_by_role("button", name="Explore with the sample profile").click()
    expect(page.get_by_text("You're exploring with the sample profile")).to_be_visible()
    expect(page.get_by_label("Job listing")).to_be_visible()
    page.reload()
    expect(page.get_by_label("Job listing")).to_be_visible()
    print("explore with the sample: tailor page with a banner, remembered on reload: ok")

    page.get_by_role("link", name="Set up your own profile").click()
    expect(page.get_by_text("This is the sample profile")).to_be_visible()
    expect(page.get_by_text("Kestrel Software (internship)")).to_be_visible()
    page.get_by_role("button", name="Set up your own from your CV").click()
    page.route("**/api/profile/import", fake_import)
    page.get_by_label("CV file").set_input_files(
        files=[{"name": "cv.txt", "mimeType": "text/plain", "buffer": b"Sam Example\nSoftware Developer, Lumora"}])
    page.get_by_role("button", name="Read my CV").click()
    expect(page.get_by_text("Check your profile")).to_be_visible()
    expect(page.get_by_text("Found 2 jobs (12 bullets)")).to_be_visible()
    expect(page.get_by_text("the number 40 isn't in the CV")).to_be_visible()
    page.screenshot(path=OUT / "s1-setup-review.png", full_page=True)
    print("upload -> review with warnings: ok")

    yaml_box = page.get_by_label("Profile YAML")
    yaml_box.fill(IMPORTED + "\n  - this: [is not valid")
    page.get_by_role("button", name="Save as my profile").click()
    expect(page.get_by_text("That profile can't be saved")).to_be_visible()
    print("invalid YAML refused: ok")

    yaml_box.fill(IMPORTED)
    page.get_by_role("button", name="Save as my profile").click()
    expect(page.get_by_label("Job listing")).to_be_visible()
    expect(page.get_by_text("You're exploring with the sample profile")).to_have_count(0)
    assert httpx.get(f"{API}/api/profile/status").json() == {"state": "own", "name": "Sam Example"}
    print("save -> profile is your own, back on the tailor page: ok")

    page.get_by_role("link", name="Profile").click()
    expect(page.get_by_text("Sam Example")).to_be_visible()
    expect(page.get_by_text("This is the sample profile")).to_have_count(0)
    expect(page.get_by_text("unverified").first).to_be_visible()  # kestrel_rampup
    page.screenshot(path=OUT / "s2-profile-view.png", full_page=True)
    print("profile page shows your profile: ok")

    page.get_by_role("button", name="Edit as YAML").click()
    box = page.get_by_label("Profile YAML")
    box.fill(box.input_value().replace("Porto, Portugal", "Braga, Portugal", 1))
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("button", name="Edit as YAML")).to_be_visible()  # back on the view
    expect(page.get_by_text("Braga, Portugal").first).to_be_visible()
    assert "Braga, Portugal" in PROFILE.read_text(encoding="utf-8")
    print("edit as YAML -> saved and shown: ok")

    page.get_by_role("button", name="Edit as YAML").click()
    PROFILE.write_text(PROFILE.read_text(encoding="utf-8") + "# changed elsewhere\n", encoding="utf-8")
    box.fill(box.input_value().replace("Braga, Portugal", "Lisbon, Portugal", 1))
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_text("changed since you opened it")).to_be_visible()
    page.get_by_role("button", name="Cancel").click()
    print("an edit over a newer profile is refused: ok")

    page.get_by_role("button", name="Replace from a CV").click()
    expect(page.get_by_text("Replace your profile from a CV")).to_be_visible()
    page.get_by_role("button", name="Keep my current profile").click()
    expect(page.get_by_role("button", name="Edit as YAML")).to_be_visible()
    print("replace from a CV can be cancelled: ok")


try:
    run()
finally:  # put the sample back for the other scripts (the save keeps a backup of "Sam Example": remove it)
    before = set(PROFILE.parent.glob("profile.backup-*.yaml"))
    httpx.post(f"{API}/api/profile/save", json={"yaml": SAMPLE}).raise_for_status()
    for backup in set(PROFILE.parent.glob("profile.backup-*.yaml")) - before:
        backup.unlink()
    assert httpx.get(f"{API}/api/profile/status").json()["state"] == "example"
