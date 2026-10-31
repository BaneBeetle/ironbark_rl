"""Film a dog walking at one or more checkpoints; several checkpoints become one labeled progression video.

  python tools/record.py IronBark-S2-Walk-Flat --label EXP-000                    # newest checkpoint
  python tools/record.py IronBark-S2-Walk-Flat --label EXP-000 --checkpoint .../model_0.pt --checkpoint .../model_1499.pt
  python tools/record.py IronBark-S2-Walk-Flat --run-dir .../2026-10-30_18-26-15 --iterations 0 100 300 700 1499

One dog, camera following it, command pinned, starting from rest, terminations off (a
fall stays on camera). Every frame is stamped with label, iteration and command.
Videos go to IRONBARK_RUNS/videos (outside OneDrive).
"""

import argparse
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from ironbark_rl.evaluation import checkpoint_iteration, load_policy, make_pinned_command_env, pin_commands
from ironbark_rl.runs import RUNS_DIR, latest_checkpoint

VIDEO_DIR = RUNS_DIR / "videos"
FRAME_HEIGHT, FRAME_WIDTH = 720, 1280
CAMERA_DISTANCE_M = 0.7  # Luwu's 1.5 m leaves the ~25 cm S2 tiny in a 720p frame
DEFAULT_COMMAND = (0.3, 0.0, 0.0)  # walk forward, between COMMAND_GRID's 0.2 and 0.4
DEFAULT_SECONDS = 8.0
RECORD_SEED = 0
LABEL_FONT_PX = 32
LABEL_MARGIN_PX = 20


def _font() -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, LABEL_FONT_PX)
        except OSError:
            continue
    return ImageFont.load_default()


def _stamp(frame: np.ndarray, text: str, font) -> np.ndarray:
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = draw.textbbox((LABEL_MARGIN_PX, LABEL_MARGIN_PX), text, font=font)
    draw.rectangle((x0 - 8, y0 - 6, x1 + 8, y1 + 6), fill=(0, 0, 0))
    draw.text((LABEL_MARGIN_PX, LABEL_MARGIN_PX), text, fill=(255, 255, 255), font=font)
    return np.asarray(img)


def record(task: str, checkpoints: list[Path], command, seconds: float, label: str, out: Path) -> Path:
    commands = np.array([command], dtype=float)
    env, _ = make_pinned_command_env(task, commands, RECORD_SEED, render=True, viewer_size=(FRAME_HEIGHT, FRAME_WIDTH),
                                     camera_distance_m=CAMERA_DISTANCE_M)
    base = env.unwrapped
    fps = round(1.0 / base.step_dt)
    font = _font()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd_text = f"cmd vx={command[0]:+.2f} vy={command[1]:+.2f} wz={command[2]:+.2f}"
    with imageio.get_writer(out, fps=fps, codec="libx264", quality=7) as writer:
        for checkpoint in checkpoints:
            policy = load_policy(task, env, checkpoint)
            env.reset()
            pin_commands(env, commands)
            obs = env.get_observations()
            text = f"{label}  ·  iteration {checkpoint_iteration(checkpoint)}  ·  {cmd_text}"
            with torch.inference_mode():
                for _ in range(round(seconds / base.step_dt)):
                    obs, *_ = env.step(policy(obs))
                    writer.append_data(_stamp(np.asarray(env.unwrapped.render()), text, font))
            print(f"  filmed {Path(checkpoint).name}")
    env.close()
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--checkpoint", type=Path, action="append", default=None, help="repeatable; default: newest checkpoint")
    p.add_argument("--run-dir", type=Path, default=None, help="with --iterations: pick model_<i>.pt from this run folder")
    p.add_argument("--iterations", type=int, nargs="*", default=None)
    p.add_argument("--command", type=float, nargs=3, default=DEFAULT_COMMAND, metavar=("VX", "VY", "WZ"))
    p.add_argument("--seconds", type=float, default=DEFAULT_SECONDS, help="per checkpoint")
    p.add_argument("--label", default="")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    checkpoints = list(args.checkpoint or [])
    if args.run_dir is not None and args.iterations:
        checkpoints += [args.run_dir / f"model_{i}.pt" for i in args.iterations]
    if not checkpoints:
        latest = latest_checkpoint(args.task)
        if latest is None:
            sys.exit(f"no checkpoint found for {args.task}")
        checkpoints = [latest]
    missing = [str(c) for c in checkpoints if not Path(c).exists()]
    if missing:
        sys.exit(f"missing checkpoints: {missing}")

    its = "-".join(str(checkpoint_iteration(c)) for c in checkpoints)
    out = args.out or VIDEO_DIR / f"{args.label or args.task}_iter{its}_vx{args.command[0]:+.2f}.mp4"
    print(f"recording {len(checkpoints)} checkpoint(s) -> {out}")
    print(f"saved {record(args.task, checkpoints, tuple(args.command), args.seconds, args.label or args.task, out)}")


if __name__ == "__main__":
    main()
