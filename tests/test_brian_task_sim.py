"""IronBark-S2-Walk-Flat-Brian in simulation. GPU, ~1 min, opt-in: python -m pytest -m sim

Reproduces the 2026-11-07 undesired_contacts finding. In EXP-003 the term's TensorBoard average
looked like 0 while some episodes ended on non-foot contact, which suggested the penalty never
fired. It does fire, on the very step the contact termination fires: mjlab computes the reward
after the terminations and before the reset, so the forces are still there. Because any contact
over the 1.43 N limit ends the episode at once, the term only ever pays on that one terminal step
(-0.25 x 1 part x 0.02 s = -0.005), and its per-step average over an episode is ~1e-6.
"""

import contextlib
import io
import math

import pytest
import torch

pytestmark = pytest.mark.sim

TASK = "IronBark-S2-Walk-Flat-Brian"
DOGS = 4
DROP_HEIGHT_M = 0.2  # the spawn height
MAX_FALL_STEPS = 50  # 1 s: plenty to land on its back from 0.2 m


@pytest.fixture(scope="module")
def env():
    if not torch.cuda.is_available():
        pytest.skip("needs the GPU")
    with contextlib.redirect_stdout(io.StringIO()):
        import ironbark_rl.tasks  # noqa: F401
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.tasks.registry import load_env_cfg

        cfg = load_env_cfg(TASK, play=True)  # play: no random pushes
        cfg.scene.num_envs = DOGS
        cfg.terminations.pop("fell_over")  # an upside-down dog would end on tilt before it lands
        env = ManagerBasedRlEnv(cfg=cfg, device="cuda:0")
        env.reset()
    yield env
    env.close()


def test_contact_termination_step_is_also_penalized(env):
    from ironbark_rl.brian import reward_config as config

    robot = env.scene["robot"]
    upside_down = torch.tensor([0.0, 1.0, 0.0, 0.0], device=env.device)  # (4,) quaternion (w, x, y, z): 180 deg about x
    pose = torch.cat([env.scene.env_origins + torch.tensor([0.0, 0.0, DROP_HEIGHT_M], device=env.device),
                      upside_down.repeat(DOGS, 1)], dim=-1)  # (DOGS, 7)
    robot.write_root_link_pose_to_sim(pose)
    robot.write_root_link_velocity_to_sim(torch.zeros(DOGS, 6, device=env.device))

    term = env.reward_manager.active_terms.index("undesired_contacts")
    weight = config.WEIGHTS["undesired_contacts"]
    penalized_at_landing = torch.full((DOGS,), math.nan)  # (DOGS,) parts counted on each dog's contact-termination step
    zero_action = torch.zeros(env.action_space.shape, device=env.device)  # (DOGS, 12): hold the default pose
    with torch.no_grad(), contextlib.redirect_stdout(io.StringIO()):
        for _ in range(MAX_FALL_STEPS):
            env.step(zero_action)
            ended = env.termination_manager.get_term("illegal_contact").cpu()  # (DOGS,) computed this step, before the reset
            counted = (env.reward_manager._step_reward[:, term] / weight).cpu()  # (DOGS,) parts the reward saw touching
            first = ended & torch.isnan(penalized_at_landing)
            penalized_at_landing[first] = counted[first]
            if not torch.isnan(penalized_at_landing).any():
                break
    assert not torch.isnan(penalized_at_landing).any(), "every dog dropped on its back should end on non-foot contact"
    assert (penalized_at_landing >= 1).all(), f"the contact-termination step must be penalized too: {penalized_at_landing.tolist()}"
