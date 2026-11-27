# Preseason overall-rating regression (2021–2024 → 2025)

This note documents constrained linear models that predict **2025 end-of-season overall margin** from **final-week `overall_margin`** in 2021–2024 for the same FBS teams. Results were produced for preseason / prior-weight calibration exploration.

**Data:** `data/previous_years.json`, week **16** (final week) per season, field `overall_margin`.

**Sample:** **n = 130** teams present in all of 2021, 2022, 2023, 2024, and 2025.

**Estimation:** `scipy.optimize.nnls` (model A) and `scipy.optimize.lsq_linear` with bound constraints (model B). Rating coefficients are constrained **≥ 0**; intercepts are free.

---

## Model A — zero intercept, positive weights only

\[
\text{overall\_margin}_{2025,i}
  = \beta_1 r_{2021,i} + \beta_2 r_{2022,i} + \beta_3 r_{2023,i} + \beta_4 r_{2024,i}
\]

| Constraint | |
|------------|---|
| Intercept | Fixed at **0** |
| \(\beta_j\) | All **≥ 0** |

### Coefficients

| Season | \(\beta_j\) |
|--------|------------:|
| 2021 | 0.0929 |
| 2022 | 0.1774 |
| 2023 | 0.0890 |
| 2024 | 0.5432 |
| **Sum** | **0.9025** |

### Fit

| RMSE | MAE | \(R^2\) |
|-----:|----:|--------:|
| 8.34 | 6.81 | 0.641 |

Unconstrained no-intercept OLS yields the same \(\beta\)s (none would be negative).

---

## Model B — group intercepts + positive weights

Same four lagged ratings, plus a **group-specific intercept** \(\alpha_g\):

\[
\text{overall\_margin}_{2025,i}
  = \beta_1 r_{2021,i} + \cdots + \beta_4 r_{2024,i} + \alpha_{g(i)}
\]

| Constraint | |
|------------|---|
| \(\beta_j\) | All **≥ 0** |
| \(\alpha_g\) | Unconstrained (one per group) |

### Conference groups

| Group | Label | Membership rule | Teams |
|------:|-------|-----------------|------:|
| 1 | Power core | **SEC**, **Big Ten**, **Notre Dame** (`team_id` 87) | 35 |
| 2 | ACC / Big 12 | **ACC**, **Big 12** | 33 |
| 3 | Mid-major / legacy Pac | **Pac-12**, **Mountain West**, **American**, **Sun Belt** | 41 |
| 4 | Rest | **MAC**, **CUSA**, other **FBS Indep.** (not Notre Dame) | 21 |

**2025 conference counts within each group**

- Group 1: Big Ten 18, SEC 16, FBS Indep. 1 (Notre Dame)
- Group 2: ACC 17, Big 12 16
- Group 3: American 14, Sun Belt 13, Mountain West 12, Pac-12 2
- Group 4: MAC 13, CUSA 7, FBS Indep. 1

Grouping uses each team’s conference label at **2025** final week (falls back to 2024 if missing).

### Coefficients

**Shared rating weights**

| Season | \(\beta_j\) |
|--------|------------:|
| 2021 | 0.0278 |
| 2022 | 0.1325 |
| 2023 | 0.0386 |
| 2024 | 0.4435 |
| **Sum** | **0.642** |

**Group intercepts \(\alpha_g\)**

| Group | \(\alpha_g\) |
|------:|-------------:|
| 1 | +2.65 |
| 2 | +2.19 |
| 3 | −3.27 |
| 4 | −8.30 |

### Fit

| RMSE | MAE | \(R^2\) |
|-----:|----:|--------:|
| 7.87 | 6.48 | 0.680 |

Compared with Model A, group intercepts improve \(R^2\) by ~0.04 and lower RMSE/MAE; the shared lag weights shrink (sum 0.90 → 0.64) while **2024 remains the dominant \(\beta\)**.

---

## Interpretation (brief)

- **2024 end-of-season overall margin** is the strongest predictor in both specifications.
- Model B attributes a persistent **level shift** by conference tier: positive intercepts for Groups 1–2, negative for Groups 3–4, while keeping a single positive-weight blend of past seasons across all teams.
- This is a descriptive fit on one holdout year (2025), not a deployed preseason formula.

---

## Reproduce

From the repository root (requires `numpy`, `scipy`):

```bash
python3 scripts/preseason_regression.py
```

Last run metrics embedded in that script match the tables above (exported_at on `previous_years.json` at time of authoring: **2026-11-27**).

---

## 2027 projection (Model B applied forward)

Use the **Model B** coefficients and group intercepts above. For a target season **T**, use final-week `overall_margin` from seasons **T−4 … T−1**, each multiplied by the matching slot weight \((\beta_{2021}, \beta_{2022}, \beta_{2023}, \beta_{2024})\) from the fit, then add \(\alpha_g\).

For **2027** that is ratings from **2023, 2024, 2025, and 2026** (within the **2022–2026** history window, the four seasons immediately before 2027). **2026** is taken from **in-season week 13** `overall_margin` in `data/rankings.json` (not a completed season).

\[
\hat{r}_{2027}
  = 0.0278\,r_{2023} + 0.1325\,r_{2024} + 0.0386\,r_{2025} + 0.4435\,r_{2026} + \alpha_g
\]

**Teams projected:** 133 with all four input seasons present.

**Outputs**

- Full list: `data/preseason_2027_predicted_rankings.csv`
- Regenerate: `python3 scripts/preseason_regression.py --predict-2027-only`

### Top 25 (projected overall margin, 2027)

| Rank | Team | Conf. | Proj. margin |
|-----:|------|-------|-------------:|
| 1 | Georgia Bulldogs | SEC | 20.74 |
| 2 | Notre Dame Fighting Irish | FBS Indep. | 18.89 |
| 3 | Texas Longhorns | SEC | 17.86 |
| 4 | Alabama Crimson Tide | SEC | 17.44 |
| 5 | Ohio State Buckeyes | Big Ten | 16.84 |
| 6 | Tennessee Volunteers | SEC | 16.45 |
| 7 | Oregon Ducks | Big Ten | 15.91 |
| 8 | LSU Tigers | SEC | 15.46 |
| 9 | Miami Hurricanes | ACC | 14.84 |
| 10 | Ole Miss Rebels | SEC | 14.65 |
| 11 | Indiana Hoosiers | Big Ten | 13.73 |
| 12 | Utah Utes | Big 12 | 13.23 |
| 13 | BYU Cougars | Big 12 | 12.22 |
| 14 | Iowa Hawkeyes | Big Ten | 11.72 |
| 15 | Louisville Cardinals | ACC | 11.52 |
| 16 | Missouri Tigers | SEC | 11.45 |
| 17 | UCLA Bruins | Big Ten | 11.23 |
| 18 | Oklahoma Sooners | SEC | 10.99 |
| 19 | Texas Tech Red Raiders | Big 12 | 10.94 |
| 20 | South Carolina Gamecocks | SEC | 10.85 |
| 21 | Florida Gators | SEC | 10.46 |
| 22 | USC Trojans | Big Ten | 10.13 |
| 23 | Nebraska Cornhuskers | Big Ten | 9.99 |
| 24 | Penn State Nittany Lions | Big Ten | 9.72 |
| 25 | Wake Forest Demon Deacons | ACC | 8.70 |