"""Tilt-recovery sweep: start the S2 tilted at increasing angles and see which it recovers from.

One simulated dog per starting angle, all in parallel. Each dog starts from the normal
reset height (0.20 m, so it drops a few cm, the same for every angle) with its body
pitched or rolled by its starting angle. It either holds its stance (--policy zero:
passive servos) or runs the newest trained checkpoint (--policy trained: active
recovery), commanded to stand still. Terminations are off, so every dog runs the full
duration: this tool observes falls, it doesn't decide them.

Tilt is measured with Brian's ironbark_rl.brian.metrics.tilt_deg (implement it first).

  python tools/tilt_test.py --axis pitch --start 0 --stop 90 --step 5
  python tools/tilt_test.py --axis roll --policy trained --recovered-below-deg 10
  python tools/tilt_test.py --axis pitch --start 30 --stop 60 --step 2 --trace 46
"""

import argparse
import sys
from dataclasses import asdict

import numpy as np
import torch

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import mjlab.tasks  # noqa: F401
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.utils.lab_api.math import quat_from_euler_xyz

from ironbark_rl.brian.metrics import tilt_deg
from ironbark_rl.runs import latest_checkpoint

DEVICE = "cuda:0"
TRACE_EVERY_S = 0.1
FINAL_WINDOW_S = 0.5  # "final tilt" = mean tilt over the last half second
UPRIGHT_GRAVITY_B = np.array([0.0, 0.0, -1.0])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--task", default="IronBark-S2-Walk-Flat")
    p.add_argument("--axis", choices=("pitch", "roll"), default="pitch")
    p.add_argument("--start", type=float, default=0.0, help="first starting tilt, deg")
    p.add_argument("--stop", type=float, default=90.0, help="last starting tilt, deg (inclusive)")
    p.add_argument("--step", type=float, default=5.0, help="tilt increment, deg")
    p.add_argument("--policy", choices=("zero", "trained"), default="zero")
    p.add_argument("--seconds", type=float, default=3.0, help="sim time per dog")
    p.add_argument("--recovered-below-deg", type=float, default=None,
                   help="your definition of 'recovered': final tilt below this (adds a yes/no column)")
    p.add_argument("--trace", type=float, default=None, help="print this starting angle's tilt every 0.1 s")
    return p.parse_args()


def _check_tilt_deg_implemented() -> None:
    try:
        tilt_deg(UPRIGHT_GRAVITY_B)
    except NotImplementedError:
        sys.exit("Implement tilt_deg() in ironbark_rl/brian/metrics.py first: this tool measures tilt with it.\n"
                 "Check it with: python -m pytest tests/brian -q -k tilt")


def _make_policy(args, env, base):
    if args.policy == "zero":
        return lambda obs: torch.zeros(base.action_space.shape, device=base.device), "zero actions (servos hold the default stance)"
    checkpoint = latest_checkpoint(args.task)
    if checkpoint is None:
        sys.exit(f"no trained checkpoint for {args.task} yet")
    runner = (load_runner_cls(args.task) or MjlabOnPolicyRunner)(env, asdict(load_rl_cfg(args.task)), device=DEVICE)
    runner.load(str(checkpoint), load_cfg={"actor": True}, strict=True, map_location=DEVICE)
    return runner.get_inference_policy(device=DEVICE), f"trained: {checkpoint}"


def main() -> None:
    args = parse_args()
    _check_tilt_deg_implemented()
    angles = np.arange(args.start, args.stop + 1e-9, args.step)

    env_cfg = load_env_cfg(args.task, play=True)
    env_cfg.scene.num_envs = len(angles)
    env_cfg.terminations = {}
    twist = env_cfg.commands["twist"]
    twist.ranges.lin_vel_x = (0.0, 0.0)
    twist.ranges.lin_vel_y = (0.0, 0.0)
    twist.ranges.ang_vel_z = (0.0, 0.0)

    env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg=env_cfg, device=DEVICE), clip_actions=load_rl_cfg(args.task).clip_actions)
    base = env.unwrapped
    robot = base.scene["robot"]
    policy, policy_name = _make_policy(args, env, base)
    env.reset()

    # Place every dog: keep its reset position, set the starting tilt, zero all motion.
    tilt = torch.deg2rad(torch.tensor(angles, dtype=torch.float32, device=base.device))
    zeros = torch.zeros_like(tilt)
    roll, pitch = (tilt, zeros) if args.axis == "roll" else (zeros, tilt)
    quat_wxyz = quat_from_euler_xyz(roll, pitch, zeros)
    robot.write_root_link_pose_to_sim(torch.cat([robot.data.root_link_pos_w.clone(), quat_wxyz], dim=-1))
    robot.write_root_link_velocity_to_sim(torch.zeros(len(angles), 6, device=base.device))
    default_q = robot.data.default_joint_pos.clone()
    robot.write_joint_state_to_sim(default_q, torch.zeros_like(default_q))
    obs = env.get_observations()

    steps = round(args.seconds / base.step_dt)
    tilts = np.empty((steps, len(angles)))
    with torch.inference_mode():
        for t in range(steps):
            obs, _, _, _ = env.step(policy(obs))
            tilts[t] = tilt_deg(robot.data.projected_gravity_b.cpu().numpy())
    env.close()

    final_steps = max(1, round(FINAL_WINDOW_S / base.step_dt))
    print(f"\n{args.axis} sweep · {policy_name} · {args.seconds:.1f} s per dog · standing-still command")
    header = f"{'start[deg]':>10}  {'max[deg]':>8}  {'final[deg]':>10}"
    if args.recovered_below_deg is not None:
        header += f"  recovered(final<{args.recovered_below_deg:g})"
    print(header)
    for i, start in enumerate(angles):
        final = tilts[-final_steps:, i].mean()
        line = f"{start:10.1f}  {tilts[:, i].max():8.1f}  {final:10.1f}"
        if args.recovered_below_deg is not None:
            line += f"  {'yes' if final < args.recovered_below_deg else 'NO'}"
        print(line)

    if args.trace is not None:
        i = int(np.abs(angles - args.trace).argmin())
        every = max(1, round(TRACE_EVERY_S / base.step_dt))
        print(f"\ntrace: start {angles[i]:.1f} deg")
        for t in range(0, steps, every):
            print(f"  t={(t + 1) * base.step_dt:4.1f}s  tilt={tilts[t, i]:6.1f} deg")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
