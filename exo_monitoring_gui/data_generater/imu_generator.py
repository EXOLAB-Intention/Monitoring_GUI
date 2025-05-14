# Fichier : imu_generator.py
import numpy as np

class IMUGenerator:
    def __init__(self, num_sensors=6):
        self.num_sensors = num_sensors

    def quaternion_multiply(self, q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return [
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ]

    def generate_quaternion(self, t):
        roll  = 0.1 * np.sin(0.2 * t)
        pitch = 0.1 * np.sin(0.17 * t + 1.0)
        yaw   = 0.1 * np.sin(0.13 * t + 2.0)

        qx = np.array([np.cos(roll/2), np.sin(roll/2), 0, 0])
        qy = np.array([np.cos(pitch/2), 0, np.sin(pitch/2), 0])
        qz = np.array([np.cos(yaw/2), 0, 0, np.sin(yaw/2)])

        q = self.quaternion_multiply(qz, self.quaternion_multiply(qy, qx))
        return [round(x, 5) for x in q]

    def generate(self, t):
        return [self.generate_quaternion(t + i) for i in range(self.num_sensors)]
