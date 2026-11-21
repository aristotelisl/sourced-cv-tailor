"""Tailor a CV: LLM draft → validated → assembled from the profile → rules applied. Also: rewrite one bullet."""
from backend.llm.bullet import rewrite_bullet as rewrite_bullet_draft
from backend.llm.tailor import draft_cv
from backend.models import Bullet, BulletOption, BulletRequest, BulletResult, TailorRequest, TailorResult
from backend.paths import PROFILE_PATH
from backend.profile import check_sources, load_profile, source_index
from backend.tailor.assemble import assemble, header_extra_texts
from backend.tailor.rules import enforce_coverage, guaranteed_gaps, header_suggestions, red_flags


def tailor(req: TailorRequest) -> TailorResult:
    profile_yaml = PROFILE_PATH.read_text(encoding="utf-8")
    profile = load_profile()
    extras = header_extra_texts(profile, req.header_extras)  # ValueError for unknown keys

    draft = draft_cv(req.job, profile, profile_yaml)
    cv = assemble(draft, req.job, profile, extras)

    check = check_sources(cv, profile)
    if not check.ok:  # validate_draft already guarantees this; belt and braces
        raise ValueError(f"Unknown sources after validation: {check.unknown}")

    gaps = guaranteed_gaps(cv.gap_report, req.job, profile)
    flags = red_flags(req.job, profile)
    cv.gap_report = gaps.model_copy(update={
        "unverified_used": check.unverified,
        "flags": flags + [f for f in gaps.flags if f not in flags],
    })
    return TailorResult(cv=cv, coverage=enforce_coverage(draft.coverage, profile),
                        header_extra_suggestions=header_suggestions(req.job, profile))


def rewrite_bullet(req: BulletRequest) -> BulletResult:
    profile_yaml = PROFILE_PATH.read_text(encoding="utf-8")
    profile = load_profile()
    verified = source_index(profile)
    options = rewrite_bullet_draft(req, profile, profile_yaml)
    return BulletResult(options=[
        BulletOption(bullet=Bullet(source=o.source, text=o.text, tech=o.tech),
                     unverified=[p for p in o.source.split("+") if not verified[p]])
        for o in options
    ])
