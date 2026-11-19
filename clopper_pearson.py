#!/usr/bin/env python3
"""CLI for Clopper–Pearson intervals (implementation in cfb_rating.clopper_pearson)."""

from __future__ import annotations

import argparse

from cfb_rating.clopper_pearson import clopper_pearson


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clopper–Pearson exact confidence interval for a binomial proportion."
    )
    parser.add_argument("successes", type=int, help="Number of successes k")
    parser.add_argument("trials", type=int, help="Number of trials n")
    parser.add_argument(
        "-c",
        "--confidence",
        type=float,
        default=0.95,
        help="Two-sided confidence level (default: 0.95)",
    )
    args = parser.parse_args(argv)

    result = clopper_pearson(args.successes, args.trials, args.confidence)
    p = result.point_estimate * 100
    lo, hi = result.lower * 100, result.upper * 100
    print(
        f"k={result.successes}, n={result.trials}, "
        f"{100 * result.confidence:.0f}% Clopper–Pearson CI"
    )
    print(f"  point estimate p̂ = {p:.4f}%")
    print(f"  interval: [{lo:.4f}%, {hi:.4f}%]")
    print(f"  midpoint: {(result.lower + result.upper) / 2 * 100:.4f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())