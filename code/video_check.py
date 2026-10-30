"""Verify an encoded video by extracting single frames back out of it.

    blender -b --factory-startup -P video_check.py -- --video v.mp4
            --frames 1 600 1100 1500 1900 --out dir
"""

from __future__ import annotations

import argparse
import os
import sys

import bpy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    se = scene.sequence_editor_create()
    new_movie = (se.strips.new_movie if hasattr(se, "strips")
                 else se.sequences.new_movie)
    strip = new_movie("v", a.video, 1, 1)
    scene.render.resolution_x = strip.elements[0].orig_width
    scene.render.resolution_y = strip.elements[0].orig_height
    print("frames in file:", strip.frame_final_duration)
    os.makedirs(a.out, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    for f in a.frames:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(a.out, "check_%05d.png" % f)
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath, flush=True)


if __name__ == "__main__":
    main()
