"""Cover letter → A4 PDF, with the CV's header so the two match."""
from datetime import date
from io import BytesIO

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from backend.models.extras import LetterPdfRequest
from backend.render.html import _env, header_context


def letter_paragraphs(text: str) -> list[list[str]]:
    """Blank lines split paragraphs; single line breaks (e.g. "Kind regards,\nJordan") stay."""
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n")]
    return [[line.strip() for line in b.split("\n")] for b in blocks if b]


def render_letter_html(req: LetterPdfRequest, person: dict, today: date | None = None) -> str:
    return _env.get_template("cover_letter.html.j2").render(
        **header_context(person, req.hide_contact, req.header_extras),
        date=f"{(today or date.today()):%d %B %Y}".lstrip("0"),
        subject=req.subject,
        paragraphs=letter_paragraphs(req.text),
    )


def render_letter_pdf(req: LetterPdfRequest, person: dict) -> tuple[bytes, int]:
    """Return the PDF and its page count. Sync Playwright: call from a threadpool (plain `def` endpoint)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(render_letter_html(req, person), wait_until="load")
            pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()
    return pdf, len(PdfReader(BytesIO(pdf)).pages)
