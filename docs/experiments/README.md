# Experiments

One file per training run: hypothesis → one change → results on a fixed scoreboard → why → next.
Phase 2A's reward ablations and the write-up come from here.

Start a new one with:

```bash
python tools/new_experiment.py "short title" --parent EXP-000
```

That creates `EXP-NNN-<title>.md` from [TEMPLATE.md](TEMPLATE.md), fills in the setup (git commit, task, seed, iterations), adds a row below, and prints the exact train command (tagged with the experiment ID so its log folder is `<timestamp>_EXP-NNN`).

## Rules

1. **Hypothesis before the run.** Write what you expect and why before training starts. Don't edit it afterwards; put surprises under "Why / next".
2. **One change per experiment**, measured against a named parent. Two changes at once means you can't tell which one mattered.
3. **The scoreboard is `metrics.py`, frozen.** Compare runs only on its metrics, never on reward values (different rewards have different scales). If the scoreboard changes, re-evaluate every run it's compared against.
4. **Seeds.** If a result is close to its parent, run seeds 42, 43, 44 and report mean ± spread. A difference smaller than the seed spread is noise.
5. **The real dog wins.** A run that scores better in sim but transfers worse loses. Real-dog results go in the same file when they exist.
6. **Results are append-only.** Don't overwrite numbers; add a dated line.

## Who writes what

- **Brian:** Hypothesis, What I saw, Why / next, the verdict.
- **Claude:** Setup (auto-filled), running training and evaluation, the Results table.

## Index

| ID | Date | Title | Change vs parent | Verdict |
|---|---|---|---|---|
| [EXP-000](EXP-000-luwu-reward-on-s2-baseline.md) | 2026-10-30 | Luwu reward on S2 (baseline) | baseline: Luwu task + reward, S2 robot | v1, mean of seeds 42/43: 0 falls · planar 0.036 m/s · yaw 0.097 rad/s · smooth 2.2 rad/s · CoT 1.38 (seed noise ~3–9%) |
| [EXP-001](EXP-001-reward-v1-tracking-bonus-stability-smoothness.md) | 2026-10-30 | reward v1: tracking bonus, stability, smoothness | reward: Luwu's → Brian's v1 (tracking bonus, stability + smoothness penalties) | superseded 2026-11-06, never trained (replaced by the legged_gym-style term set) |
| [EXP-002](EXP-002-baseline-on-env-v2-50-deg-tilt-1-4-n-contact-all.md) | 2026-11-06 | baseline on env v2: 50 deg tilt, 1.4 N contact, all collisions | env v2 (Luwu reward unchanged): tilt termination 70° → 50°, non-foot contact 10 N → 1.43 N, all collision meshes touch the ground | v1, seed 42: 0 falls · planar 0.036 m/s · yaw 0.092 rad/s · smooth 2.14 rad/s · CoT 1.36; seeds 43/44 also scored (see file); verdict pending (Brian) |
| [EXP-003](EXP-003-brian-s-legged-gym-style-reward-on-env-v2.md) | 2026-11-07 | Brian's legged_gym-style reward on env v2 | reward: Luwu's → Brian's eleven legged_gym-style terms | v1, seed 42: 0 falls · planar 0.039 m/s · yaw 0.084 rad/s · smooth 2.53 rad/s · CoT 1.47; verdict pending (Brian) |
| [EXP-004](EXP-004-feet-air-time-weight-7-5x.md) | 2026-11-07 | feet_air_time weight 7.5x | `feet_air_time` weight 1.0 → 7.5 | v1, seed 42: falls 0.000 · planar 0.036 m/s · yaw 0.096 rad/s · smooth 3.44 rad/s · CoT 2.39; flicker 15.7% · swing median 0.192 s · saturation 0.97%; finalist vs EXP-005; seeds 42–44 scored, verdict pending (Brian) |
| [EXP-005](EXP-005-sweep-feet-air-time-weight-3.md) | 2026-11-07 | sweep: feet_air_time weight 3 | `feet_air_time` weight 7.5 → 3 (sweep) | v1, seed 42: falls 0.000 · planar 0.034 m/s · yaw 0.095 rad/s · smooth 2.82 rad/s · CoT 1.82; flicker 17.7% · swing median 0.188 s · saturation 0.52%; **provisional winner** (Brian, 2026-11-07); seeds 42–44 scored, verdict pending (Brian) |
| [EXP-006](EXP-006-sweep-feet-air-time-weight-15.md) | 2026-11-07 | sweep: feet_air_time weight 15 | `feet_air_time` weight 7.5 → 15 (sweep) | v1, seed 42: falls 0.000 · planar 0.066 m/s · yaw 0.124 rad/s · smooth 5.66 rad/s · CoT 4.20; flicker 9.9% · swing median 0.220 s · saturation 5.34%; out (Brian: saturation and tracking) |
| [EXP-007](EXP-007-sweep-feet-air-time-weight-30.md) | 2026-11-07 | sweep: feet_air_time weight 30 | `feet_air_time` weight 7.5 → 30 (sweep) | v1, seed 42: falls 0.000 · planar 0.109 m/s · yaw 0.151 rad/s · smooth 7.65 rad/s · CoT 4.57; flicker 7.4% · swing median 0.228 s · saturation 11.72%; out (Brian: saturation and tracking) |
| [EXP-008](EXP-008-sweep-feet-air-time-weight-5.md) | 2026-11-07 | sweep: feet_air_time weight 5 | `feet_air_time` weight 7.5 → 5 (sweep point) | v1, seed 42: falls 0.000 · planar 0.039 m/s · yaw 0.109 rad/s · smooth 3.25 rad/s · CoT 2.00; flicker 18.5% · swing median 0.188 s · saturation 0.87%; verdict pending (Brian) |
