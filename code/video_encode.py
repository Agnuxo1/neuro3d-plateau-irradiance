"""Encode the numbered image sequence into the submission MP4 with Blender.

    blender -b --factory-startup -P video_encode.py -- --frames dir
            --out video.mp4 --fps 24 --count N
"""

from __future__ import annotations

import argparse
import os
import sys

import bpy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--res", type=int, default=1280)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = a.res
    scene.render.resolution_y = int(a.res * 9 / 16)
    scene.render.fps = a.fps
    scene.frame_start = 1
    scene.frame_end = a.count
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = a.out

    se = scene.sequence_editor_create()
    names = sorted(f for f in os.listdir(a.frames) if f.endswith(".png"))
    missing = a.count - len(names)
    if missing > 0:
        raise SystemExit(f"{missing} frames missing from the sequence")
    strip = se.strips.new_image("seq", os.path.join(a.frames, names[0]), 1, 1) \
        if hasattr(se, "strips") else \
        se.sequences.new_image("seq", os.path.join(a.frames, names[0]), 1, 1)
    for n in names[1:]:
        strip.elements.append(n)
    strip.frame_final_duration = a.count

    bpy.ops.render.render(animation=True)
    print("wrote", a.out, os.path.getsize(a.out) / 1e6, "MB")


if __name__ == "__main__":
    main()
