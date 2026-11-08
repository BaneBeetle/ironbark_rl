"""Scoreboard evaluation: run a checkpoint on metrics.COMMAND_GRID and score it with metrics.py.

Conditions are fixed so runs are comparable across experiments:
- every command in COMMAND_GRID gets EPISODES_PER_COMMAND dogs, all simulated in parallel;
- each dog's command is pinned for the whole episode (no resampling) and it starts from rest;
- play config: no random pushes, no observation noise;
- environment terminations are off: falls are judged by metrics.is_fallen, not the env;
- fixed seed.
Smoothness and cost of transport only use episodes that never fell (a dog lying on the
ground isn't walking); NaN when every episode of a command fell.
"""

import datetime
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import mjlab.tasks  # noqa: F401
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls

from ironbark_rl.brian import metrics

DEVICE = "cuda:0"
EPISODES_PER_COMMAND = 32
EVAL_SECONDS = 10.0
EVAL_SEED = 0
TWIST_COMMAND = "twist"
JOINT_ACTION = "joint_pos"
NEVER_RESAMPLE_S = 1e9


def checkpoint_iteration(checkpoint: Path) -> int | None:
    match = re.fullmatch(r"model_(\d+)", Path(checkpoint).stem)
    return int(match.group(1)) if match else None


def load_policy(task: str, env, checkpoint: Path):
    runner = (load_runner_cls(task) or MjlabOnPolicyRunner)(env, asdict(load_rl_cfg(task)), device=DEVICE)
    runner.load(str(checkpoint), load_cfg={"actor": True}, strict=True, map_location=DEVICE)
    return runner.get_inference_policy(device=DEVICE)


def apply_reward_weights(cfg, reward_weights: dict[str, float] | None) -> None:
    """Override reward terms' weights in place (e.g. a search trial's). An unknown term name raises KeyError."""
    for name, weight in (reward_weights or {}).items():
        cfg.rewards[name].weight = weight


def make_pinned_command_env(task: str, commands: np.ndarray, seed: int, render: bool = False,
                            viewer_size: tuple[int, int] | None = None, camera_distance_m: float | None = None,
                            reward_weights: dict[str, float] | None = None):
    """Play-config env with one dog per row of `commands`, terminations off, resampling off.

    reward_weights overrides those terms' weights (the scoreboard doesn't read rewards; reward_check does).
    """
    cfg = load_env_cfg(task, play=True)
    apply_reward_weights(cfg, reward_weights)
    cfg.scene.num_envs = len(commands)
    cfg.seed = seed
    cfg.terminations = {}
    twist = cfg.commands[TWIST_COMMAND]
    twist.resampling_time_range = (NEVER_RESAMPLE_S, NEVER_RESAMPLE_S)
    twist.rel_standing_envs = 0.0
    twist.init_velocity_prob = 0.0
    if viewer_size is not None:
        cfg.viewer.height, cfg.viewer.width = viewer_size
    if camera_distance_m is not None:
        cfg.viewer.distance = camera_distance_m
    env = RslRlVecEnvWrapper(
        ManagerBasedRlEnv(cfg=cfg, device=DEVICE, render_mode="rgb_array" if render else None),
        clip_actions=load_rl_cfg(task).clip_actions,
    )
    return env, cfg


def pin_commands(env, commands: np.ndarray) -> None:
    """Overwrite every dog's command and start it from rest."""
    base = env.unwrapped
    base.command_manager.get_term(TWIST_COMMAND).vel_command_b[:] = torch.as_tensor(commands, dtype=torch.float32, device=base.device)
    base.scene["robot"].write_root_link_velocity_to_sim(torch.zeros(len(commands), 6, device=base.device))


def rollouts(task: str, checkpoints: list[Path], episodes_per_command: int, seconds: float, seed: int):
    """Yield (checkpoint, per-step arrays) for each checkpoint, reusing one env (building it is the slow part)."""
    grid = np.asarray(metrics.COMMAND_GRID, dtype=float)
    commands = np.repeat(grid, episodes_per_command, axis=0)  # dog i runs grid[i // episodes_per_command]
    env, cfg = make_pinned_command_env(task, commands, seed)
    base, robot = env.unwrapped, env.unwrapped.scene["robot"]
    scale = cfg.actions[JOINT_ACTION].scale
    default_q = robot.data.default_joint_pos
    steps = round(seconds / base.step_dt)
    keys = ("gravity", "command", "velocity", "joint_targets", "joint_torque", "joint_velocity", "base_velocity_xy")
    for checkpoint in checkpoints:
        policy = load_policy(task, env, checkpoint)
        env.reset()
        pin_commands(env, commands)
        rec = {k: [] for k in keys}
        obs = env.get_observations()
        # no_grad, not inference_mode: inference_mode marks env buffers created during the
        # rollout read-only, and the next checkpoint's env.reset() then fails to update them.
        with torch.no_grad():
            for _ in range(steps):
                obs, *_ = env.step(policy(obs))
                lin_b, ang_b = robot.data.root_link_lin_vel_b, robot.data.root_link_ang_vel_b
                for key, value in (
                    ("gravity", robot.data.projected_gravity_b),
                    ("command", base.command_manager.get_command(TWIST_COMMAND)),
                    ("velocity", torch.cat([lin_b[:, :2], ang_b[:, 2:3]], dim=-1)),
                    ("joint_targets", default_q + scale * base.action_manager.action),
                    ("joint_torque", robot.data.actuator_force),
                    ("joint_velocity", robot.data.joint_vel),
                    ("base_velocity_xy", lin_b[:, :2]),
                ):
                    rec[key].append(value.cpu().numpy())
        data = {k: np.stack(v) for k, v in rec.items()}  # each (T, N, ...)
        data.update(grid=grid, dt=base.step_dt, mass_kg=float(base.sim.mj_model.body_mass.sum()))
        yield checkpoint, data
    env.close()


def score(data: dict, episodes_per_command: int) -> dict:
    """Apply metrics.py to a rollout: one row per grid command plus an overall row."""
    rows = []
    for k, command in enumerate(data["grid"]):
        s = slice(k * episodes_per_command, (k + 1) * episodes_per_command)
        fallen = metrics.is_fallen(data["gravity"][:, s])
        valid = metrics.steps_before_fall(fallen)
        planar, yaw = metrics.velocity_tracking_error(data["command"][:, s], data["velocity"][:, s], valid)
        upright = ~fallen.any(axis=0)  # episodes that never fell
        smooth = metrics.joint_target_rate(data["joint_targets"][:, s][:, upright], data["dt"]) if upright.any() else np.array([np.nan])
        cot = (metrics.cost_of_transport(data["joint_torque"][:, s][:, upright], data["joint_velocity"][:, s][:, upright],
                                         data["base_velocity_xy"][:, s][:, upright], data["mass_kg"])
               if upright.any() else np.array([np.nan]))
        rows.append({
            "command": [round(float(c), 3) for c in command],
            "fall_rate": metrics.fall_rate(fallen),
            "planar_error_mps": _nanmean(planar),
            "yaw_rate_error_radps": _nanmean(yaw),
            "joint_target_rate_radps": _nanmean(smooth),
            "cost_of_transport": _nanmean(cot),
        })
    overall = {key: _nanmean(np.array([r[key] for r in rows])) for key in rows[0] if key != "command"}
    return {"per_command": rows, "overall": overall}


def _nanmean(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.nanmean(x)) if np.isfinite(x).any() else float("nan")


def markdown_table(result: dict) -> str:
    header = "| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |\n|---|---|---|---|---|---|\n"
    def fmt(r, label):
        return (f"| {label} | {r['fall_rate']:.3f} | {r['planar_error_mps']:.3f} | {r['yaw_rate_error_radps']:.3f} | "
                f"{r['joint_target_rate_radps']:.2f} | {r['cost_of_transport']:.2f} |\n")
    body = "".join(fmt(r, f"({r['command'][0]:+.1f}, {r['command'][1]:+.1f}, {r['command'][2]:+.1f})") for r in result["per_command"])
    return header + body + fmt(result["overall"], "**overall (mean of rows)**")


def evaluate_many(task: str, checkpoints: list[Path], episodes_per_command: int = EPISODES_PER_COMMAND,
                  seconds: float = EVAL_SECONDS, seed: int = EVAL_SEED) -> list[dict]:
    results = []
    for checkpoint, data in rollouts(task, checkpoints, episodes_per_command, seconds, seed):
        result = score(data, episodes_per_command)
        result.update(
            scoreboard_version=metrics.SCOREBOARD_VERSION, task=task, checkpoint=str(checkpoint),
            iteration=checkpoint_iteration(checkpoint), episodes_per_command=episodes_per_command,
            seconds=seconds, seed=seed, mass_kg=data["mass_kg"], date=datetime.date.today().isoformat(),
        )
        results.append(result)
    return results


def evaluate(task: str, checkpoint: Path, episodes_per_command: int = EPISODES_PER_COMMAND,
             seconds: float = EVAL_SECONDS, seed: int = EVAL_SEED) -> dict:
    """The official scoreboard number for one checkpoint (fresh env, fixed seed)."""
    return evaluate_many(task, [checkpoint], episodes_per_command, seconds, seed)[0]
