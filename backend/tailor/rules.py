"""Deterministic tailoring rules (SPEC §5): header suggestions, red flags and guaranteed gaps.

These run in code rather than in the prompt so they hold on every CV.
"""
import re

from backend.models import GapReport, HeaderExtraSuggestion, JobAnalysis, RequirementCoverage
from backend.tailor.vocab import mentions, split_skill

UK_PLACES = ["United Kingdom", "UK", "U.K.", "Britain", "England", "Scotland", "Wales", "Northern Ireland",
             "London", "Manchester", "Edinburgh", "Cambridge", "Oxford", "Bristol", "Bath", "Birmingham",
             "Leeds", "Glasgow", "Belfast", "Reading"]
# EU + EEA + Switzerland (where an EU citizen can work freely).
EU_PLACES = ["EU", "European Union", "EEA", "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech",
             "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
             "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania",
             "Slovakia", "Slovenia", "Spain", "Sweden", "Norway", "Iceland", "Liechtenstein", "Switzerland",
             "Amsterdam", "Berlin", "Munich", "Paris", "Dublin", "Madrid", "Barcelona", "Lisbon", "Athens",
             "Milan", "Stockholm", "Copenhagen", "Vienna", "Warsaw", "Prague", "Zurich"]
# Region names `preferences` can use instead of listing places.
REGIONS = {"uk": UK_PLACES, "eu": EU_PLACES}
CURRENCY_COUNTRY = {"INR": "India", "USD": "the US", "CAD": "Canada", "AUD": "Australia", "SGD": "Singapore",
                    "AED": "the UAE", "JPY": "Japan", "CNY": "China", "BRL": "Brazil", "ZAR": "South Africa",
                    "ILS": "Israel", "TRY": "Turkey", "NZD": "New Zealand", "HKD": "Hong Kong"}


def preferences(profile: dict) -> dict:
    """The profile's optional `preferences:` section (where you live and can work, header rules...)."""
    return profile.get("preferences") or {}


def places(names: list[str]) -> list[str]:
    """Expand region names ("uk", "eu") into places; anything else is a place name itself."""
    return [p for n in names for p in REGIONS.get(n.lower(), [n])]


def _mentions_any(text: str, places: list[str]) -> bool:
    return any(mentions(text, p) for p in places)


def _where(job: JobAnalysis) -> str:
    return f"{job.location or ''}\n{job.right_to_work or ''}"


def header_suggestions(job: JobAnalysis, profile: dict) -> list[HeaderExtraSuggestion]:
    """`preferences.header_suggestions`: suggest a header line when the job is in one of its places."""
    extras = profile["person"].get("header_extras") or {}
    suggestions = []
    for rule in preferences(profile).get("header_suggestions", []):
        key = rule["extra"]
        if extras.get(key) and _mentions_any(_where(job), places(rule.get("when_job_in", []))):
            suggestions.append(HeaderExtraSuggestion(key=key, text=extras[key], reason=rule.get("reason", "")))
    return suggestions


def professional_years(profile: dict) -> float:
    """Non-internship experience, from the profile's MM/YYYY dates (end month inclusive)."""
    months = 0
    for exp in profile.get("experience", []):
        if exp.get("is_internship"):
            continue
        (sm, sy), (em, ey) = (map(int, exp[k].split("/")) for k in ("start", "end"))
        months += (ey - sy) * 12 + (em - sm) + 1
    return months / 12


def red_flags(job: JobAnalysis, profile: dict) -> list[str]:
    """Each check runs only when `preferences` says what to compare against."""
    prefs = preferences(profile)
    home = prefs.get("home_places", [])
    flags = []
    currencies = {c.upper() for c in prefs.get("home_currencies", [])}
    if currencies and job.salary and job.salary.currency.upper() not in currencies:
        cur = job.salary.currency.upper()
        country = CURRENCY_COUNTRY.get(cur)
        flags.append(f"Salary is in {cur}: the posting is probably for another country"
                     + (f" ({country})" if country else "") + ". Check where the role is really based.")

    rights = prefs.get("work_rights", [])
    allowed = home + places([p for r in rights for p in r.get("places", [])])
    if rights and job.right_to_work and not _mentions_any(job.right_to_work, allowed):
        labels = [r["label"] for r in rights]
        have = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
        flags.append(f"Requires the right to work in {job.right_to_work}; you have it in {have}.")

    if home and job.remote in ("on-site", "hybrid") and job.location and not _mentions_any(job.location, home):
        flags.append(f"{job.remote.capitalize()} in {job.location}: you'd need to be based there.")

    match = re.search(r"\d+(?:\.\d+)?", job.years_required or "")
    have = professional_years(profile)
    if match and float(match.group()) > have + 0.25:
        flags.append(f"Asks for {job.years_required} years of experience; you have about {have:g} "
                     "plus an internship.")
    return flags


def enforce_coverage(coverage: list[RequirementCoverage], profile: dict) -> list[RequirementCoverage]:
    """A requirement naming a not_claimed skill can never be 'covered' or 'partial'."""
    terms = [t for item in profile.get("skills", {}).get("not_claimed", []) for t in split_skill(item)]
    result = []
    for item in coverage:
        hit = next((t for t in terms if mentions(item.requirement, t, ignore_case=True)), None)
        if hit and item.status != "missing":
            item = item.model_copy(update={"status": "missing", "note": f"{hit} is not claimed"})
        result.append(item)
    return result


def guaranteed_gaps(gaps: GapReport, job: JobAnalysis, profile: dict) -> GapReport:
    """Make sure every not_claimed skill the job asks for is listed as missing."""
    must, nice = list(gaps.must_have_missing), list(gaps.nice_to_have_missing)
    for item in profile.get("skills", {}).get("not_claimed", []):
        for term in split_skill(item):
            if any(mentions(x, term, ignore_case=True) for x in must + nice):
                continue
            required = [r for r in job.must_have if mentions(r, term, ignore_case=True)]
            optional = [r for r in job.nice_to_have if mentions(r, term, ignore_case=True)]
            if required:
                must.append(required[0])
            elif optional:
                nice.append(optional[0])
            elif any(mentions(s, term, ignore_case=True) for s in job.stack):
                nice.append(term)
    return gaps.model_copy(update={"must_have_missing": must, "nice_to_have_missing": nice})
