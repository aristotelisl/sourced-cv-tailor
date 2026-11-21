"""HTML → one-page A4 PDF with Playwright, tightening the layout until it fits."""
from dataclasses import dataclass
from io import BytesIO

from playwright.sync_api import Page, sync_playwright
from pypdf import PdfReader

from backend.models import TailoredCV
from backend.render.html import render_html

# Tighter layouts tried in order until the CV fits on one page.
FIT_STEPS = [
    {},
    {"font_pt": 10.3, "line_height": 1.22},
    {"font_pt": 10.2, "line_height": 1.2, "section_gap": "7px"},
    {"font_pt": 10.0, "line_height": 1.18, "section_gap": "6px", "margin_mm": "11mm 14mm 9mm 14mm"},
    {"font_pt": 9.8, "line_height": 1.16, "section_gap": "5px", "margin_mm": "10mm 13mm 8mm 13mm"},
]


@dataclass
class PdfResult:
    pdf: bytes
    html: str
    pages: int
    fit_step: int

    @property
    def fits(self) -> bool:
        return self.pages == 1


def _print(page: Page, html: str) -> bytes:
    page.set_content(html, wait_until="load")
    return page.pdf(prefer_css_page_size=True, print_background=True)


def render_pdf(cv: TailoredCV, person: dict) -> PdfResult:
    """Try each fit step; return the first one-page result, or the tightest attempt if none fit.

    Uses the sync Playwright API, so call it from a thread without a running event loop
    (FastAPI runs plain `def` endpoints in a threadpool).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            for step, layout in enumerate(FIT_STEPS):
                html = render_html(cv, person, layout)
                pdf = _print(page, html)
                result = PdfResult(pdf, html, len(PdfReader(BytesIO(pdf)).pages), step)
                if result.fits:
                    break
            return result
        finally:
            browser.close()
