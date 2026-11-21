"""Tailored CV → HTML via templates/cv.html.j2."""
from jinja2 import Environment, FileSystemLoader

from backend.models import TailoredCV
from backend.paths import TEMPLATES_DIR

# Default (lenient) Undefined: optional fields like middle_url simply fall back.
_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def header_context(person: dict, hide_contact: list[str], header_extras: list[str]) -> dict:
    """The header shared by the CV and the cover letter: contact details minus hidden ones, plus extra lines."""
    shown = {k: v for k, v in person.items() if k not in hide_contact}
    left_lines = [shown[k] for k in ("location", "phone") if shown.get(k)] + list(header_extras)
    return {"person": shown, "left_lines": left_lines}


def render_html(cv: TailoredCV, person: dict, fit_layout: dict | None = None) -> str:
    """Render the CV. `fit_layout` (a fit step) overrides the CV's own layout."""
    # exclude_none so the template's `| default(...)` filters apply to unset fields.
    data = cv.model_dump(exclude_none=True)
    return _env.get_template("cv.html.j2").render(
        **header_context(person, cv.hide_contact, data["header_extras"]),
        sections=data["sections"],
        layout={**data["layout"], **(fit_layout or {})},
    )
