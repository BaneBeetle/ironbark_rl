# Progress

## 2026-10-30: Phase 0 (move to PC), in progress

**Decision:** Path A, locomotion RL with MuJoCo Playground/MJX + Brax PPO. Brian chose it before the Phase 1 gate ran. Phase 1 now decides *how* the policy deploys on the real dog (joint-level commands vs. a lower-rate action space), not A vs. B.

**PC environment:** Windows 11 + WSL2 Ubuntu-24.04 (Python 3.12, RTX 3090 visible, driver 610.88). Plan: run everything in WSL2 with mirrored networking, because JAX has no GPU builds for native Windows.

### Done
- Environment detected (above). PC LAN IP `192.168.68.55` (DHCP, no reservation yet).
- V1 reference repo cloned read-only to WSL `~/ironbark-v1` (push URL disabled).
- Pi located: `raspberrypi.local` → `192.168.68.56` (fixed MAC). ED25519 host key verified: `SHA256:wqOZO9hVbi+SvpNwRq5HVHM1M877bQ1TpzFUTJUguZ8`.

### Open: Brian
- [ ] URL of the V2 repo (only on the Mac today)
- [ ] WSL mirrored mode + Hyper-V firewall rule for TCP 5556/5558/50505/50507
- [ ] WSL SSH key authorized on the Pi (from the Mac) + `ssh pi` alias
- [ ] Deco DHCP reservations: Pi `.56`, PC `.55`
- [ ] Mac's Claude memory folder copied to the PC
- [ ] Remote access to the PC (Tailscale)

### Open: Claude (after the above)
- [ ] Verify Pi → PC TCP on the four ZMQ ports
- [ ] `.env` `PC_IP`; perception device auto-select (CUDA instead of `mps`)

### Notes
- Old `known_hosts` entries for `192.168.68.56` (on the Mac and the PC) belong to other devices that held that lease earlier, not the Pi. Connect by `raspberrypi.local` and check the fingerprint above.
- The Pi offers password auth as well as keys (the earlier handoff said key-only).

**Interview talking point:** the OS follows from the simulator, not the GPU. MJX runs thousands of environments in parallel on one GPU, which is what makes on-policy PPO for locomotion practical on a single 3090, and JAX's GPU support is Linux-only.
