"""Job listing text file → analysis → tailored CV JSON + one-page PDF.

Usage:
    python scripts/tailor_job.py path/to/job.txt --out out/ [--extra uk_presettled] [--accept-suggestions]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.llm import LLMError, analyse_job  # noqa: E402
from backend.llm.tailor import DraftRejected  # noqa: E402
from backend.models import TailorRequest  # noqa: E402
from backend.paths import ROOT  # noqa: E402
from backend.profile import load_profile  # noqa: E402
from backend.render import render_pdf  # noqa: E402
from backend.tailor.service import tailor  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_text")
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--extra", action="append", default=[], help="header extra key to show (repeatable)")
    ap.add_argument("--accept-suggestions", action="store_true", help="also show suggested header extras")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  %(message)s")
    logging.getLogger("cv_tailor").setLevel(logging.INFO)  # per-call cost lines

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        print("Analysing job...", file=sys.stderr)
        job = analyse_job(Path(args.job_text).read_text(encoding="utf-8"))
        print(f"  {job.title} @ {job.company} ({job.role_family}, {job.location})", file=sys.stderr)
        print("Tailoring CV...", file=sys.stderr)
        result = tailor(TailorRequest(job=job, header_extras=args.extra))
        if args.accept_suggestions:  # header lines don't need another LLM call
            result.cv.header_extras += [s.text for s in result.header_extra_suggestions
                                        if s.text not in result.cv.header_extras]
    except DraftRejected as e:
        sys.exit("REJECTED:\n" + "\n".join(f"  - {p}" for p in e.problems))
    except LLMError as e:
        sys.exit(f"LLM ERROR: {e}")

    cv = result.cv
    (out / f"{cv.filename}.analysis.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
    (out / f"{cv.filename}.tailored.json").write_text(cv.model_dump_json(indent=2, by_alias=True, exclude_none=True),
                                                      encoding="utf-8")
    pdf = render_pdf(cv, load_profile()["person"])
    (out / f"{cv.filename}.pdf").write_bytes(pdf.pdf)
    (out / f"{cv.filename}.html").write_text(pdf.html, encoding="utf-8")

    print(json.dumps({
        "pdf": str(out / f"{cv.filename}.pdf"), "pages": pdf.pages, "fit_step": pdf.fit_step,
        "header_extra_suggestions": [s.model_dump() for s in result.header_extra_suggestions],
        "gap_report": cv.gap_report.model_dump(),
    }, indent=2, ensure_ascii=False))
    if not pdf.fits:
        sys.exit("OVERFLOW: more than one page even at the tightest layout. Cut a bullet.")


if __name__ == "__main__":
    main()
