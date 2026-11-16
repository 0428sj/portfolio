#!/usr/bin/env python3
# 점유격자 번짐 판정: 같은 stamp 의 장애물 점군과 격자를 맞대어 정렬률·유령 칸 비율 계산
import sys
import time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.parameter import Parameter
from rclpy.duration import Duration
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import OccupancyGrid
from sensor_msgs_py import point_cloud2
import tf2_ros

WALL = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
R_MIN, R_MAX, Z_MIN, Z_MAX = 1.0, 20.0, 0.0, 2.0  # 가상 스캔 설정과 동일 범위
BIN = 0.00349065850  # 0.2 deg, 가상 스캔 angle_increment
OCC = 65


def quat_yaw(q):
    return np.arctan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class Judge(Node):
    def __init__(self):
        super().__init__("judge_ogm", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.tfb = tf2_ros.Buffer(cache_time=Duration(seconds=600))
        tf2_ros.TransformListener(self.tfb, self)
        self.clouds, self.grids = {}, {}
        self.create_subscription(PointCloud2, "/perception/obstacle_segmentation/single_frame/pointcloud", self.on_cloud, qos_profile_sensor_data)
        self.create_subscription(OccupancyGrid, "/perception/occupancy_grid_map/map", self.on_grid, 10)

    def on_cloud(self, m):
        a = point_cloud2.read_points(m, field_names=("x", "y", "z"), skip_nans=True)
        p = np.stack([a["x"], a["y"], a["z"]], 1)
        r = np.hypot(p[:, 0], p[:, 1])
        k = (r > R_MIN) & (r < R_MAX) & (p[:, 2] > Z_MIN) & (p[:, 2] < Z_MAX)
        self.clouds[(m.header.stamp.sec, m.header.stamp.nanosec)] = (m.header.stamp, p[k], m.header.frame_id)

    def on_grid(self, m):
        g = np.array(m.data, dtype=np.int16).reshape(m.info.height, m.info.width)
        o = m.info.origin
        self.grids[(m.header.stamp.sec, m.header.stamp.nanosec)] = (g, m.info.resolution, o.position.x, o.position.y, quat_yaw(o.orientation), m.header.frame_id)

    def evaluate(self):
        rows = []
        for k in sorted(set(self.clouds) & set(self.grids)):
            stamp, p, cf = self.clouds[k]
            g, res, ox, oy, oyaw, gf = self.grids[k]
            try:
                t = self.tfb.lookup_transform(gf, cf, rclpy.time.Time.from_msg(stamp))
            except Exception:
                continue
            tr, q = t.transform.translation, t.transform.rotation
            yaw = quat_yaw(q)
            c, s = np.cos(yaw), np.sin(yaw)
            ang = np.arctan2(p[:, 1], p[:, 0])
            rng = np.hypot(p[:, 0], p[:, 1])
            b = np.floor((ang + np.pi) / BIN).astype(int)
            order = np.lexsort((rng, b))
            first = np.ones(len(order), bool)
            first[1:] = b[order][1:] != b[order][:-1]
            ep = p[order][first]  # 부채꼴마다 가장 가까운 점 = 가상 스캔 끝점

            def to_cell(pts):
                mx = tr.x + c * pts[:, 0] - s * pts[:, 1] - ox
                my = tr.y + s * pts[:, 0] + c * pts[:, 1] - oy
                co, so = np.cos(-oyaw), np.sin(-oyaw)
                gx, gy = co * mx - so * my, so * mx + co * my
                return np.floor(gx / res).astype(int), np.floor(gy / res).astype(int)

            ix, iy = to_cell(ep)
            ok = (ix >= 0) & (iy >= 0) & (ix < g.shape[1]) & (iy < g.shape[0])
            align = (g[iy[ok], ix[ok]] >= OCC).mean() if ok.any() else np.nan
            ax, ay = to_cell(p)
            near = np.zeros_like(g, bool)
            okp = (ax >= 1) & (ay >= 1) & (ax < g.shape[1] - 1) & (ay < g.shape[0] - 1)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near[ay[okp] + dy, ax[okp] + dx] = True
            vx, vy = to_cell(np.zeros((1, 3)))
            yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]]
            ring = np.hypot(xx - vx[0], yy - vy[0]) * res < R_MAX
            occ = (g >= OCC) & ring
            ghost = (occ & ~near).sum() / max(occ.sum(), 1)
            rows.append((align, ghost, occ.sum()))
        return np.array(rows)


def main():
    rclpy.init()
    n = Judge()
    t0 = time.time()
    while time.time() - t0 < WALL:
        rclpy.spin_once(n, timeout_sec=0.1)
    r = n.evaluate()
    if len(r) == 0:
        print("NO MATCHED FRAMES")
        sys.exit(3)
    print(f"frames={len(r)} align median={np.nanmedian(r[:, 0]) * 100:.1f}% mean={np.nanmean(r[:, 0]) * 100:.1f}% | "
          f"ghost median={np.median(r[:, 1]) * 100:.1f}% mean={np.mean(r[:, 1]) * 100:.1f}% | occupied cells/frame={np.mean(r[:, 2]):.0f}")
    np.save(sys.argv[2] if len(sys.argv) > 2 else "/tmp/judge_ogm.npy", r)


if __name__ == "__main__":
    main()
