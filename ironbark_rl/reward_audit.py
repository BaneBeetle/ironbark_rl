"""Per-step reward contributions: the "fall on purpose" guard (Brian, 2026-11-06).

If a typical step's total reward is negative, ending the episode early raises the return,
so PPO learns to fall to escape the penalties. Two views of the same numbers:
- training: per_step_reward_metrics() adds one mjlab metric per reward term plus the total,
  which TensorBoard shows as `Episode_Metrics/reward/<term>`: each episode's mean per-step
  contribution, averaged over the episodes that ended in that iteration.
- offline: tools/reward_check.py runs fixed scenarios (standing still with a zero command,
  a trained policy on metrics.COMMAND_GRID) and reports the same means, flagging a
  negative total.

A contribution is what a term adds to the reward PPO sees in one step, weight x value x dt
(mjlab scales by the 0.02 s step), so the contributions of all terms sum to the total.
Claude's plumbing: it only reads the reward manager and never changes a weight.
"""

from collections.abc import Callable, Iterable

import numpy as np
import torch
from mjlab.managers.metrics_manager import MetricsTermCfg

from ironbark_rl import evaluation

METRIC_PREFIX = "reward/"
TOTAL = "total"


def _scale(base) -> float:
    """mjlab's per-step reward scale: dt unless the reward manager was built with scale_by_dt=False."""
    return base.step_dt if getattr(base.reward_manager, "_scale_by_dt", True) else 1.0


def step_contributions(base) -> dict[str, torch.Tensor]:
    """This step's contribution of every reward term, plus TOTAL. Each (num_envs,).

    Read right after env.step(): `_step_reward` holds weight x value per term (num_envs, n_terms)
    and `reward_buf` (num_envs,) their dt-scaled sum.
    """
    rm = base.reward_manager
    scale = _scale(base)
    out = {name: rm._step_reward[:, i] * scale for i, name in enumerate(rm.active_terms)}  # each (num_envs,)
    out[TOTAL] = base.reward_buf.clone()  # (num_envs,)
    return out


def _term_metric(env, term: str) -> torch.Tensor:
    rm = env.reward_manager
    return rm._step_reward[:, rm.active_terms.index(term)] * _scale(env)  # (num_envs,)


def _total_metric(env) -> torch.Tensor:
    return env.reward_buf  # (num_envs,)


def per_step_reward_metrics(reward_terms: Iterable[str]) -> dict[str, MetricsTermCfg]:
    """mjlab metrics terms (env_cfg.metrics) that log each reward term's per-step contribution and the total."""
    metrics = {METRIC_PREFIX + term: MetricsTermCfg(func=_term_metric, params={"term": term}) for term in reward_terms}
    metrics[METRIC_PREFIX + TOTAL] = MetricsTermCfg(func=_total_metric)
    return metrics


def mean_contributions(env, commands: np.ndarray, policy: Callable, seconds: float) -> tuple[dict[str, float], np.ndarray]:
    """Run every dog on its pinned command and average the per-step contributions.

    Args:
      env: an evaluation.make_pinned_command_env env with len(commands) dogs.
      commands: (N, 3) one (vx, vy, wz) per dog.
      policy: obs -> actions (N, J).
    Returns:
      ({term: mean per-step contribution over all dogs and steps}, (N,) each dog's mean per-step total).
    """
    base = env.unwrapped
    steps = round(seconds / base.step_dt)
    env.reset()
    evaluation.pin_commands(env, commands)
    obs = env.get_observations()
    sums: dict[str, torch.Tensor] = {}
    with torch.no_grad():
        for _ in range(steps):
            obs, *_ = env.step(policy(obs))
            for name, value in step_contributions(base).items():  # value (N,)
                sums[name] = sums.get(name, 0.0) + value
    per_dog = {name: (total / steps).cpu().numpy() for name, total in sums.items()}  # each (N,)
    return {name: float(v.mean()) for name, v in per_dog.items()}, per_dog[TOTAL]


def summary_lines(means: dict[str, float]) -> list[str]:
    """Terms sorted by |contribution|, each with its share of the summed |contributions|, then the total."""
    terms = {k: v for k, v in means.items() if k != TOTAL}
    magnitude = sum(abs(v) for v in terms.values()) or 1.0
    lines = [f"  {name:22s} {value:+.5f}  {100 * abs(value) / magnitude:5.1f}%"
             for name, value in sorted(terms.items(), key=lambda kv: -abs(kv[1]))]
    lines.append(f"  {'TOTAL':22s} {means[TOTAL]:+.5f}" + ("   <-- NEGATIVE: falling early would raise the return" if is_negative(means[TOTAL]) else ""))
    return lines


def is_negative(mean_total: float) -> bool:
    return mean_total < 0.0
