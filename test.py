import h5py
import numpy as np
import re

raw_data = [
    "[sensor_ts=40 ms | recv_ts=40 ms] IMU5=(w=-0.7031,x=0.0088,y=0.0164,z=-0.7106) EMG25=0.949 EMG26=0.919 EMG27=0.935 EMG28=0.932 EMG29=0.938 EMG30=0.921 EMG32=0.979 Buttons: A=0 B=0 X=0 Y=0 OK=0 Joystick: X=0,Y=0",
    "[sensor_ts=90 ms | recv_ts=89 ms] IMU5=(w=-0.7027,x=0.0085,y=0.0163,z=-0.7111) EMG25=0.949 EMG26=0.918 EMG27=0.935 EMG28=0.931 EMG29=0.936 EMG30=0.926 EMG32=0.978 Buttons: A=0 B=0 X=0 Y=0 OK=0 Joystick: X=0,Y=0"
]

# IDs dynamiques
sensor_ids = {
    'emg_ids': [25, 26, 27, 28, 29, 30, 32],
    'imu_ids': [5],
    'pmmg_ids': [],
    'fsr_ids': []
}

# Initialisation des structures
emg_data = {f"emg{id}": [] for id in sensor_ids['emg_ids']}
imu_data = {f"imu{id}": [] for id in sensor_ids['imu_ids']}
pmmg_data = {f"pmmg{id}": [] for id in sensor_ids['pmmg_ids']}
fsr_data = {f"fsr{id}": [] for id in sensor_ids['fsr_ids']}
labels = []  # vide car pas fourni
timestamps = []

# Regex pour parser
ts_regex = re.compile(r"sensor_ts=(\d+)\s*ms")
emg_regex = re.compile(r"EMG(\d+)=([0-9.]+)")
imu_regex = re.compile(r"IMU(\d+)=\(w=([-0-9.]+),x=([-0-9.]+),y=([-0-9.]+),z=([-0-9.]+)\)")

# Parsing
for line in raw_data:
    ts_match = ts_regex.search(line)
    if not ts_match:
        continue
    timestamps.append(int(ts_match.group(1)))

    for match in emg_regex.finditer(line):
        id = int(match.group(1))
        val = float(match.group(2))
        key = f"emg{id}"
        if key in emg_data:
            emg_data[key].append(val)

    for match in imu_regex.finditer(line):
        id = int(match.group(1))
        values = [float(match.group(i)) for i in range(2, 6)]
        key = f"imu{id}"
        if key in imu_data:
            imu_data[key].append(values)

# Remplissage des capteurs vides avec array vide
for d in [emg_data, imu_data, pmmg_data, fsr_data]:
    for key in d:
        if len(d[key]) == 0:
            if key.startswith("imu"):
                d[key] = np.empty((0, 4), dtype=np.float32)
            else:
                d[key] = np.empty((0,), dtype=np.float32)
        else:
            d[key] = np.array(d[key], dtype=np.float32)

# Conversion time et label
timestamps = np.array(timestamps, dtype=np.int32)
labels = np.empty((0,), dtype=np.int32)  # si jamais tu veux les ajouter plus tard

# Écriture du fichier HDF5
with h5py.File("output.h5", "w") as f:
    sensor_group = f.create_group("Sensor")
    
    for group_name, group_data in [("EMG", emg_data), ("IMU", imu_data), ("PMMG", pmmg_data), ("FSR", fsr_data)]:
        g = sensor_group.create_group(group_name)
        for name, data in group_data.items():
            g.create_dataset(name, data=data)

    label_group = sensor_group.create_group("LABEL")
    label_group.create_dataset("label", data=labels, dtype=np.int32)

    time_group = sensor_group.create_group("Time")
    time_group.create_dataset("time", data=timestamps, dtype=np.int32)
