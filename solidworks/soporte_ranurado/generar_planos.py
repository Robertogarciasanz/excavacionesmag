"""Genera el plano (PDF A3 + PNG) del soporte con ranura en arco.

Las cotas son las mismas variables globales que usa la macro de SolidWorks
(Soporte_Ranurado_v1.bas). Ejes: X largo, Y alto, Z profundidad (Z=0 cara
posterior). Sistema europeo (primer diedro).

Uso:  python3 generar_planos.py
"""
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Circle, Rectangle
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

# ---------------- VARIABLES (iguales que en la macro) ----------------
L, H, D = 160, 13, 54            # base: largo, alto, fondo
E = 20                           # espesor del alma / oreja
XP, YP = 48, 46                  # eje del buje inferior (pivote)
RR = 40                          # radio de la ranura y del buje superior
DB, LB = 33, 44                  # diametro y largo de los bujes
DS, DT = 17, 12                  # taladro buje inferior / superior
AR, AS = 24, 12                  # ancho de oreja / ancho de ranura
XO = 87                          # X del extremo de la oreja (48 + 39)
S1, S2 = 18, 52                  # angulos de la ranura (grados)
XG = 110                         # pie del nervio inclinado
XB1, XB2, ZB = 100, 135, 34      # taladros avellanados de la base
DA, DAV = 14, 28                 # taladro y avellanado 90 grados
RF = 10                          # redondeo esquinas delanteras de la base

A1 = math.degrees(math.acos((XO - XP) / RR))   # angulo del extremo de la oreja
YU = YP + RR                                    # eje del buje superior
YO = YP + RR * math.sin(math.radians(A1))


def arc_line(r, a1, a2, n=120):
    return LineString([(XP + r * math.cos(math.radians(a1 + (a2 - a1) * i / n)),
                        YP + r * math.sin(math.radians(a1 + (a2 - a1) * i / n))) for i in range(n + 1)])


# ---------------- GEOMETRIA ----------------
base_f = box(0, 0, L, H)
alma = Polygon([(XP - DB / 2, H), (XG, H), (XO, YO), (XP, YU), (XP - DB / 2, YU)])
oreja = arc_line(RR, A1, 90).buffer(AR / 2, quad_segs=32)
ranura = arc_line(RR, S1, S2).buffer(AS / 2, quad_segs=32)
buje_i = Point(XP, YP).buffer(DB / 2, quad_segs=48)
buje_s = Point(XP, YU).buffer(DB / 2, quad_segs=48)
tal_i = Point(XP, YP).buffer(DS / 2, quad_segs=32)
tal_s = Point(XP, YU).buffer(DT / 2, quad_segs=32)
placa = unary_union([alma, oreja]).difference(unary_union([ranura, tal_i, tal_s]))
frente = unary_union([base_f, alma, oreja, buje_i, buje_s])


def base_planta():
    b = box(0, 0, L, D)
    for x in (0, L):  # redondeo de las esquinas delanteras (Z = D)
        cx = RF if x == 0 else L - RF
        corner = box(min(x, cx), D - RF, max(x, cx), D)
        b = b.difference(corner).union(Point(cx, D - RF).buffer(RF, quad_segs=16).intersection(corner))
    return b


# ---------------- AYUDAS DE DIBUJO ----------------
LW, THIN = 0.7, 0.25
ARW = 2.5


def poly_lines(ax, g, ox, oy, sx=1, sy=1, swap=False, **kw):
    geoms = getattr(g, "geoms", [g])
    for p in geoms:
        for ring in [p.exterior, *p.interiors]:
            xs, ys = ring.xy
            if swap:
                xs, ys = ys, xs
            ax.plot([ox + sx * x for x in xs], [oy + sy * y for y in ys], color="k", lw=kw.get("lw", LW),
                    ls=kw.get("ls", "-"))


def line(ax, p, q, lw=LW, ls="-", color="k"):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, ls=ls)


def hidden(ax, p, q):
    line(ax, p, q, lw=THIN + 0.1, ls=(0, (3, 1.5)))


def axisl(ax, p, q):
    line(ax, p, q, lw=THIN, ls=(0, (8, 2, 1.5, 2)), color="#c0392b")


def arrow(ax, tip, d):
    ux, uy = d
    px, py = -uy, ux
    ax.add_patch(MplPoly([tip, (tip[0] - ARW * ux + 0.6 * px, tip[1] - ARW * uy + 0.6 * py),
                          (tip[0] - ARW * ux - 0.6 * px, tip[1] - ARW * uy - 0.6 * py)], closed=True, color="k", lw=0))


def dim_h(ax, x1, x2, y_ref1, y_ref2, y, txt=None):
    """Cota horizontal entre x1 y x2 situada a la altura y."""
    for x, yr in ((x1, y_ref1), (x2, y_ref2)):
        line(ax, (x, yr + (1 if y > yr else -1)), (x, y + (1.5 if y > yr else -1.5)), lw=THIN)
    line(ax, (x1, y), (x2, y), lw=THIN)
    arrow(ax, (x1, y), (-1, 0) if x2 > x1 else (1, 0))
    arrow(ax, (x2, y), (1, 0) if x2 > x1 else (-1, 0))
    ax.text((x1 + x2) / 2, y + 0.8, txt or fmt(abs(x2 - x1)), ha="center", va="bottom", fontsize=7)


def dim_v(ax, y1, y2, x_ref1, x_ref2, x, txt=None):
    for yy, xr in ((y1, x_ref1), (y2, x_ref2)):
        line(ax, (xr + (1 if x > xr else -1), yy), (x + (1.5 if x > xr else -1.5), yy), lw=THIN)
    line(ax, (x, y1), (x, y2), lw=THIN)
    arrow(ax, (x, y1), (0, -1) if y2 > y1 else (0, 1))
    arrow(ax, (x, y2), (0, 1) if y2 > y1 else (0, -1))
    ax.text(x - 0.8, (y1 + y2) / 2, txt or fmt(abs(y2 - y1)), ha="right", va="center", fontsize=7, rotation=90)


def leader(ax, tip, ang, length, txt):
    a = math.radians(ang)
    p = (tip[0] + length * math.cos(a), tip[1] + length * math.sin(a))
    line(ax, tip, p, lw=THIN)
    arrow(ax, tip, (-math.cos(a), -math.sin(a)))
    right = math.cos(a) >= 0
    q = (p[0] + (8 if right else -8), p[1])
    line(ax, p, q, lw=THIN)
    ax.text(q[0] + (0.5 if right else -0.5), q[1], txt, fontsize=7, ha="left" if right else "right", va="center")


def fmt(v):
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


# ---------------- VISTAS ----------------
def alzado(ax, ox, oy):
    poly_lines(ax, frente, ox, oy)
    for c, r in (((XP, YP), DB / 2), ((XP, YU), DB / 2)):
        ax.add_patch(Circle((ox + c[0], oy + c[1]), r, fill=False, lw=LW))
    for c, r in (((XP, YP), DS / 2), ((XP, YU), DT / 2)):
        ax.add_patch(Circle((ox + c[0], oy + c[1]), r, fill=False, lw=LW))
    poly_lines(ax, ranura, ox, oy)
    # taladros avellanados de la base (ocultos)
    for xb in (XB1, XB2):
        for s in (-1, 1):
            hidden(ax, (ox + xb + s * DA / 2, oy), (ox + xb + s * DA / 2, oy + H - (DAV - DA) / 2))
            hidden(ax, (ox + xb + s * DA / 2, oy + H - (DAV - DA) / 2), (ox + xb + s * DAV / 2, oy + H))
        axisl(ax, (ox + xb, oy - 3), (ox + xb, oy + H + 3))
    # ejes
    for yc in (YP, YU):
        axisl(ax, (ox + XP - DB / 2 - 4, oy + yc), (ox + XP + DB / 2 + 4, oy + yc))
    axisl(ax, (ox + XP, oy + YP - DB / 2 - 4), (ox + XP, oy + YU + DB / 2 + 4))
    ax.add_patch(matplotlib.patches.Arc((ox + XP, oy + YP), 2 * RR, 2 * RR, theta1=A1 - 6, theta2=94,
                                        lw=THIN, ls=(0, (8, 2, 1.5, 2)), color="#c0392b"))
    # cotas
    dim_h(ax, ox, ox + L, oy, oy, oy - 12)
    dim_h(ax, ox, ox + XP, oy, oy + YP, oy - 6)
    dim_h(ax, ox + XP, ox + XO, oy + YP, oy + YO, oy - 6)
    dim_h(ax, ox + XO, ox + XG, oy + YO, oy + H, oy - 6)
    dim_v(ax, oy, oy + H, ox, ox, ox - 6)
    dim_v(ax, oy, oy + YP, ox + XP - DB / 2, ox + XP - DB / 2, ox - 12)
    dim_v(ax, oy + YP, oy + YU, ox + XP - DB / 2, ox + XP - DB / 2, ox - 12)
    dim_v(ax, oy, oy + YU + DB / 2, ox + XP, ox + XP, ox - 18)
    leader(ax, (ox + XP - DB / 2 * 0.707, oy + YU + DB / 2 * 0.707), 125, 14, f"ø{DB}")
    leader(ax, (ox + XP - DT / 2 * 0.707, oy + YU - DT / 2 * 0.707), 200, 30, f"ø{DT}")
    leader(ax, (ox + XP - DS / 2 * 0.707, oy + YP - DS / 2 * 0.707), 215, 22, f"ø{DS}")
    leader(ax, (ox + XP + DB / 2 * 0.707, oy + YP - DB / 2 * 0.707), -40, 10, f"ø{DB}")
    a = math.radians(70)
    leader(ax, (ox + XP + (RR + AR / 2) * math.cos(a), oy + YP + (RR + AR / 2) * math.sin(a)), 60, 14, f"R{RR + AR // 2}")
    a = math.radians(35)
    leader(ax, (ox + XP + (RR + AS / 2) * math.cos(a), oy + YP + (RR + AS / 2) * math.sin(a)), 30, 22,
           f"Ranura {AS}  R{RR} ({S1}°–{S2}°)")
    leader(ax, (ox + XO + AR / 2, oy + YO), 0, 8, f"R{AR // 2}")
    ax.text(ox + L / 2, oy + YU + DB / 2 + 12, "ALZADO", ha="center", fontsize=9, weight="bold")


def perfil(ax, ox, oy):
    """Vista lateral izquierda: Z hacia la derecha."""
    ytop = max(frente.bounds[3], 0)
    ax.add_patch(Rectangle((ox, oy), D, H, fill=False, lw=LW))
    ear_top = placa.bounds[3]
    ax.add_patch(Rectangle((ox, oy + H), E, ear_top - H, fill=False, lw=LW))
    for yc in (YP, YU):
        ax.add_patch(Rectangle((ox, oy + yc - DB / 2), LB, DB, fill=False, lw=LW))
        axisl(ax, (ox - 3, oy + yc), (ox + LB + 3, oy + yc))
    for yc, d in ((YP, DS), (YU, DT)):
        hidden(ax, (ox, oy + yc - d / 2), (ox + LB, oy + yc - d / 2))
        hidden(ax, (ox, oy + yc + d / 2), (ox + LB, oy + yc + d / 2))
    for s in (-1, 1):
        hidden(ax, (ox + ZB + s * DA / 2, oy), (ox + ZB + s * DA / 2, oy + H - (DAV - DA) / 2))
        hidden(ax, (ox + ZB + s * DA / 2, oy + H - (DAV - DA) / 2), (ox + ZB + s * DAV / 2, oy + H))
    axisl(ax, (ox + ZB, oy - 3), (ox + ZB, oy + H + 3))
    dim_h(ax, ox, ox + D, oy, oy, oy - 12)
    dim_h(ax, ox, ox + E, oy + ear_top, oy + ear_top, oy + ytop + 8)
    dim_h(ax, ox, ox + LB, oy + YU + DB / 2, oy + YU + DB / 2, oy + ytop + 15)
    dim_h(ax, ox, ox + ZB, oy, oy, oy - 6)
    dim_v(ax, oy, oy + ear_top, ox + E, ox + E, ox + D + 8, txt=fmt(ear_top))
    ax.text(ox + D / 2, oy + ytop + 24, "PERFIL IZQUIERDO", ha="center", fontsize=9, weight="bold")


def planta(ax, ox, oy):
    """Planta (primer diedro, debajo del alzado): Z=0 arriba, Z=D abajo."""
    bp = base_planta()
    xs, zs = bp.exterior.xy
    ax.plot([ox + x for x in xs], [oy - z for z in zs], color="k", lw=LW)
    # alma + oreja (Z 0..E) y bujes (Z 0..LB)
    x0, x1 = placa.bounds[0], max(placa.bounds[2], XG)
    line(ax, (ox + XP + DB / 2, oy - E), (ox + x1, oy - E))
    for xx in (XP - DB / 2, XP + DB / 2):
        line(ax, (ox + xx, oy), (ox + xx, oy - LB))
    line(ax, (ox + XP - DB / 2, oy - LB), (ox + XP + DB / 2, oy - LB))
    line(ax, (ox + x1, oy), (ox + x1, oy - E))
    line(ax, (ox + XO + AR / 2, oy), (ox + XO + AR / 2, oy - E), lw=THIN)
    for xb in (XB1, XB2):
        ax.add_patch(Circle((ox + xb, oy - ZB), DA / 2, fill=False, lw=LW))
        ax.add_patch(Circle((ox + xb, oy - ZB), DAV / 2, fill=False, lw=LW))
        axisl(ax, (ox + xb - DAV / 2 - 3, oy - ZB), (ox + xb + DAV / 2 + 3, oy - ZB))
        axisl(ax, (ox + xb, oy - ZB - DAV / 2 - 3), (ox + xb, oy - ZB + DAV / 2 + 3))
    axisl(ax, (ox + XP, oy + 3), (ox + XP, oy - LB - 3))
    dim_h(ax, ox, ox + XB1, oy - D + RF, oy - ZB, oy - D - 8)
    dim_h(ax, ox + XB1, ox + XB2, oy - ZB, oy - ZB, oy - D - 8)
    dim_h(ax, ox + XB2, ox + L, oy - ZB, oy - D + RF, oy - D - 8)
    dim_v(ax, oy - ZB, oy, ox + L, ox + L, ox + L + 8)
    dim_v(ax, oy - D, oy, ox + L, ox + L, ox + L + 15)
    leader(ax, (ox + XB2 + DAV / 2 * 0.707, oy - ZB - DAV / 2 * 0.707), -35, 10,
           f"2x ø{DA} avell. ø{DAV}x90°")
    leader(ax, (ox + RF * (1 - 0.707), oy - D + RF * (1 - 0.707)), 225, 8, f"R{RF}")
    ax.text(ox + L / 2, oy + 5, "PLANTA", ha="center", fontsize=9, weight="bold")


# ---------------- ISOMETRICA (z-buffer) ----------------
def prism(poly2d, z0, z1, plane="xy"):
    """Triangulos 3D de un prisma extruido desde un poligono (con agujeros)."""
    tris = []

    def P(u, v, w):
        return (u, v, w) if plane == "xy" else (u, w, v)  # "xz": poligono en X-Z, extruido en Y

    for t in constrained_delaunay_triangles(poly2d).geoms:
        c = list(t.exterior.coords)[:3]
        tris.append([P(u, v, z0) for u, v in c])
        tris.append([P(u, v, z1) for u, v in c])
    for g in getattr(poly2d, "geoms", [poly2d]):
        for ring in [g.exterior, *g.interiors]:
            cs = list(ring.coords)
            for (u1, v1), (u2, v2) in zip(cs[:-1], cs[1:]):
                a, b, c, d = P(u1, v1, z0), P(u2, v2, z0), P(u2, v2, z1), P(u1, v1, z1)
                tris += [[a, b, c], [a, c, d]]
    return tris


def iso(ax, cx, cy, size=100, res=900):
    import numpy as np
    tris = []
    bp = base_planta()
    holes = unary_union([Point(xb, ZB).buffer(DA / 2, quad_segs=24) for xb in (XB1, XB2)])
    hc = H - (DAV - DA) / 2
    tris += prism(bp.difference(holes), 0, hc, "xz")
    # avellanado: tronco de cono aproximado por anillos
    n = 6
    for i in range(n):
        za, zb = hc + (H - hc) * i / n, hc + (H - hc) * (i + 1) / n
        r = DA / 2 + (DAV - DA) / 2 * (i + 0.5) / n
        ring = bp.difference(unary_union([Point(xb, ZB).buffer(r, quad_segs=24) for xb in (XB1, XB2)]))
        tris += prism(ring, za, zb, "xz")
    tris += prism(placa.difference(base_f), 0, E)
    tris += prism(buje_i.difference(tal_i), 0, LB)
    tris += prism(buje_s.difference(tal_s), 0, LB)
    T = np.array(tris, dtype=float) - np.array([L / 2, 50, D / 2])

    c = np.array([0.75, 0.75, 1.0]); c /= np.linalg.norm(c)
    r = np.cross([0, 1, 0], c); r /= np.linalg.norm(r)
    u = np.cross(c, r)
    P2 = np.stack([T @ r, T @ u, T @ c], axis=-1)            # (n,3,3): x, y, profundidad
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    light = np.array([0.35, 0.85, 0.4]); light /= np.linalg.norm(light)
    shade = 0.45 + 0.5 * np.abs(nrm @ light)

    lo, hi = P2[..., :2].min((0, 1)), P2[..., :2].max((0, 1))
    sc = (res - 20) / (hi - lo).max()
    pix = (P2[..., :2] - lo) * sc + 10
    zbuf = np.full((res, res), -1e9)
    img = np.ones((res, res, 3))
    edge = np.zeros((res, res), dtype=np.int64) - 1
    for k in range(len(T)):
        p = pix[k]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax_, ay), (bx, by), (cx_, cy_) = p
        den = (by - cy_) * (ax_ - cx_) + (cx_ - bx) * (ay - cy_)
        if abs(den) < 1e-9:
            continue
        w1 = ((by - cy_) * (xs - cx_) + (cx_ - bx) * (ys - cy_)) / den
        w2 = ((cy_ - ay) * (xs - cx_) + (ax_ - cx_) * (ys - cy_)) / den
        w3 = 1 - w1 - w2
        m = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
        if not m.any():
            continue
        z = w1 * P2[k, 0, 2] + w2 * P2[k, 1, 2] + w3 * P2[k, 2, 2]
        xs, ys, z = xs[m], ys[m], z[m]
        ok = (xs >= 0) & (xs < res) & (ys >= 0) & (ys < res)
        xs, ys, z = xs[ok], ys[ok], z[ok]
        upd = z > zbuf[ys, xs] + 1e-4
        g = shade[k]
        zbuf[ys[upd], xs[upd]] = z[upd]
        img[ys[upd], xs[upd]] = (0.8 * g, 0.86 * g, g)
        edge[ys[upd], xs[upd]] = int(round(g * 1000))
    # siluetas y aristas: cambios de sombreado o de profundidad
    gx = np.zeros_like(zbuf, dtype=bool)
    sh = edge
    gx[:, 1:] |= np.abs(sh[:, 1:] - sh[:, :-1]) > 25
    gx[1:, :] |= np.abs(sh[1:, :] - sh[:-1, :]) > 25
    img[gx] = (0.15, 0.15, 0.2)
    ext = (cx - size / 2, cx + size / 2, cy - size / 2, cy + size / 2)
    ax.imshow(img, origin="lower", extent=ext, interpolation="antialiased")
    ax.text(cx, cy + size / 2 - 22, "ISOMÉTRICA (sin escala)", ha="center", fontsize=9, weight="bold")


# ---------------- LAMINA A3 ----------------
def main():
    fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 420)
    ax.set_ylim(0, 297)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=1.2))

    alzado(ax, 45, 150)
    perfil(ax, 250, 150)
    planta(ax, 45, 120)
    iso(ax, 345, 100, size=105)

    # cajetin
    x0, y0 = 250, 10
    ax.add_patch(Rectangle((x0, y0), 160, 34, fill=False, lw=1))
    for yy in (y0 + 10, y0 + 22):
        line(ax, (x0, yy), (x0 + 160, yy), lw=0.5)
    ax.text(x0 + 3, y0 + 28, "SOPORTE CON RANURA EN ARCO", fontsize=10, weight="bold", va="center")
    ax.text(x0 + 3, y0 + 16, "Material: F-1110 / S275   ·   Escala 1:1   ·   Cotas en mm   ·   A3", fontsize=7,
            va="center")
    ax.text(x0 + 3, y0 + 5, "Sistema europeo (1.er diedro)   ·   Plano nº SR-001   ·   Rev. 1", fontsize=7,
            va="center")
    ax.text(15, 16, "Notas: redondeos no indicados aristas vivas. Medidas interpretadas del boceto original; "
                    "todas son variables globales en la macro (Herramientas > Ecuaciones).",
            fontsize=6.5, va="center")

    fig.savefig("Soporte_Ranurado_plano.pdf")
    fig.savefig("Soporte_Ranurado_plano.png", dpi=150)
    print("Altura total:", fmt(frente.bounds[3]), " Angulo oreja A1:", round(A1, 2))


if __name__ == "__main__":
    main()
