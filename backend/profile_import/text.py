"""Plain text from an uploaded CV (PDF, DOCX or text), plus the links a PDF hides behind words."""
import io
import re
import zipfile
from xml.etree import ElementTree

from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 60_000  # far more than any CV; stops someone uploading a book
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class UnreadableFile(ValueError):
    """Not a file we can read, or no text in it."""


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise UnreadableFile("The file is over 10 MB")
    name = filename.lower()
    if name.endswith(".pdf") or data.startswith(b"%PDF"):
        text = _pdf(data)
    elif name.endswith(".docx"):
        text = _docx(data)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace")
    else:
        raise UnreadableFile("Upload a PDF, Word (.docx) or text file")
    return clean(text)


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 50:
        raise UnreadableFile("Found almost no text in the file. If it's a scanned image, paste the text instead.")
    return text[:MAX_CHARS]


def _with_links(text: str, links: list[str]) -> str:
    """Links that sit behind words ("LinkedIn", "Portfolio") are only in the file's metadata."""
    hidden = [u for u in dict.fromkeys(links) if u.split("://")[-1].rstrip("/") not in text]
    return text + ("\n\nLinks in the document:\n" + "\n".join(hidden) if hidden else "")


def _pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        links = []
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                action = annot.get_object().get("/A") or {}
                uri = action.get("/URI") if hasattr(action, "get") else None
                if isinstance(uri, str) and uri.startswith(("http", "mailto:")):
                    links.append(uri.removeprefix("mailto:"))
    except Exception as e:  # pypdf raises many kinds of error on damaged files
        raise UnreadableFile("Couldn't read that PDF") from e
    return _with_links("\n\n".join(pages), links)


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            body = ElementTree.fromstring(z.read("word/document.xml"))
            rels = ElementTree.fromstring(z.read("word/_rels/document.xml.rels")) \
                if "word/_rels/document.xml.rels" in z.namelist() else None
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise UnreadableFile("Couldn't read that Word file (only .docx is supported, not .doc)") from e
    paragraphs = []
    for p in body.iter(f"{W}p"):
        parts = []
        for node in p.iter():
            if node.tag == f"{W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{W}tab":
                parts.append("\t")
            elif node.tag in (f"{W}br", f"{W}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    links = []
    if rels is not None:
        links = [r.get("Target", "") for r in rels if r.get("TargetMode") == "External"]
        links = [u.removeprefix("mailto:") for u in links if u.startswith(("http", "mailto:"))]
    return _with_links("\n".join(paragraphs), links)
