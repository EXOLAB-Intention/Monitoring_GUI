# Fichier : emg_generator.py
import random

class EMGGenerator:
    def __init__(self, num_sensors=8):
        self.num_sensors = num_sensors

    def generate(self):
        emg = []
        for _ in range(self.num_sensors):
            if random.random() < 0.2:
                val = random.uniform(-1e-4, 1e-4)
            elif random.random() < 0.3:
                val = random.uniform(-1e-6, 1e-6)
            else:
                val = random.gauss(0, 2e-5)
            emg.append(round(val, 7))
        return emg

