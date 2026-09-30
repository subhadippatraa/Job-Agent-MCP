"""Experience matching with graceful gap handling."""

from __future__ import annotations


def compute_experience_score(
    candidate_years: float | None,
    job_min_years: int | None,
    job_max_years: int | None,
) -> tuple[float, str]:
    """Compute experience match score (0-100) with explanation.

    Key rules:
    - 1.8yr candidate vs 2yr requirement = minor penalty (score ~85)
    - 1.8yr candidate vs 5+yr requirement = significant penalty (score ~30)
    - No experience requirement = full score
    - Candidate exceeds requirement = full score (not penalized for overqualification here)
    """
    if job_min_years is None and job_max_years is None:
        return 100.0, "No experience requirement stated"

    if candidate_years is None:
        return 70.0, "Candidate experience not specified; job requires experience"

    # If only max is set, treat it as a range 0-max
    min_req = job_min_years or 0
    max_req = job_max_years

    # Case 1: Candidate meets or exceeds minimum
    if candidate_years >= min_req:
        # Check if overqualified (exceeds max by a lot)
        if max_req and candidate_years > max_req + 2:
            return (
                75.0,
                f"Candidate ({candidate_years}yr) may be overqualified (job asks {min_req}-{max_req}yr)",
            )
        return 100.0, f"Candidate ({candidate_years}yr) meets requirement ({min_req}yr+)"

    # Case 2: Small gap (within ~1 year)
    gap = min_req - candidate_years
    if gap <= 0.5:
        score = 95.0
        detail = f"Negligible gap: candidate {candidate_years}yr vs {min_req}yr required ({gap:.1f}yr short)"
    elif gap <= 1.0:
        score = 85.0
        detail = (
            f"Minor gap: candidate {candidate_years}yr vs {min_req}yr required ({gap:.1f}yr short)"
        )
    elif gap <= 2.0:
        score = 65.0
        detail = f"Moderate gap: candidate {candidate_years}yr vs {min_req}yr required ({gap:.1f}yr short)"
    elif gap <= 3.0:
        score = 40.0
        detail = f"Significant gap: candidate {candidate_years}yr vs {min_req}yr required ({gap:.1f}yr short)"
    else:
        # More than 3 years short — low match
        score = max(10.0, 30.0 - (gap - 3) * 10)
        detail = (
            f"Large gap: candidate {candidate_years}yr vs {min_req}yr required ({gap:.1f}yr short)"
        )

    return score, detail
