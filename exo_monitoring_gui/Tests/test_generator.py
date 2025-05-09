import time
import json
import numpy as np
import sys
import os

# Ajoute le dossier racine du projet (exo_monitoring_gui) au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Essaie d'importer le module sensor_simulator depuis data_generater
from exo_monitoring_gui.data_generator.sensor_simulator import SensorSimulator

def convert(o):
    if isinstance(o, np.generic):
        return o.item()
    return o

simulator = SensorSimulator()

interval = 0.042  # Intervalle fixe entre chaque point de données (≈24 Hz)
timestamp = 0.0   # On commence à 0.0 comme dans dummy_data_generator

print("Starting the simulation session... (Press Ctrl+C to stop)")

while True:
    packet = simulator.generate_packet()  # Appel sans argument timestamp
    print(json.dumps(packet, default=convert, indent=2))

    timestamp += interval  # On incrémente artificiellement le temps
    time.sleep(interval)   # On attend juste pour simuler un rythme régulier
