"""render_previews.py -- tiny CPU rasterizer for her fairy-body previews (task FAIRY, 2026-10-29).

Input: the JSON meshes written by the Rust test `dump_preview_meshes`
  (FAIRY_DUMP_DIR=<dir> cargo test --features sanctuary --test fairy_body dump_preview_meshes)
  = the exact meshes, colours and world transforms the Bevy plugin builds.
Output: <preset>_<view>.png (front, three_quarter, back) in the output dir.
Usage: python3 render_previews.py <dump_dir> <out_dir>
Needs numpy + Pillow only. Lambert shading, z-buffer, alpha-blended wings (back to front),
glow drawn as a soft additive 2D halo (approximation of Bevy's additive halo + bloom).
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

W, H, SS = 480, 640, 2
VIEWS = {"front": 0.0, "three_quarter": 40.0, "back": 180.0}
TARGET = np.array([0.0, 0.55, 0.0])
DIST, FOV = 2.7, 30.0


def cam(yaw_deg):
    a = math.radians(yaw_deg)
    eye = TARGET + DIST * np.array([math.sin(a), 0.12, math.cos(a)])
    f = TARGET - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, r, u, f


def project(p, eye, r, u, f, w, h):
    d = p - eye
    x, y, z = d @ r, d @ u, d @ f
    s = (h / 2) / math.tan(math.radians(FOV) / 2)
    return np.stack([w / 2 + s * x / z, h / 2 - s * y / z, z], -1)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def raster(tri, cols, alpha, zbuf, img, blend):
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
    h, w = zbuf.shape
    xmin, xmax = int(max(0, math.floor(min(x0, x1, x2)))), int(min(w - 1, math.ceil(max(x0, x1, x2))))
    ymin, ymax = int(max(0, math.floor(min(y0, y1, y2)))), int(min(h - 1, math.ceil(max(y0, y1, y2))))
    if xmin > xmax or ymin > ymax:
        return
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(den) < 1e-12:
        return
    xs, ys = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
    a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
    b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
    c = 1 - a - b
    m = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
    if not m.any():
        return
    z = a * z0 + b * z1 + c * z2
    zb = zbuf[ymin:ymax + 1, xmin:xmax + 1]
    m &= z < zb
    if not m.any():
        return
    col = a[..., None] * cols[0] + b[..., None] * cols[1] + c[..., None] * cols[2]
    sub = img[ymin:ymax + 1, xmin:xmax + 1]
    if blend:
        sub[m] = sub[m] * (1 - alpha) + col[m] * alpha
    else:
        sub[m] = col[m]
        zb[m] = z[m]


def render(parts, yaw, label):
    w, h = W * SS, H * SS
    eye, r, u, f = cam(yaw)
    gy = np.linspace(0, 1, h)[:, None, None]
    img = (np.array([0.020, 0.024, 0.040]) * (1 - gy) + np.array([0.060, 0.066, 0.090]) * gy) * np.ones((h, w, 3))
    zbuf = np.full((h, w), np.inf)
    key = -f * 0.6 + u * 0.6 - r * 0.45
    key /= np.linalg.norm(key)
    fill = -f * 0.8 - u * 0.2 + r * 0.6
    fill /= np.linalg.norm(fill)
    halos, trans = [], []
    for p in parts:
        pos = np.array(p["pos"], float)
        if p["add"]:
            c = pos.mean(0)
            halos.append((c, np.linalg.norm(pos - c, axis=1).max(), np.array(p["emissive"][:3])))
            continue
        nrm = np.array(p["nrm"], float)
        base = np.array(p["base"][:3])
        vc = np.array(p["col"])[:, :3] if p["col"] else np.ones((len(pos), 3))
        if p["blend"]:  # double-sided thin membranes
            lam = 0.35 + 0.75 * np.abs(nrm @ key) + 0.2 * np.abs(nrm @ fill)
        else:
            lam = 0.22 + 0.85 * np.clip(nrm @ key, 0, 1) + 0.25 * np.clip(nrm @ fill, 0, 1)
        col = base * vc * lam[:, None] + np.array(p["emissive"][:3])
        sp = project(pos, eye, r, u, f, w, h)
        for t in np.array(p["idx"]).reshape(-1, 3):
            tri = sp[t]
            if p["blend"]:
                trans.append((tri[:, 2].mean(), tri, col[t], p["base"][3]))
            else:
                raster(tri, col[t], None, zbuf, img, False)
    trans.sort(key=lambda x: -x[0])
    for _, tri, c, al in trans:
        raster(tri, c, al, zbuf, img, True)
    ys, xs = np.mgrid[0:h, 0:w]
    s = (h / 2) / math.tan(math.radians(FOV) / 2)
    for c, rad, em in halos:
        sp = project(c[None], eye, r, u, f, w, h)[0]
        pr = rad * s / sp[2]
        d2 = ((xs - sp[0]) ** 2 + (ys - sp[1]) ** 2) / (pr * pr)
        img += (0.25 * np.exp(-d2 * 1.6))[..., None] * em
    out = Image.fromarray((to_srgb(img) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    ImageDraw.Draw(out).text((10, 10), label, fill=(220, 220, 225))
    return out


def main(dump, outdir):
    os.makedirs(outdir, exist_ok=True)
    for fn in sorted(os.listdir(dump)):
        if not fn.endswith(".json"):
            continue
        preset = fn[:-5]
        with open(os.path.join(dump, fn)) as fh:
            parts = json.load(fh)
        for view, yaw in VIEWS.items():
            im = render(parts, yaw, "preset: %s   view: %s   (procedural preview)" % (preset, view.replace("_", "-")))
            im.save(os.path.join(outdir, "%s_%s.png" % (preset, view)))
            print("wrote", preset, view)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
