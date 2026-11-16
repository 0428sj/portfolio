# VMB 에서 내보낸 lanelet2 osm 을 Autoware 주행·주차 조건으로 검사 (+ 위에서 본 그림)
import sys, math, xml.etree.ElementTree as E, numpy as np, matplotlib
from collections import Counter
from matplotlib.path import Path
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = sys.argv[1]; png = sys.argv[2] if len(sys.argv) > 2 else None
r = E.parse(src).getroot()
tg = lambda e: {t.get("k"): t.get("v") for t in e.findall("tag")}
nodes = r.findall("node")
miss = [n.get("id") for n in nodes if "local_x" not in tg(n)]
N = {n.get("id"): (float(tg(n)["local_x"]), float(tg(n)["local_y"])) for n in nodes if n.get("id") not in miss}
W = {w.get("id"): [n.get("ref") for n in w.findall("nd")] for w in r.findall("way")}
WT = {w.get("id"): tg(w) for w in r.findall("way")}
P = lambda wid: np.array([N[i] for i in W[wid]])
bad = []
print(f"[메타] {r.find('MetaInfo').attrib if r.find('MetaInfo') is not None else '없음'} · 점 {len(nodes)} (local_x 누락 {len(miss)})")
if miss: bad.append("local_x 누락 점")
print("[선/도형]", dict(Counter((t.get("type"), t.get("subtype")) for t in WT.values())))

# 차선
lan = {}
for x in r.findall("relation"):
    t = tg(x); m = {mm.get("role"): mm.get("ref") for mm in x.findall("member")}
    if t.get("type") == "lanelet":
        lan[x.get("id")] = (t, m["left"], m["right"])
    else:
        print("[규칙]", x.get("id"), t)
for k, (t, l, rr) in lan.items():
    L, R = P(l), P(rr); w0, w1 = math.dist(L[0], R[0]), math.dist(L[-1], R[-1])
    nxt = [b for b, (_, lb, rb) in lan.items() if b != k and W[l][-1] == W[lb][0] and W[rr][-1] == W[rb][0]]
    prv = [b for b, (_, lb, rb) in lan.items() if b != k and W[lb][-1] == W[l][0] and W[rb][-1] == W[rr][0]]
    print(f"[차선] {k} {t.get('subtype')} 속도 {t.get('speed_limit')} 폭 {w0:.2f}→{w1:.2f} m · 앞 {prv or '-'} 뒤 {nxt or '-'}")

# 주차장·주차 칸
lots = {w: P(w) for w, t in WT.items() if t.get("type") == "parking_lot"}
spaces = {w: t for w, t in WT.items() if t.get("type") == "parking_space"}
for w, t in WT.items():
    if t.get("area") == "yes" and "type" not in t: print(f"[주의] 종류 없는 도형 {w} (Autoware 무시)");
for k, p in lots.items():
    e = [math.dist(p[i], p[(i + 1) % len(p)]) for i in range(len(p))]
    print(f"[주차장] {k} 꼭짓점 {len(p)} 변 {[round(v, 1) for v in e]} m")
grid = np.mgrid[-100:200:0.1, 100:300:0.1].reshape(2, -1).T
for k, (t, l, rr) in lan.items():
    poly = Path(np.vstack([P(l), P(rr)[::-1]])); inl = poly.contains_points(grid)
    for j, p in lots.items():
        frac = (inl & Path(p).contains_points(grid)).sum() / max(inl.sum(), 1)
        if frac > 0: print(f"[차선↔주차장] 차선 {k} 면적의 {frac*100:.0f}% 가 주차장 {j} 안")
for w, t in spaces.items():
    p = P(w); ok2 = len(p) == 2; okw = "width" in t
    inside = [j for j, q in lots.items() if Path(q).contains_points(p).all()]
    print(f"[주차 칸] {w} 점 {len(p)} {'✓' if ok2 else '❌(2개여야)'} · width {t.get('width', '❌없음')} · 길이 {math.dist(p[0], p[-1]):.1f} m · subtype {t.get('subtype')} · 주차장 안 {inside or '❌'}")
    if not ok2 or not okw or not inside: bad.append(f"칸 {w}")
# 칸마다: 가장 가까운 차선 가운데줄 위 점(차선 주행이 멈추는 곳, 근사)이 주차장 안인지 = 주차 모드 전환 조건
def centerline(l, rr, n=300):
    def rs(q):
        s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]; t = np.linspace(0, s_[-1], n)
        return np.c_[np.interp(t, s_, q[:, 0]), np.interp(t, s_, q[:, 1])]
    return (rs(P(l)) + rs(P(rr))) / 2
CL = {k: centerline(l, rr) for k, (t, l, rr) in lan.items()}
for w, t in spaces.items():
    c = P(w).mean(0); k = min(CL, key=lambda q: np.linalg.norm(CL[q] - c, axis=1).min())
    sp = CL[k][np.argmin(np.linalg.norm(CL[k] - c, axis=1))]
    inl = [j for j, q in lots.items() if Path(q).contains_point(sp)]
    print(f"[멈춤점] 칸 {w} → 차선 {k} 위 ({sp[0]:.1f}, {sp[1]:.1f}) · 주차장 안 {inl or '❌ (주차 모드 전환 안 됨)'}")
    if not inl: bad.append(f"칸 {w} 멈춤점 주차장 밖")
if spaces and len(lan) < 2:  # mission_planner nearestUntil 은 "더 먼 차선"을 만나야 성공 → 차선 1개면 차선 밖 목표 거절
    print("[주의] 차선 1개 — 차선 밖 목표(주차)가 'Goal is not valid' 로 거절됨"); bad.append("차선 1개")
if not lots and spaces: bad.append("주차장 없음")
print("[판정]", "✅ Autoware 조건 통과" if not bad else f"❌ {bad}")

if png:
    fig, ax = plt.subplots(figsize=(7, 7), dpi=120)
    for j, p in lots.items(): ax.fill(p[:, 0], p[:, 1], color="#1f3a68", alpha=0.35, label="parking_lot" if j == list(lots)[0] else None)
    for i, (k, (t, l, rr)) in enumerate(lan.items()):
        q = np.vstack([P(l), P(rr)[::-1]]); ax.fill(q[:, 0], q[:, 1], color="#9a9a9a", alpha=0.7, label="lanelet" if i == 0 else None)
        ax.annotate(k, q.mean(0), fontsize=8)
    for i, (w, t) in enumerate(spaces.items()):
        p = P(w); d = p[-1] - p[0]; n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9) * float(t.get("width", 0)) / 2
        box = np.array([p[0] + n, p[-1] + n, p[-1] - n, p[0] - n])
        ax.fill(box[:, 0], box[:, 1], facecolor="none", edgecolor="#1a9e3f", lw=1.5, label="parking_space (width)" if i == 0 else None)
        ax.plot(p[:, 0], p[:, 1], color="black", lw=1)
    ax.set_aspect("equal"); ax.grid(color="#cccccc", lw=0.4); ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.legend(loc="best")
    fig.tight_layout(); fig.savefig(png)
