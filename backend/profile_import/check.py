"""Check an extracted profile against the CV it came from: nothing may be added on the way in.

The same rule as everywhere else in the app, at the very start: profile.yaml must only hold what
the user's own CV says. Every name, date, skill and link must be in the CV text, and every bullet
must use the CV's own words (a little tidying is allowed, new numbers and technologies are not).
"""
import re
from dataclasses import dataclass

from backend.models.profile_import import ImportedProfile
from backend.tailor.vocab import mentions, split_skill

Path = tuple[str | int, ...]

# Short function words a tidied bullet may add ("Built X" -> "Built the X").
FILLER = {"the", "and", "for", "with", "from", "into", "using", "via", "its", "their", "our", "that", "which",
          "was", "were", "has", "had", "have", "all", "per", "across", "over", "within", "including"}
SHORT_FIELDS = {"name", "title", "company", "institution", "degree", "location", "grade"}
YEAR = re.compile(r"(?<!\d)(?:19|20)\d\d(?!\d)")


@dataclass
class Problem:
    path: Path
    message: str


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-").lower()
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", _norm(text))


def _bare_url(url: str) -> str:
    url = _norm(url).split("://")[-1].removeprefix("www.").removeprefix("mailto:")
    return url.rstrip("/")


class Source:
    def __init__(self, text: str):
        self.text = text
        self.norm = _norm(text)
        self.words = set(_tokens(text))
        self.digits = re.sub(r"\D", "", text)
        self.bare = self.norm.replace("://www.", "://")

    def new_words(self, value: str) -> list[str]:
        return [w for w in dict.fromkeys(_tokens(value)) if w not in self.words]

    def new_numbers(self, value: str) -> list[str]:
        return [n for n in re.findall(r"\d+(?:[.,]\d+)*", value)
                if not re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d]|[.,]\d)", self.text)]

    def has_term(self, term: str) -> bool:
        return mentions(self.text, term, ignore_case=True) or _norm(term) in self.norm


def check_import(draft: ImportedProfile, source_text: str) -> list[Problem]:
    src = Source(source_text)
    problems: list[Problem] = []

    def short(path: Path, value: str | None) -> None:
        if value and (new := src.new_words(value)):
            problems.append(Problem(path, f"'{value}': {', '.join(new)} isn't in the CV"))

    def long(path: Path, value: str | None) -> None:
        """A bullet: the CV's words, tidied. No new numbers; at most a few new short words."""
        if not value:
            return
        if numbers := src.new_numbers(value):
            problems.append(Problem(path, f"the number {', '.join(numbers)} isn't in the CV"))
            return
        new = [w for w in src.new_words(value) if not w.isdigit() and w not in FILLER and len(w) > 2]
        if len(new) > max(1, len(_tokens(value)) // 12):
            problems.append(Problem(path, f"uses words that aren't in the CV ({', '.join(new[:6])})"))

    def date(path: Path, value: str | None) -> None:
        if value and any(year not in src.text for year in YEAR.findall(value)):
            problems.append(Problem(path, f"the date '{value}' isn't in the CV"))

    def term(path: Path, value: str) -> None:
        missing = [t for t in split_skill(value) if not src.has_term(t)]
        if missing:
            problems.append(Problem(path, f"'{', '.join(missing)}' isn't in the CV"))

    def link(path: Path, value: str | None) -> None:
        if value and _bare_url(value) not in src.bare:
            problems.append(Problem(path, f"the link '{value}' isn't in the CV"))

    p = draft.person
    short(("person", "name"), p.name)
    short(("person", "location"), p.location)
    if p.email and _norm(p.email) not in src.norm:
        problems.append(Problem(("person", "email"), f"the email '{p.email}' isn't in the CV"))
    if p.phone and re.sub(r"\D", "", p.phone).lstrip("0")[-8:] not in src.digits:
        problems.append(Problem(("person", "phone"), f"the phone number '{p.phone}' isn't in the CV"))
    for key in ("website", "linkedin", "github"):
        link(("person", key), getattr(p, key))
    for i, lang in enumerate(p.spoken_languages):
        short(("person", "spoken_languages", i), lang)

    for i, edu in enumerate(draft.education):
        at: Path = ("education", i)
        for key in ("degree", "institution", "location", "grade"):
            short((*at, key), getattr(edu, key))
        date((*at, "start"), edu.start)
        date((*at, "end"), edu.end)
        long((*at, "dissertation"), edu.dissertation)
        for j, module in enumerate(edu.modules):
            short((*at, "modules", j), module)

    for i, exp in enumerate(draft.experience):
        at = ("experience", i)
        for key in ("title", "company", "location"):
            short((*at, key), getattr(exp, key))
        link((*at, "url"), exp.url)
        date((*at, "start"), exp.start)
        date((*at, "end"), exp.end)
        for j, tech in enumerate(exp.stack):
            term((*at, "stack", j), tech)
        for j, bullet in enumerate(exp.bullets):
            long((*at, "bullets", j, "text"), bullet.text)

    for i, project in enumerate(draft.projects):
        at = ("projects", i)
        short((*at, "name"), project.name)
        long((*at, "context"), project.context)
        link((*at, "url"), project.url)
        date((*at, "year"), project.year)
        for j, tech in enumerate(project.stack):
            term((*at, "stack", j), tech)
        for j, fact in enumerate(project.facts):
            long((*at, "facts", j, "text"), fact.text)

    for i, award in enumerate(draft.awards):
        at = ("awards", i)
        short((*at, "name"), award.name)
        short((*at, "institution"), award.institution)
        date((*at, "date"), award.date)
        long((*at, "text"), award.text)

    for i, skill in enumerate(draft.skills):
        term(("skills", i), skill)
    return problems


def describe(path: Path, draft: ImportedProfile) -> str:
    """'experience[0].bullets[2].text' -> 'Software Engineer at Acme, bullet 3', for the user."""
    if path[0] == "person":
        return f"Contact details ({path[1]})"
    if path[0] == "skills":
        return "Skills"
    group, i = path[0], path[1]
    item = getattr(draft, group)[i]
    label = {
        "experience": lambda e: f"{e.title} at {e.company}",
        "education": lambda e: f"{e.degree}, {e.institution}",
        "projects": lambda e: e.name,
        "awards": lambda e: e.name,
    }[group](item)
    if len(path) > 3 and path[2] in ("bullets", "facts"):
        return f"{label}, {'bullet' if path[2] == 'bullets' else 'fact'} {path[3] + 1}"
    return f"{label} ({path[2]})" if len(path) > 2 else label
