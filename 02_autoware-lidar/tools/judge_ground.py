#!/usr/bin/env python3
# 지면 제거 판정: 지면 제거 전(range_cropped) vs 후(single_frame) 점군의 높이 분포를 같은 stamp 끼리 비교
import sys
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2

BEFORE = "/perception/obstacle_segmentation/range_cropped/pointcloud"
AFTER = "/perception/obstacle_segmentation/single_frame/pointcloud"
R_MAX = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0  # 판정 반경 [m]
Z_GROUND = 0.10   # 이보다 낮으면 "지면 높이" 점 [m] (base_link = 뒷바퀴 축 아래 지면)
Z_OBJ = 0.50      # 이보다 높으면 "확실한 물체" 점 [m]
N_FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 20


def xyz(msg):
    a = point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)
    a = np.stack([a["x"], a["y"], a["z"]], axis=1).astype(np.float64)
    return a[np.hypot(a[:, 0], a[:, 1]) < R_MAX]


class Judge(Node):
    def __init__(self):
        super().__init__("judge_ground")
        self.buf = {BEFORE: {}, AFTER: {}}
        self.rows = []
        for t in (BEFORE, AFTER):
            self.create_subscription(PointCloud2, t, lambda m, t=t: self.cb(t, m), qos_profile_sensor_data)

    def cb(self, topic, msg):
        k = (msg.header.stamp.sec, msg.header.stamp.nanosec)
        self.buf[topic][k] = xyz(msg)
        if k in self.buf[BEFORE] and k in self.buf[AFTER]:
            b, a = self.buf[BEFORE].pop(k), self.buf[AFTER].pop(k)
            self.rows.append((
                len(b), len(a),
                int((b[:, 2] < Z_GROUND).sum()), int((a[:, 2] < Z_GROUND).sum()),
                int((b[:, 2] > Z_OBJ).sum()), int((a[:, 2] > Z_OBJ).sum()),
            ))


def main():
    rclpy.init()
    n = Judge()
    while rclpy.ok() and len(n.rows) < N_FRAMES:
        rclpy.spin_once(n, timeout_sec=1.0)
    r = np.array(n.rows, dtype=np.float64)
    if len(r) == 0:
        print("NO MATCHED FRAMES")
        sys.exit(3)
    nb, na, gb, ga, ob, oa = r.sum(axis=0)
    print(f"frames={len(r)} (r<{R_MAX} m, base_link)")
    print(f"before: {nb:.0f} pts | ground-height(z<{Z_GROUND}) {gb:.0f} | object(z>{Z_OBJ}) {ob:.0f}")
    print(f"after : {na:.0f} pts | ground-height(z<{Z_GROUND}) {ga:.0f} | object(z>{Z_OBJ}) {oa:.0f}")
    print(f"A  ground-height share in obstacle cloud = {ga / max(na, 1) * 100:.2f} %")
    print(f"B  object points kept                    = {oa / max(ob, 1) * 100:.2f} %")
    print(f"C  ground-height points removed          = {(gb - ga) / max(gb, 1) * 100:.2f} %")


if __name__ == "__main__":
    main()
