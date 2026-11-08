# Roadmap

Brian's plan, 2026-11-08. These are product phases for what the dog can do; they're separate from the Phase 0–2B numbering in `CLAUDE.md`, which tracks the ML work.

The overall shape (Brian's earlier note): the RL policy is the fast "cerebellum", and a VLM is the slow "brain" that sends (vx, vy, yaw_rate).

## Phase 1: walks, follows, talks

**Deploy the RL policy on the real dog.** Needed first (runtime requirements so far are in [deployment-notes.md](deployment-notes.md)):

- Domain randomization
- Gyro units
- Joint-mapping check
- Pi-hang stop test
- Kill switch = power button

**VLM brain with owner tracking:**

- Tracker + VLM verify, with multi-reference photos
- Dead reckoning from commanded turns
- Confidence decay
- Rescan with cooldown
- Voice fallback: "that you, bro?"

**Voice output:** done.

**Personality:** built-in action groups exposed to the VLM as a menu of tools.

## Phase 2: listens + world

**Conversation:** S2 voice module for speech-to-text → Haiku → TTS loop. Latency is the priority.

**LiDAR:** avoidance as a fast safety reflex, plus SLAM starting from Yahboom's ROS2 packages.

**Rough-terrain training** in sim.

## Later

Gamepad.
