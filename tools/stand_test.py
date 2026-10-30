"""Zero-action standing test: can the robot hold its default stance under gravity?

Zero actions command the default joint pose, so this isolates the model (mass,
servo strength, stance) from any policy. Runs the task's play config headless.

  python tools/stand_test.py IronBark-S2-Walk-Flat [num_envs] [seconds]
"""

import sys

import torch

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import mjlab.tasks  # noqa: F401
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg

DEFAULT_NUM_ENVS = 16
DEFAULT_SECONDS = 5.0
REPORT_EVERY_S = 1.0


def main() -> None:
    task = sys.argv[1]
    num_envs = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NUM_ENVS
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_SECONDS

    env_cfg = load_env_cfg(task, play=True)
    env_cfg.scene.num_envs = num_envs
    env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg=env_cfg, device="cuda:0"))
    base = env.unwrapped
    robot = base.scene["robot"]
    actions = torch.zeros(base.action_space.shape, device=base.device)
    steps = round(seconds / base.step_dt)
    report_every = round(REPORT_EVERY_S / base.step_dt)

    falls = 0
    print(f"{task}: {num_envs} envs, {seconds:.1f} s, zero actions")
    print("  t[s]  base_z[m]  max|q-q0|[rad]  max|torque|[N*m]  tilt[deg]")
    with torch.inference_mode():
        for step in range(1, steps + 1):
            _, _, dones, extras = env.step(actions)
            timeouts = extras.get("time_outs", torch.zeros_like(dones)).bool()
            falls += (dones.bool() & ~timeouts).sum().item()
            if step % report_every == 0:
                base_z = robot.data.root_link_pos_w[:, 2].mean().item()
                sag = (robot.data.joint_pos - robot.data.default_joint_pos).abs().max().item()
                torque = robot.data.actuator_force.abs().max().item()
                # Angle between body z and world z, from gravity in the body frame.
                gravity_z = -robot.data.projected_gravity_b[:, 2].clamp(-1.0, 1.0)
                tilt = torch.rad2deg(torch.acos(gravity_z)).max().item()
                print(f"  {step * base.step_dt:4.1f}  {base_z:9.4f}  {sag:14.3f}  {torque:16.3f}  {tilt:9.2f}")
    print(f"  falls/early terminations: {falls}")
    env.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
