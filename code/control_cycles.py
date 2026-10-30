"""Professional control: per-probe irradiance baked with Blender Cycles.

Run with a Blender 4.5 binary:

    blender -b --factory-startup -P control_cycles.py -- --tile ... --out ...

The same PLATEAU geometry, the same sun positions and the same clear-sky model
as the Neuro3D engine are used. The city is a black Lambertian body, so neither
engine includes inter-reflection and the comparison isolates shadowing and sky
visibility.

For each time step the scene is path-traced and the diffuse direct+indirect
light arriving at each probe is baked into one texel block of a small atlas.
With an albedo-1 Lambertian probe and the colour pass excluded, the baked value
is the outgoing radiance E/pi, so the irradiance is pi times the baked value.
An extra unobstructed horizontal probe is included as a calibration check: its
irradiance must equal DNI*sin(alt) + DHI analytically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solar  # noqa: E402

import bpy  # noqa: E402
import mathutils  # noqa: E402

BLOCK = 8          # texels per probe side
INNER = slice(2, 6)  # texels averaged inside each block


def argv_after_dashes():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_mesh(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def diffuse_material(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
    bsdf.inputs["Color"].default_value = (*color, 1.0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def probe_quads(centres, normals, size):
    """Build one quad per probe, plus the UV atlas layout."""
    nprobe = len(centres)
    side = int(np.ceil(np.sqrt(nprobe)))
    res = side * BLOCK
    verts, faces, uvs = [], [], []
    up = np.array([0.0, 0.0, 1.0])
    for i, (c, n) in enumerate(zip(centres, normals)):
        t = np.cross(up, n)
        if np.linalg.norm(t) < 1e-6:
            t = np.cross(np.array([1.0, 0.0, 0.0]), n)
        t /= np.linalg.norm(t)
        b = np.cross(n, t)
        h = size / 2.0
        quad = [c - t * h - b * h, c + t * h - b * h, c + t * h + b * h, c - t * h + b * h]
        base = len(verts)
        verts.extend(quad)
        faces.append((base, base + 1, base + 2, base + 3))
        gx, gy = i % side, i // side
        u0, v0 = gx * BLOCK / res, gy * BLOCK / res
        u1, v1 = (gx + 1) * BLOCK / res, (gy + 1) * BLOCK / res
        uvs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    return verts, faces, uvs, side, res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--probes", required=True, help="npz with probe centres and normals")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--tz", type=float, default=9.0)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--hour-step", type=float, default=1.0)
    ap.add_argument("--min-alt", type=float, default=1.0)
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--probe-size", type=float, default=1.0)
    ap.add_argument("--device", default="GPU")
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--no-city", action="store_true",
                    help="bake without the city, for atlas validation")
    ap.add_argument("--no-ground", dest="ground", action="store_false",
                    help="omit the ground disc; the sky then lights from below")
    a = ap.parse_args(argv_after_dashes())

    tile = np.load(a.tile)
    pr = np.load(a.probes)
    centres = pr["centres"].astype(np.float64)
    normals = pr["normals"].astype(np.float64)
    # Calibration probe: horizontal, high above the city, nothing can shade it.
    zmax = float(tile["tri"].reshape(-1, 3)[:, 2].max())
    centres = np.vstack([centres, [0.0, 0.0, zmax + 200.0]])
    normals = np.vstack([normals, [0.0, 0.0, 1.0]])

    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = False
    # No interreflection in either engine: only direct sun and direct sky.
    scene.cycles.max_bounces = 0
    scene.cycles.diffuse_bounces = 0
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if a.device.upper() == "GPU":
        for backend in ("CUDA", "OPTIX", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
                break
            except TypeError:
                continue
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"

    tri = tile["tri"].astype(np.float64)
    verts = tri.reshape(-1, 3)
    faces = np.arange(len(verts)).reshape(-1, 3)
    if not a.no_city:
        city = make_mesh("city", verts, faces)
        city.data.materials.append(diffuse_material("black", (0.0, 0.0, 0.0)))

    if a.ground:
        # Without a ground, Blender's uniform world lights a surface from the
        # whole sphere, while the own engine integrates the upper hemisphere
        # only. A vertical probe then receives about 1.3 times too much
        # diffuse light in the control. A large black disc at the base of the
        # tile removes the half of the sky that a real ground blocks, so both
        # engines see the same sky.
        z0 = float(tri.reshape(-1, 3)[:, 2].min()) - 0.5
        r = 20000.0
        n = 64
        ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
        ring = np.stack([r * np.cos(ang), r * np.sin(ang),
                         np.full(n, z0)], axis=1)
        gverts = np.vstack([[0.0, 0.0, z0], ring])
        gfaces = [(0, i + 1, (i + 1) % n + 1) for i in range(n)]
        ground = make_mesh("ground", gverts, gfaces)
        ground.data.materials.append(diffuse_material("black", (0.0, 0.0, 0.0)))

    pv, pf, puv, side, res = probe_quads(centres, normals, a.probe_size)
    probes = make_mesh("probes", pv, pf)
    if len(probes.data.polygons) != len(centres):
        raise RuntimeError(
            f"probe mesh has {len(probes.data.polygons)} faces for "
            f"{len(centres)} probes: the atlas mapping would be wrong")
    probes.data.materials.append(diffuse_material("white", (1.0, 1.0, 1.0)))
    uv = probes.data.uv_layers.new(name="bake")
    for fi, poly in enumerate(probes.data.polygons):
        for k, li in enumerate(poly.loop_indices):
            uv.data[li].uv = puv[fi][k]
    # Probes must not shade each other or the city, but they must still be
    # bakeable, so only shadow casting is switched off.
    probes.visible_shadow = False

    img = bpy.data.images.new("bake", res, res, float_buffer=True)
    mat = probes.data.materials[0]
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex

    world = bpy.data.worlds.new("sky")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    sun_data = bpy.data.lights.new("sun", type="SUN")
    sun_data.angle = np.radians(0.526)
    sun = bpy.data.objects.new("sun", sun_data)
    bpy.context.collection.objects.link(sun)

    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False
    scene.render.bake.margin = 0
    scene.render.bake.use_clear = True

    times, weights = solar.timesteps(a.year, a.tz, a.hour_step)
    alt, az = solar.solar_position(times, a.lat, a.lon)
    dni, dhi = solar.clear_sky(alt)
    sv = solar.sun_vector(alt, az)
    steps = np.nonzero(alt > np.radians(a.min_alt))[0]
    if a.max_steps:
        steps = steps[: a.max_steps]

    nprobe = len(centres)
    acc = np.zeros(nprobe)              # Wh/m2 accumulated
    analytic = 0.0
    t0 = time.time()
    per_step = []
    for k, i in enumerate(steps):
        bg.inputs["Strength"].default_value = float(dhi[i]) / np.pi
        sun_data.energy = float(dni[i])
        d = mathutils.Vector(tuple(sv[i]))
        sun.rotation_mode = "QUATERNION"
        sun.rotation_quaternion = d.to_track_quat("Z", "Y")

        bpy.ops.object.select_all(action="DESELECT")
        probes.select_set(True)
        bpy.context.view_layer.objects.active = probes
        t1 = time.time()
        status = bpy.ops.object.bake(type="DIFFUSE")
        if "FINISHED" not in status:
            raise RuntimeError(f"bake did not finish: {status}")
        px = np.array(img.pixels[:], dtype=np.float64).reshape(res, res, 4)[:, :, 0]
        vals = np.zeros(nprobe)
        for p in range(nprobe):
            gx, gy = p % side, p // side
            block = px[gy * BLOCK:(gy + 1) * BLOCK, gx * BLOCK:(gx + 1) * BLOCK]
            vals[p] = block[INNER, INNER].mean()
        e = np.pi * vals                                    # W/m2
        acc += e * float(weights[i])
        analytic += (float(dni[i]) * np.sin(alt[i]) + float(dhi[i])) * float(weights[i])
        per_step.append({"step": int(i), "seconds": round(time.time() - t1, 2),
                         "calibration_w_m2": float(e[-1]),
                         "calibration_analytic_w_m2":
                             float(dni[i]) * float(np.sin(alt[i])) + float(dhi[i])})
        print(f"[{k+1}/{len(steps)}] step {i} alt={np.degrees(alt[i]):.1f} "
              f"bake={per_step[-1]['seconds']:.2f}s cal={e[-1]:.1f} vs "
              f"{per_step[-1]['calibration_analytic_w_m2']:.1f} W/m2", flush=True)

    total_s = time.time() - t0
    kwh = acc / 1000.0
    meta = {
        "engine": "Blender Cycles " + bpy.app.version_string,
        "device": scene.cycles.device,
        "samples": a.samples,
        "probes": int(nprobe - 1),
        "steps": int(len(steps)),
        "seconds_total": round(total_s, 2),
        "seconds_per_bake_mean": round(total_s / max(1, len(steps)), 3),
        "calibration_kwh_m2_cycles": float(kwh[-1]),
        "calibration_kwh_m2_analytic": float(analytic / 1000.0),
        "calibration_rel_error": float(abs(kwh[-1] - analytic / 1000.0)
                                       / (analytic / 1000.0)),
        "probe_size_m": a.probe_size,
    }
    np.savez_compressed(a.out, kwh=kwh[:-1], calibration_kwh=kwh[-1],
                        probe_index=pr["index"], centres=centres[:-1],
                        normals=normals[:-1])
    with open(a.out + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"summary": meta, "per_step": per_step}, f, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
