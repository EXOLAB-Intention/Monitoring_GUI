import json
import os

def reset_json_file():
    base_dir = os.path.dirname(__file__)  # répertoire de ici.py
    json_full_path = os.path.join(base_dir, '..', 'plots', "sensor_mappings.json")
    json_full_path = os.path.abspath(json_full_path)
    data = {
        "EMG": {},
        "IMU": {},
        "pMMG": {}
    }
    with open(json_full_path, 'w') as f:
        json.dump(data, f, indent=2)
