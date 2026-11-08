"""Brian's observation design: what the policy can actually see on the real dog.

Written by Claude (2026-11-07) to Brian's design (EXP-010): joint positions come from read_motor(),
which returns a sample-and-hold of each servo, re-polled round-robin (latency_config.py). Brian's
choices: 130 ms cycle, random phase per env, joint velocity dropped from the actor (the dog has no
velocity readback), critic keeps the true, fresh joint state (it never runs on the dog).

Example (one env, joint fr_thigh = slot 4 of 15, cycle 130 ms -> refreshes at phase + 34.7 ms + n * 130 ms;
policy step 20 ms; with phase 0 the refreshes land at 34.7 ms and 164.7 ms):

    step              0      1      2      3      4      5      6      7      8      9
    t [ms]            0     20     40     60     80    100    120    140    160    180
    true [rad]     0.00   0.05   0.11   0.16   0.20   0.22   0.23   0.22   0.19   0.15
    observed       0.00   0.00   0.09   0.09   0.09   0.09   0.09   0.09   0.09   0.18

    At step 2 the 34.7 ms refresh is in (20, 40] ms: 0.05 + (34.7-20)/20 * (0.11-0.05) = 0.094.
    At step 9 the 164.7 ms refresh is in (160, 180]: 0.19 + (4.7/20) * (0.15-0.19) = 0.181.

Output: (num_envs, 12) rad, relative to the default pose (like mjlab's joint_pos_rel), in sim joint order.
"""

from __future__ import annotations

import torch
from mjlab.managers.manager_base import ManagerTermBase

from ironbark_rl.brian import latency_config as config

_STATE_ATTR = "_ironbark_round_robin_readback"  # one shared readback per env object (pos and vel terms agree)


class RoundRobinReadback:
    """What read_motor() would return right now, for every env and joint."""

    def __init__(self, env) -> None:
        self.env = env  # the ManagerBasedRlEnv: clock (episode_length_buf, step_dt) and the robot
        self.asset = env.scene["robot"]  # the S2 entity: joint_pos, default_joint_pos, joint_names
        n_envs, device = env.num_envs, env.device  # sizes and device for every buffer below
        n_joints = len(self.asset.joint_names)  # 12 leg joints, sim order fl, fr, br, bl x hip, thigh, calf
        self.period = config.JOINT_REFRESH_PERIOD_S  # 0.130 s: one full polling cycle
        slot_s = self.period / config.READBACK_SLOTS  # ~8.7 ms per slot: 15 slots share the cycle
        self.offset = torch.tensor(  # (12,) s: when in the cycle each joint is polled
            [config.readback_slot(name) * slot_s for name in self.asset.joint_names], device=device
        )
        self.phase = torch.zeros(n_envs, device=device)  # (num_envs,) s: cycle start, random per env at reset
        self.held = torch.zeros(n_envs, n_joints, device=device)  # (num_envs, 12) rad: what read_motor returns
        self.held_last_step = torch.zeros_like(self.held)  # (num_envs, 12): held one policy step ago (for velocity)
        self.true_last = torch.zeros_like(self.held)  # (num_envs, 12): true position at the last update
        self.t_last = torch.zeros(n_envs, device=device)  # (num_envs,) s: time of the last update
        self.fresh = torch.ones(n_envs, dtype=torch.bool, device=device)  # (num_envs,): just reset, start from truth

    def reset(self, env_ids) -> None:
        ids = slice(None) if env_ids is None else env_ids  # None means every env
        self.fresh[ids] = True  # next update starts these envs from the true pose (the board has a reading)
        n = self.phase[ids].numel()  # how many envs are resetting
        self.phase[ids] = torch.rand(n, device=self.phase.device) * self.period  # (n,) s: uniform cycle phase

    def update(self) -> None:
        """Advance to the current env time; refresh each joint whose poll fell in the elapsed interval."""
        t = self.env.episode_length_buf.float() * self.env.step_dt  # (num_envs,) s since each env's reset
        true = self.asset.data.joint_pos - self.asset.data.default_joint_pos  # (num_envs, 12) rad, like joint_pos_rel
        moved = (t > self.t_last) & ~self.fresh  # (num_envs,): time advanced since the last call (idempotent per step)
        rel_now = (t[:, None] - self.phase[:, None] - self.offset[None, :]) / self.period  # (num_envs, 12) cycles
        rel_last = (self.t_last[:, None] - self.phase[:, None] - self.offset[None, :]) / self.period  # (num_envs, 12)
        k_now = torch.floor(rel_now)  # (num_envs, 12): index of the latest poll at or before now
        polled = (k_now > torch.floor(rel_last)) & moved[:, None]  # (num_envs, 12): a poll happened in (t_last, t]
        t_poll = self.phase[:, None] + self.offset[None, :] + k_now * self.period  # (num_envs, 12) s: when it happened
        span = (t - self.t_last).clamp_min(1e-9)[:, None]  # (num_envs, 1) s: elapsed interval (never divide by 0)
        alpha = ((t_poll - self.t_last[:, None]) / span).clamp(0.0, 1.0)  # (num_envs, 12): where the poll sits in it
        sampled = self.true_last + alpha * (true - self.true_last)  # (num_envs, 12): linear guess of the pose at the poll
        self.held_last_step = torch.where(moved[:, None], self.held, self.held_last_step)  # (num_envs, 12): keep before overwrite
        self.held = torch.where(polled, sampled, self.held)  # (num_envs, 12): only polled joints change
        start = self.fresh[:, None]  # (num_envs, 1): envs that were just reset
        self.held = torch.where(start, true, self.held)  # (num_envs, 12): a reset dog's reading is its true pose
        self.held_last_step = torch.where(start, true, self.held_last_step)  # (num_envs, 12): no fake velocity at reset
        advanced = moved | self.fresh  # (num_envs,): envs whose clock state moves forward now
        self.true_last = torch.where(advanced[:, None], true, self.true_last)  # (num_envs, 12): for next interpolation
        self.t_last = torch.where(advanced, t, self.t_last)  # (num_envs,) s
        self.fresh = torch.zeros_like(self.fresh)  # (num_envs,): every env is now running


def round_robin_readback(env) -> RoundRobinReadback:
    """The env's shared readback (created on first use), so stale pos and stale vel see the same polls."""
    readback = getattr(env, _STATE_ATTR, None)  # None until the first term asks for it
    if readback is None:
        readback = RoundRobinReadback(env)  # one per env object
        setattr(env, _STATE_ATTR, readback)  # stash it on the env so every term finds the same one
    return readback


class stale_joint_pos(ManagerTermBase):  # noqa: N801 (mjlab term naming: lowercase like joint_pos_rel)
    """Actor joint positions as read_motor() reports them: (num_envs, 12) rad, relative to the default pose."""

    def __init__(self, cfg, env) -> None:
        super().__init__(env)  # ManagerTermBase keeps the env
        self.readback = round_robin_readback(env)  # shared state

    def reset(self, env_ids=None) -> None:
        self.readback.reset(env_ids)  # new random phase, start from truth

    def __call__(self, env, **params) -> torch.Tensor:
        self.readback.update()  # advance the polls to now
        return self.readback.held.clone()  # (num_envs, 12): clone, the manager adds noise in place


class stale_joint_vel(ManagerTermBase):  # noqa: N801
    """Velocity the Pi could compute: change of the stale reading over one policy step. (num_envs, 12) rad/s.

    Not in Brian's EXP-010 actor (he dropped joint velocity). Only for scoring EXP-005, whose actor needs a
    velocity input, under EXP-010's conditions: zero most steps, a spike when a poll lands.
    """

    def __init__(self, cfg, env) -> None:
        super().__init__(env)  # ManagerTermBase keeps the env
        self.readback = round_robin_readback(env)  # same polls as stale_joint_pos

    def reset(self, env_ids=None) -> None:
        self.readback.reset(env_ids)  # harmless if stale_joint_pos already reset them

    def __call__(self, env, **params) -> torch.Tensor:
        self.readback.update()  # idempotent within a step
        return (self.readback.held - self.readback.held_last_step) / env.step_dt  # (num_envs, 12) rad/s



# ---------------------------------------------------------------------------------------------------------
# IMU freezes (scoring only; Brian, 2026-11-07). On the dog the whole IMU block sometimes repeats one value
# for ~1 s, then updates live again (latency_config.IMU_FROZEN_MS / IMU_LIVE_MS). Each env runs its own
# frozen/live alternation, each stretch's length drawn from the measured ones. While frozen, the actor's
# IMU terms (base_ang_vel, projected_gravity) hold the value they had at the last live step.
#
# Example (one env, policy step 20 ms): live for 3 steps, then a 987 ms freeze starts:
#     step               0      1      2      3      4    ...   51     52
#     true gyro z      0.10   0.30   0.50   0.40   0.20  ...   0.00   0.10
#     observed         0.10   0.30   0.50   0.50   0.50  ...   0.50   0.10   (frozen for steps 3-51)
# ---------------------------------------------------------------------------------------------------------

_FREEZE_ATTR = "_ironbark_imu_freeze"  # one shared alternation per env object, so gyro and gravity freeze together


class ImuFreezeSchedule:
    """Per env: is the IMU frozen right now? Advances once per policy step (idempotent within a step)."""

    def __init__(self, env) -> None:
        self.env = env  # clock: episode_length_buf, step_dt
        device = env.device  # every buffer lives where the sim does
        self.frozen_s = torch.tensor(config.IMU_FROZEN_MS, device=device) / 1000.0  # (38,) s: measured freezes
        self.live_s = torch.tensor(config.IMU_LIVE_MS, device=device) / 1000.0  # (40,) s: measured live stretches
        share = self.frozen_s.sum() / (self.frozen_s.sum() + self.live_s.sum())  # () 0.418: time frozen in the logs
        self.frozen_share = float(share)  # used to start each env in a frozen or live stretch in that proportion
        self.frozen = torch.zeros(env.num_envs, dtype=torch.bool, device=device)  # (num_envs,): frozen now?
        self.remaining = torch.zeros(env.num_envs, device=device)  # (num_envs,) s: left in the current stretch
        self.t_last = torch.zeros(env.num_envs, device=device)  # (num_envs,) s: env time at the last advance
        self.fresh = torch.ones(env.num_envs, dtype=torch.bool, device=device)  # (num_envs,): just reset

    def _draw(self, frozen: torch.Tensor) -> torch.Tensor:
        """A stretch length for each entry: a random measured freeze if frozen, else a random live stretch."""
        f = self.frozen_s[torch.randint(len(self.frozen_s), frozen.shape, device=frozen.device)]  # (n,) s
        live = self.live_s[torch.randint(len(self.live_s), frozen.shape, device=frozen.device)]  # (n,) s
        return torch.where(frozen, f, live)  # (n,) s

    def reset(self, env_ids) -> None:
        ids = slice(None) if env_ids is None else env_ids  # None means every env
        self.fresh[ids] = True  # start a new alternation at the next advance

    def advance(self) -> None:
        t = self.env.episode_length_buf.float() * self.env.step_dt  # (num_envs,) s since each env's reset
        start = self.fresh  # (num_envs,): envs starting over
        n = int(start.sum())  # how many
        if n:
            begin_frozen = torch.rand(n, device=t.device) < self.frozen_share  # (n,): frozen in 41.8% of starts
            self.frozen[start] = begin_frozen  # (n,)
            self.remaining[start] = torch.rand(n, device=t.device) * self._draw(begin_frozen)  # (n,) s: part-way in
            self.t_last[start] = t[start]  # (n,) s
            self.fresh[start] = False  # running now
        moved = (t > self.t_last) & ~start  # (num_envs,): time advanced since the last call
        self.remaining -= torch.where(moved, t - self.t_last, torch.zeros_like(t))  # (num_envs,) s
        self.t_last = torch.where(moved, t, self.t_last)  # (num_envs,) s
        while True:  # stretches are >= 25 ms, a step is 20 ms: almost always 0 or 1 switch per step
            over = self.remaining <= 0  # (num_envs,): this stretch ended during the step
            if not bool(over.any()):
                break
            self.frozen = torch.where(over, ~self.frozen, self.frozen)  # (num_envs,): live <-> frozen
            self.remaining = torch.where(over, self.remaining + self._draw(self.frozen), self.remaining)  # (num_envs,)


def imu_freeze_schedule(env) -> ImuFreezeSchedule:
    """The env's shared schedule (created on first use)."""
    schedule = getattr(env, _FREEZE_ATTR, None)  # None until the first IMU term asks
    if schedule is None:
        schedule = ImuFreezeSchedule(env)  # one per env object
        setattr(env, _FREEZE_ATTR, schedule)  # every IMU term finds the same one
    return schedule


class imu_frozen(ManagerTermBase):  # noqa: N801 (mjlab term naming)
    """Wraps an IMU observation (params: inner = its function, inner_params = its params) with the freezes."""

    def __init__(self, cfg, env) -> None:
        super().__init__(env)  # ManagerTermBase keeps the env
        self.schedule = imu_freeze_schedule(env)  # shared with the other IMU term
        self.held = None  # (num_envs, k): last live value, allocated on the first call (k = 3 here)
        self.need_start = torch.ones(env.num_envs, dtype=torch.bool, device=env.device)  # (num_envs,): just reset

    def reset(self, env_ids=None) -> None:
        self.schedule.reset(env_ids)  # harmless if the other IMU term already did
        self.need_start[slice(None) if env_ids is None else env_ids] = True  # take the true value next call

    def __call__(self, env, inner, inner_params) -> torch.Tensor:
        true = inner(env, **inner_params)  # (num_envs, k): what a live IMU would report
        self.schedule.advance()  # idempotent within a step
        if self.held is None:
            self.held = true.clone()  # (num_envs, k)
        take = (~self.schedule.frozen | self.need_start)[:, None]  # (num_envs, 1): live, or just reset
        self.held = torch.where(take, true, self.held)  # (num_envs, k): frozen envs keep their last live value
        self.need_start[:] = False  # every env has a value now
        return self.held.clone()  # (num_envs, k): clone, the manager adds noise in place
