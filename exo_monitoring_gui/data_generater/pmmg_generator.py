# Fichier : pmmg_generator.py
import math

class PMMGGenerator:
    def __init__(self, num_sensors=8):
        self.num_sensors = num_sensors

    def generate(self, t):
        return [round(110 + (10 + i) * math.sin(t + i * 0.3), 2) for i in range(self.num_sensors)]
