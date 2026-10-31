"""Renderer for the still images and the animations.

Every pixel comes from the measured arrays: each triangle of the district is
drawn as a filled polygon whose colour is the value computed for that triangle,
with no relief shading added on top, so the colour is the datum and nothing
else. The projection is orthographic, and the triangles are painted far to near.

Outputs (see --what):
    hero        oblique view of the district coloured by annual irradiance
    svf         the same view coloured by sky view factor
    plan        top-down map, annual irradiance
    orbit       animated GIF: the district turning
    sun         animated GIF: the direct beam sweeping across a single day
    method      animated GIF: the two depth buffers of one light direction
"""

from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

BG, FG, DIM = "#0b0f14", "#e8eef6", "#9fb0c3"
JP = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP", "DejaVu Sans"]


def style():
    plt.rcParams.update({
        "font.family": JP, "figure.facecolor": BG, "axes.facecolor": BG,
        "savefig.facecolor": BG, "text.color": FG, "axes.labelcolor": FG,
        "axes.edgecolor": "#223042", "xtick.color": DIM, "ytick.color": DIM,
        "axes.grid": False, "font.size": 11, "figure.dpi": 150,
    })


def basis(az_deg: float, el_deg: float):
    az, el = np.radians(az_deg), np.radians(el_deg)
    view = np.array([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az),
                     -np.sin(el)])
    right = np.array([np.cos(az), -np.sin(az), 0.0])
    up = np.cross(right, view)
    return right, up / np.linalg.norm(up), view


def draw(ax, tri: np.ndarray, val: np.ndarray, az: float, el: float,
         cmap: str, vmin: float, vmax: float):
    right, up, view = basis(az, el)
    c = tri.mean(axis=1)
    order = np.argsort(-(c @ view))          # far to near
    t = tri[order]
    xy = np.stack([t @ right, t @ up], axis=-1)
    norm = plt.Normalize(vmin, vmax)
    colors = matplotlib.colormaps[cmap](norm(val[order]))
    pc = PolyCollection(xy, facecolors=colors, edgecolors="none",
                        antialiaseds=False)
    ax.add_collection(pc)
    flat = xy.reshape(-1, 2)
    pad = 0.02 * (flat[:, 0].max() - flat[:, 0].min())
    ax.set_xlim(flat[:, 0].min() - pad, flat[:, 0].max() + pad)
    ax.set_ylim(flat[:, 1].min() - pad, flat[:, 1].max() + pad)
    ax.set_aspect("equal")
    ax.set_axis_off()
    return matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)


def still(tri, val, out, az, el, cmap, vmax, title, cbar_label, size=(9.5, 6.4)):
    fig, ax = plt.subplots(figsize=size)
    sm = draw(ax, tri, val, az, el, cmap, 0.0, vmax)
    cb = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label(cbar_label, color=DIM)
    cb.outline.set_edgecolor("#223042")
    cb.ax.yaxis.set_tick_params(color=DIM)
    ax.set_title(title, color=FG, fontsize=15, pad=14)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def still_plain(tri, val, out, az, el, cmap, vmax, size=(12.8, 7.2)):
    """Full-bleed render with no title and no colour bar, for compositing."""
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0, 0, 1, 1])
    draw(ax, tri, val, az, el, cmap, 0.0, vmax)
    fig.savefig(out)
    plt.close(fig)
    print("wrote", out)


def frame_to_rgb(fig):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3]
    return buf.copy()


def write_gif(frames, out, ms=90, loop=0):
    from PIL import Image
    imgs = [Image.fromarray(f).convert("P", palette=Image.ADAPTIVE, colors=128)
            for f in frames]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=ms,
                 loop=loop, optimize=True, disposal=2)
    print("wrote", out, f"{os.path.getsize(out)/1e6:.2f} MB, {len(frames)} frames")


def gif_orbit(tri, val, out, vmax, cmap, title, n=48, el=24.0, width=7.2):
    frames = []
    for i in range(n):
        az = 360.0 * i / n
        fig, ax = plt.subplots(figsize=(width, width * 0.62))
        sm = draw(ax, tri, val, az, el, cmap, 0.0, vmax)
        cb = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.01)
        cb.outline.set_edgecolor("#223042")
        cb.ax.yaxis.set_tick_params(color=DIM, labelcolor=DIM, labelsize=8)
        ax.set_title(title, color=FG, fontsize=13, pad=8)
        fig.tight_layout()
        frames.append(frame_to_rgb(fig))
        plt.close(fig)
    write_gif(frames, out, ms=110)


def gif_sun(args, tri, nrm, scene_mask, keep, svf_all, out):
    """Total irradiance over one clear day, recomputed for every frame.

    Direct beam from the shadow maps, recomputed at every sun position, plus
    the diffuse term of the same model, DHI*(1+cos beta)/2 scaled by the sky
    view factor already computed for that face.
    """
    import torch

    import solar
    from neuro3d_irradiance import DirectionalShadow, sample_points, slope_bias

    dev = torch.device("cpu")
    pts, pidx = sample_points(tri[scene_mask], args.samples_per_m2, seed=0,
                              with_index=True)
    pnrm = nrm[scene_mask][pidx].astype(np.float32)
    shadow = DirectionalShadow(torch.from_numpy(pts).to(dev), args.texel,
                              torch.from_numpy(pnrm).to(dev))
    c = tri.mean(axis=1)
    q = torch.from_numpy((c + nrm * 0.05)[keep].astype(np.float32)).to(dev)
    nq = torch.from_numpy(nrm[keep].astype(np.float32)).to(dev)

    # 21 June, local clock time, one frame every twenty minutes of daylight.
    import datetime as dt
    hours = np.arange(4.0, 20.01, 1.0 / 3.0)
    times = np.array([
        (dt.datetime(args.year, 6, 21) + dt.timedelta(hours=float(h) - args.tz)
         ).replace(tzinfo=dt.timezone.utc).timestamp() for h in hours])
    alt, az = solar.solar_position(times, args.lat, args.lon)
    dni, dhi = solar.clear_sky(alt)
    tilt = (1.0 + np.clip(nrm[keep][:, 2], -1.0, 1.0)) / 2.0
    diffuse_unit = tilt * svf_all[keep]
    sv = solar.sun_vector(alt, az)

    vals = []
    for i in range(len(times)):
        if alt[i] <= np.radians(1.0):
            vals.append(np.zeros(int(keep.sum()), np.float32))
            continue
        diff = (float(dhi[i]) * diffuse_unit).astype(np.float32)
        d = torch.tensor(sv[i], dtype=torch.float32)
        cosi = (nq @ d).clamp(min=0.0)
        vis = shadow.visible(d, q, 0.05, 0,
                             front_bias=slope_bias(cosi, args.texel, 0.05))
        vals.append((cosi * float(dni[i]) * vis).cpu().numpy() + diff)
        print(f"  frame {i+1}/{len(times)} alt={np.degrees(alt[i]):.1f} deg",
              flush=True)

    vmax = float(np.concatenate(vals).max()) or 1.0
    full = np.zeros(len(tri), np.float32)
    frames = []
    for i, v in enumerate(vals):
        full[:] = 0.0
        full[keep] = v
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        sm = draw(ax, tri, full, 20.0, 26.0, "inferno", 0.0, vmax)
        cb = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.01)
        cb.set_label("W/m²", color=DIM, fontsize=9)
        cb.outline.set_edgecolor("#223042")
        cb.ax.yaxis.set_tick_params(color=DIM, labelcolor=DIM, labelsize=8)
        mins = int(round(float(hours[i]) * 60.0))
        ax.set_title(f"6 月 21 日 {mins//60:02d}:{mins%60:02d}  "
                     f"全日射（直達＋天空散乱） W/m²（太陽高度 "
                     f"{max(0.0, np.degrees(alt[i])):.0f}°）",
                     color=FG, fontsize=12, pad=8)
        fig.tight_layout()
        frames.append(frame_to_rgb(fig))
        plt.close(fig)
    write_gif(frames, out, ms=110)


def gif_method(args, tri, nrm, scene_mask, out):
    """The two depth buffers that decide one light direction."""
    import torch

    from neuro3d_irradiance import DirectionalShadow, sample_points

    dev = torch.device("cpu")
    pts, pidx = sample_points(tri[scene_mask], args.samples_per_m2, seed=0,
                              with_index=True)
    pnrm = nrm[scene_mask][pidx].astype(np.float32)
    # A few hundred thousand points read exactly like the full set at this
    # size, and keep the drawing time sane.
    if len(pts) > 260_000:
        k = np.random.default_rng(0).choice(len(pts), 260_000, replace=False)
        pts, pnrm = pts[k], pnrm[k]
    pts_t = torch.from_numpy(pts).to(dev)
    pnrm_t = torch.from_numpy(pnrm).to(dev)
    sh = DirectionalShadow(pts_t, args.texel, pnrm_t)

    frames = []
    azs = np.linspace(60.0, 260.0, 24)
    for azd in azs:
        d = np.array([np.sin(np.radians(azd)) * np.cos(np.radians(35.0)),
                      np.cos(np.radians(azd)) * np.cos(np.radians(35.0)),
                      np.sin(np.radians(35.0))], np.float32)
        dt_ = torch.from_numpy(d)
        u, v = sh._basis(dt_)
        px = (pts_t @ u).numpy()
        py = (pts_t @ v).numpy()
        pd = (pts_t @ dt_).numpy()
        facing = (pnrm_t @ dt_).numpy()
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.3))
        for ax, mask, name, cm in (
                (axes[0], facing < -1e-4, "背面バッファ（街区の影）", "magma"),
                (axes[1], facing > 1e-4, "前面バッファ（埋もれた面）", "cividis")):
            o = np.argsort(pd[mask])
            ax.scatter(px[mask][o], py[mask][o], c=pd[mask][o], s=0.6, lw=0,
                       cmap=cm)
            ax.set_aspect("equal"); ax.set_axis_off()
            ax.set_title(name, color=FG, fontsize=12)
        fig.suptitle(f"光の方向 方位 {azd:.0f}° ・ 高度 35°："
                     f"この 2 枚で街区の全面を 1 回で判定",
                     color=FG, fontsize=13)
        fig.tight_layout()
        frames.append(frame_to_rgb(fig))
        plt.close(fig)
    write_gif(frames + frames[::-1], out, ms=130)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--what", default="hero,svf,plan,orbit,sun,method")
    ap.add_argument("--lat", type=float, default=34.39298186)
    ap.add_argument("--lon", type=float, default=132.46132208)
    ap.add_argument("--tz", type=float, default=9.0)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--texel", type=float, default=0.5)
    ap.add_argument("--samples-per-m2", type=float, default=2.0)
    a = ap.parse_args()

    style()
    os.makedirs(a.out, exist_ok=True)
    d = np.load(a.tile)
    n3 = np.load(a.neuro3d)
    tri = d["tri"].astype(np.float32)
    nrm = n3["normals"].astype(np.float64)
    keep = n3["keep"]
    per = n3["per_tri"]
    area = per[:, 5]
    scene_mask = np.isfinite(nrm).all(1) & (area > 1e-6)

    annual = per[:, 0] + per[:, 1]
    svf = per[:, 4]
    vmax = float(np.percentile(annual[keep], 99))
    want = set(a.what.split(","))

    if "hero" in want:
        still(tri[keep], annual[keep], os.path.join(a.out, "hero_irradiance.png"),
              20.0, 26.0, "inferno", vmax,
              "広島市 3 次メッシュ 51324376：面ごとの年間日射量",
              "kWh/m²·年")
    if "svf" in want:
        still(tri[keep], svf[keep], os.path.join(a.out, "hero_svf.png"),
              20.0, 26.0, "viridis", 1.0,
              "同じ街区の天空率（0 = 完全に閉塞、1 = 全天可視）", "天空率")
    if "plain" in want:
        still_plain(tri[keep], annual[keep],
                    os.path.join(a.out, "hero_plain.png"),
                    20.0, 26.0, "inferno", vmax)
    if "plan" in want:
        still(tri[keep], annual[keep], os.path.join(a.out, "plan_irradiance.png"),
              0.0, 89.9, "inferno", vmax,
              "真上から見た年間日射量", "kWh/m²·年", size=(8.4, 7.4))
    if "orbit" in want:
        gif_orbit(tri[keep], annual[keep], os.path.join(a.out, "orbit.gif"),
                  vmax, "inferno", "年間日射量 kWh/m²·年")
    if "sun" in want:
        gif_sun(a, tri, nrm, scene_mask, keep, svf,
                os.path.join(a.out, "sun_day.gif"))
    if "method" in want:
        gif_method(a, tri, nrm, scene_mask, os.path.join(a.out, "method.gif"))


if __name__ == "__main__":
    main()
