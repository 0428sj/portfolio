#!/usr/bin/env python3
# 차량 속도 + IMU 요레이트 적분으로 map->base_link TF 발행 (2D 추측항법, 지도·GNSS 없음)
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from autoware_vehicle_msgs.msg import VelocityReport
from tf2_ros import TransformBroadcaster


def stamp_s(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9


class DeadReckoning(Node):
    def __init__(self):
        super().__init__("dead_reckoning")
        self.frame = self.declare_parameter("map_frame", "map").value
        self.child = self.declare_parameter("base_frame", "base_link").value
        self.body = self.declare_parameter("imu_expected_frame", "base_link").value
        self.v = 0.0
        self.x = self.y = self.yaw = 0.0
        self.t_prev = None
        self.tfb = TransformBroadcaster(self)
        self.pub = self.create_publisher(Odometry, "~/odom", 10)
        self.create_subscription(VelocityReport, "/vehicle/status/velocity_status", self.on_vel, 10)
        # imu_data 는 imu_corrector 가 base_link 로 변환·바이어스 보정한 값 (원시 IMU 는 뒤집혀 장착됨)
        self.create_subscription(Imu, "/sensing/imu/imu_data", self.on_imu, qos_profile_sensor_data)

    def on_vel(self, m):
        self.v = m.longitudinal_velocity

    def on_imu(self, m):
        if m.header.frame_id != self.body:
            self.get_logger().error(f"imu frame {m.header.frame_id} != {self.body}", throttle_duration_sec=5.0)
            return
        t = stamp_s(m.header)
        if self.t_prev is None or t < self.t_prev:  # 첫 메시지 또는 bag 되감기 -> 원점 재시작
            self.x = self.y = self.yaw = 0.0
            self.t_prev = t
            self.publish(m.header.stamp, m.angular_velocity.z)
            return
        dt = t - self.t_prev
        self.t_prev = t
        wz = m.angular_velocity.z
        yaw_mid = self.yaw + 0.5 * wz * dt
        self.x += self.v * math.cos(yaw_mid) * dt
        self.y += self.v * math.sin(yaw_mid) * dt
        self.yaw += wz * dt
        self.publish(m.header.stamp, wz)

    def publish(self, stamp, wz):
        qz, qw = math.sin(self.yaw / 2), math.cos(self.yaw / 2)
        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = self.frame
        tf.child_frame_id = self.child
        tf.transform.translation.x, tf.transform.translation.y = self.x, self.y
        tf.transform.rotation.z, tf.transform.rotation.w = qz, qw
        self.tfb.sendTransform(tf)
        o = Odometry()
        o.header = tf.header
        o.child_frame_id = self.child
        o.pose.pose.position.x, o.pose.pose.position.y = self.x, self.y
        o.pose.pose.orientation.z, o.pose.pose.orientation.w = qz, qw
        o.twist.twist.linear.x, o.twist.twist.angular.z = self.v, wz
        self.pub.publish(o)


def main():
    rclpy.init()
    rclpy.spin(DeadReckoning())


if __name__ == "__main__":
    main()
