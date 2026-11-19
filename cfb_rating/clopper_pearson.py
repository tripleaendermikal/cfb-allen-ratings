"""Clopper–Pearson exact binomial confidence intervals."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import beta as beta_dist

RESUME_TARGET_CONFIDENCE = 0.5


@dataclass(frozen=True)
class BinomialCI:
    successes: int
    trials: int
    confidence: float
    lower: float
    upper: float
    point_estimate: float


def clopper_pearson(
    successes: int, trials: int, confidence: float = 0.95
) -> BinomialCI:
    """Exact two-sided Clopper–Pearson interval for binomial proportion p."""
    if trials < 1:
        raise ValueError("trials must be at least 1")
    if not 0 <= successes <= trials:
        raise ValueError("successes must be between 0 and trials inclusive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")

    k, n = successes, trials
    alpha = 1.0 - confidence

    if k == 0:
        lower = 0.0
    else:
        lower = float(beta_dist.ppf(alpha / 2, k, n - k + 1))

    if k == n:
        upper = 1.0
    else:
        upper = float(beta_dist.ppf(1.0 - alpha / 2, k + 1, n - k))

    return BinomialCI(
        successes=k,
        trials=n,
        confidence=confidence,
        lower=lower,
        upper=upper,
        point_estimate=k / n,
    )


def clopper_pearson_midpoint(
    successes: int,
    trials: int,
    *,
    confidence: float = RESUME_TARGET_CONFIDENCE,
) -> float:
    """Midpoint of a Clopper–Pearson interval (used as resume target win rate)."""
    ci = clopper_pearson(successes, trials, confidence)
    return (ci.lower + ci.upper) / 2.0