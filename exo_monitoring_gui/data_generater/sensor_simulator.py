from pmmg_generator import PMMGGenerator
from imu_generator import IMUGenerator
from emg_generator import EMGGenerator
from controller_generator import ControllerState
import time

class SensorSimulator:
    def __init__(self):
        self.pmmg = PMMGGenerator()
        self.imu = IMUGenerator()
        self.emg = EMGGenerator()
        self.controller = ControllerState()

    def generate_packet(self):
        t = time.time()
        return {
            "timestamp": round(t, 3),
            "pMMG": self.pmmg.generate(t),
            "IMU": self.imu.generate(t),
            "EMG": self.emg.generate(),
            "Controller": self.controller.generate(t)
        }
