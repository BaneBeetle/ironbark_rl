# Quiz: reward terms (2026-11-06)

Milestone: Brian's eleven legged_gym-style reward terms implemented (ten by Claude on his request, `feet_air_time` by Brian), weights approved. Answers are Brian's, verbatim.

**Q1. Why do the tracking terms use exp(−error²/width) instead of a plain penalty like −error²?**

> The tracking terms use exp(−error²/width) because it's bounded and positive. A plain −error² would be insanely large in magnitude early in training (huge negative numbers), which destabilizes learning. It's also always ≤ 0, so every step alive loses points and the best strategy becomes falling instantly. exp pays 0 to 1 every step, so staying up and tracking is worth something.

**Q2. Why square the penalties rather than use absolute values? What does squaring do to small vs large errors?**

> Squaring shrinks small errors and magnifies large ones. Training is noisy with lots of small, medium and large errors: small ones approach zero, medium ones grow a bit, and the large critical ones get magnified the most, so the policy focuses on the mistakes that matter. Squaring is also smooth at 0, unlike abs, which has a sharp corner.

**Q3. Why does `torques` read the requested torque instead of `actuator_force`?**

> torques reads the requested torque because actuator_force is capped at 0.43 N·m. If the policy asks for more than the servo can give, actuator_force just reads the max, so the penalty can't tell 0.5 from 5.0 and the policy gets no signal to stop over-asking. That would keep servos saturated, which overheats and stalls them on the real dog.

## Follow-ups to think about (Claude)

- Q1: our commands top out at 0.6 m/s, and a fallen dog moves at most a few tenths of a m/s. How big can error² actually get here, then? Which of your two reasons carries the argument for this robot?
- Q1, the flip side: far from the target, exp(−error²/width) is almost flat. What does that do to the learning signal for a dog that's badly off its command, and how does `width` trade that off?
- Q2: squaring makes the gradient shrink to 0 near the target. When would you want abs (constant push even for tiny errors) instead?
