"""Render the orbit segments of the submission video with Blender.

    blender -b --factory-startup -P video_frames.py -- --neuro3d ... --out dir
            --mode irr --start 1 --frames 600

The district is drawn with one flat emissive colour per face, taken from the
computed value, so the video shows the actual result and not a relighting of it.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

import bpy  # noqa: E402

RAMP = np.array([[0.17, 0.06, 0.23], [0.17, 0.29, 0.56], [0.12, 0.62, 0.64],
                 [0.56, 0.82, 0.31], [1.00, 0.82, 0.40], [1.00, 0.48, 0.29]])


def srgb_to_linear(c):
    """Blender reads FLOAT_COLOR attributes as linear; the ramp is in sRGB."""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def ramp(t):
    t = np.clip(t, 0, 1) * (len(RAMP) - 1)
    i = np.minimum(len(RAMP) - 2, np.floor(t).astype(int))
    f = (t - i)[:, None]
    return RAMP[i] * (1 - f) + RAMP[i + 1] * f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--tile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["irr", "svf"], default="irr")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--elev", type=float, default=26.0)
    ap.add_argument("--radius-factor", type=float, default=0.62)
    ap.add_argument("--az0", type=float, default=0.0)
    ap.add_argument("--az-span", type=float, default=140.0)
    ap.add_argument("--engine", choices=["eevee", "cycles-cpu"], default="eevee",
                    help="cycles-cpu renders without touching the GPU")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

    n3 = np.load(a.neuro3d)
    tile = np.load(a.tile)
    tri = tile["tri"].astype(np.float64)
    per, keep, nrm = n3["per_tri"], n3["keep"], n3["normals"]
    m = keep & (nrm[:, 2] > -0.5)
    tri = tri[m]
    if a.mode == "irr":
        v = per[m, 0] + per[m, 1]
        v = v / max(np.percentile(v, 99.0), 1e-6)
    else:
        v = per[m, 4]
    cols = srgb_to_linear(ramp(v))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    if a.engine == "eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    else:
        # Emission-only materials need a single sample, and keeping Cycles on
        # the CPU leaves the machine's GPU reservation untouched.
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.cycles.max_bounces = 0
    scene.render.resolution_x = a.res
    scene.render.resolution_y = int(a.res * 9 / 16)
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (
        0.043, 0.059, 0.078, 1.0)

    verts = tri.reshape(-1, 3)
    centre = (verts.min(0) + verts.max(0)) / 2.0
    centre[2] = verts[:, 2].min()
    verts = verts - centre
    me = bpy.data.meshes.new("city")
    me.from_pydata([tuple(p) for p in verts],
                   [], [(i, i + 1, i + 2) for i in range(0, len(verts), 3)])
    me.update()
    ob = bpy.data.objects.new("city", me)
    bpy.context.collection.objects.link(ob)

    attr = me.color_attributes.new("value", "FLOAT_COLOR", "CORNER")
    data = np.repeat(cols, 3, axis=0)
    flat = np.concatenate([data, np.ones((len(data), 1))], axis=1).ravel()
    attr.data.foreach_set("color", flat)

    mat = bpy.data.materials.new("flat")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "value"
    nt.links.new(col.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    me.materials.append(mat)

    span = float(max(verts[:, 0].ptp(), verts[:, 1].ptp()))
    target = np.array([0.0, 0.0, 35.0])
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 40
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    os.makedirs(a.out, exist_ok=True)
    r = span * a.radius_factor
    for k in range(a.frames):
        f = k / max(1, a.frames - 1)
        az = np.radians(a.az0 + a.az_span * f)
        el = np.radians(a.elev - 8.0 * np.sin(np.pi * f))
        pos = target + np.array([np.cos(el) * np.sin(az) * r,
                                 -np.cos(el) * np.cos(az) * r,
                                 np.sin(el) * r])
        cam.location = tuple(pos)
        d = target - pos
        import mathutils
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = mathutils.Vector(tuple(-d)).to_track_quat("Z", "Y")
        scene.render.filepath = os.path.join(a.out, "f%05d.png" % (a.start + k))
        bpy.ops.render.render(write_still=True)
        if k % 50 == 0:
            print("frame", a.start + k, flush=True)
    print("done", a.frames, "frames")


if __name__ == "__main__":
    main()
