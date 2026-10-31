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
| [EXP-001](EXP-001-reward-v1-tracking-bonus-stability-smoothness.md) | 2026-10-30 | reward v1: tracking bonus, stability, smoothness | reward: Luwu's → Brian's v1 (tracking bonus, stability + smoothness penalties) | _planned_ |
