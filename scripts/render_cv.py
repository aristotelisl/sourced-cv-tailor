"""Render a tailored CV JSON into HTML and a one-page A4 PDF.

Usage:
    python scripts/render_cv.py examples/example_frontend.tailored.json --out out/

Steps (the logic lives in backend/, this is just a CLI around it):
1. Load data/profile.yaml and validate the tailored JSON against backend.models.TailoredCV.
2. Check sources: every `source` must exist in the profile (else exit 1); warn when a
   source is marked `verified: false`.
3. Render templates/cv.html.j2, print to PDF with Playwright, tightening the layout
   step by step until it fits on one page.
"""
import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import TailoredCV  # noqa: E402
from backend.paths import PROFILE_PATH, ROOT  # noqa: E402
from backend.profile import check_sources, load_profile  # noqa: E402
from backend.render import render_pdf  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tailored_json")
    ap.add_argument("--profile", default=str(PROFILE_PATH))
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()

    profile = load_profile(Path(args.profile))
    try:
        cv = TailoredCV.model_validate_json(Path(args.tailored_json).read_text(encoding="utf-8"))
    except ValidationError as e:
        sys.exit(f"INVALID: {args.tailored_json}\n{e}")

    check = check_sources(cv, profile)
    for part in check.unverified:
        print(f"WARNING: UNVERIFIED '{part}': confirm before sending", file=sys.stderr)
    if not check.ok:
        sys.exit("ERROR: sources not in profile.yaml: " + ", ".join(check.unknown))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    html_path, pdf_path = out / f"{cv.filename}.html", out / f"{cv.filename}.pdf"
    result = render_pdf(cv, profile["person"])
    html_path.write_text(result.html, encoding="utf-8")
    pdf_path.write_bytes(result.pdf)
    if not result.fits:
        sys.exit(f"OVERFLOW: {pdf_path} is {result.pages} pages even at the tightest layout. Cut a bullet.")
    print(f"OK: {pdf_path} (1 page, fit step {result.fit_step})")


if __name__ == "__main__":
    main()
