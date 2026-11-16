#!/usr/bin/env python3
# 실시간 판정: 토픽별 수신 주기와 지연(수신 시각의 sim time - header.stamp)
import sys
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.parameter import Parameter
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import OccupancyGrid

TOPICS = [
    ("/sensing/lidar/concatenated/pointcloud", PointCloud2),
    ("/perception/obstacle_segmentation/single_frame/pointcloud", PointCloud2),
    ("/perception/obstacle_segmentation/pointcloud", PointCloud2),
    ("/perception/occupancy_grid_map/map", OccupancyGrid),
]
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0  # sim 초


class Judge(Node):
    def __init__(self):
        super().__init__("judge_realtime", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.rx = {t: [] for t, _ in TOPICS}
        for t, typ in TOPICS:
            self.create_subscription(typ, t, lambda m, t=t: self.cb(t, m), qos_profile_sensor_data)

    def cb(self, topic, msg):
        now = self.get_clock().now().nanoseconds * 1e-9
        st = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if now > 0:
            self.rx[topic].append((now, now - st))


def main():
    rclpy.init()
    n = Judge()
    t0 = None
    while rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.5)
        now = n.get_clock().now().nanoseconds * 1e-9
        if now > 0 and t0 is None:
            t0 = now
        if t0 is not None and now - t0 > DURATION:
            break
    for t, _ in TOPICS:
        a = np.array(n.rx[t])
        if len(a) < 2:
            print(f"{t}: NO DATA")
            continue
        rate = (len(a) - 1) / (a[-1, 0] - a[0, 0])
        lat = a[:, 1] * 1000
        print(f"{t}: n={len(a)} rate={rate:.2f} Hz latency ms median={np.median(lat):.0f} p95={np.percentile(lat, 95):.0f} max={lat.max():.0f}")


if __name__ == "__main__":
    main()
