# 점군 지도 위에서 본 그림: 지면만 있는 칸(길 후보)·구조물 칸·걸어간 경로 (차선 위치 고르기용)
import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

def read_binary_pcd(path):
    b = open(path, "rb").read(); end = b.index(b"DATA binary\n") + len(b"DATA binary\n")
    H = {l.split()[0]: l.split()[1:] for l in b[:end].decode().splitlines() if l and not l.startswith("#")}
    dt = [(f, {"F": "f", "U": "u", "I": "i"}[t] + s) for f, s, t in zip(H["FIELDS"], H["SIZE"], H["TYPE"])]
    return np.frombuffer(b[end:], dtype=dt, count=int(H["POINTS"][0]))

m = read_binary_pcd(sys.argv[1]); tr = read_binary_pcd(sys.argv[2]); out = sys.argv[3]
RES = 0.5
x, y, z = m["x"], m["y"], m["z"]
x0, y0 = np.floor(x.min()), np.floor(y.min())
ix = ((x - x0) / RES).astype(int); iy = ((y - y0) / RES).astype(int)
W, Hh = ix.max() + 1, iy.max() + 1
zmin = np.full((Hh, W), np.inf); zmax = np.full((Hh, W), -np.inf); cnt = np.zeros((Hh, W), int)
np.minimum.at(zmin, (iy, ix), z); np.maximum.at(zmax, (iy, ix), z); np.add.at(cnt, (iy, ix), 1)
# 칸 바닥 = 칸 최저점, 경로 아래 바닥과 ±1.5 m 안일 때만 바닥으로 인정(지하·지붕 배제)
tix = ((tr["x"] - x0) / RES).astype(int).clip(0, W - 1); tiy = ((tr["y"] - y0) / RES).astype(int).clip(0, Hh - 1)
h_sensor = float(np.median(tr["z"] - np.where(np.isfinite(zmin[tiy, tix]), zmin[tiy, tix], np.nan)[~np.isnan(np.where(np.isfinite(zmin[tiy, tix]), zmin[tiy, tix], np.nan))]))
from scipy.spatial import cKDTree
gy, gx = np.mgrid[0:Hh, 0:W]; cx = x0 + (gx + 0.5) * RES; cy = y0 + (gy + 0.5) * RES
_, nn = cKDTree(np.c_[tr["x"], tr["y"]]).query(np.c_[cx.ravel(), cy.ravel()])
g_traj = (tr["z"][nn] - h_sensor).reshape(Hh, W)
has = cnt >= 3
ground_ok = has & (np.abs(zmin - g_traj) < 1.5)
rel = z - zmin[iy, ix]                                      # 점의 칸 바닥 위 높이
obs = np.zeros((Hh, W), int); np.add.at(obs, (iy[(rel > 0.25) & (rel < 1.5)], ix[(rel > 0.25) & (rel < 1.5)]), 1)
open_ground = ground_ok & (obs == 0)                        # 바닥 있고 UGV 높이에 아무것도 없음 = 길 후보
structure = has & ~open_ground
tz = h_sensor
img = np.zeros((Hh, W), int); img[structure] = 1; img[open_ground] = 2
cmap = ListedColormap(["#ffffff", "#9a9a9a", "#1f3a68"])
fig, ax = plt.subplots(figsize=(10, 13), dpi=120)
ax.imshow(img, origin="lower", cmap=cmap, extent=[x0, x0 + W * RES, y0, y0 + Hh * RES], interpolation="nearest", vmin=0, vmax=2)
ax.plot(tr["x"], tr["y"], color="#1a9e3f", lw=1.6, label="walked trajectory")
ax.plot(tr["x"][0], tr["y"][0], "o", color="black", ms=7, label="start (0,0)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#1f3a68", label="open ground"), Patch(color="#9a9a9a", label="structure / vegetation"),
                   ax.lines[0], ax.lines[1]], loc="upper right")
ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_aspect("equal")
ax.set_xticks(np.arange(-60, 141, 20)); ax.set_yticks(np.arange(-40, 261, 20)); ax.grid(color="#cccccc", lw=0.4)
fig.tight_layout(); fig.savefig(out)
print(f"라이다 높이(경로-바닥) {tz:.2f} m · 칸 {RES} m · 길 후보 {open_ground.sum()*RES*RES:.0f} m² · 구조물 {structure.sum()*RES*RES:.0f} m²")
