import h5py
import os
from datetime import datetime
import numpy as np
import re

def load_metadata(subject_file):
    """Load metadata from an HDF5 file.
    Prioritizes reading participant_ prefixed attributes from root.
    Falls back to reading attributes from /metadata group for backward compatibility.
    """
    data = {}
    image_path = None # Initialisation de image_path

    if not os.path.exists(subject_file):
        print(f"File not found: {subject_file}")
        return data, image_path
    
    try:
        with h5py.File(subject_file, 'r') as f:
            root_attrs = dict(f.attrs)
            for key, value in root_attrs.items():
                if key.startswith("participant_"):
                    # Stocker directement la clé telle quelle, par exemple "participant_name"
                    data[key] = value 
                    # Si la clé est spécifiquement "participant_image_path", on la retient aussi pour image_path
                    if key == "participant_image_path":
                        image_path = value
                # Gérer aussi le cas où "image_path" est à la racine et n'est pas encore défini par "participant_image_path"
                elif key == "image_path" and image_path is None:
                    image_path = value
            
            # Après avoir parcouru tous les attributs, si image_path a été trouvé (soit par "image_path", soit par "participant_image_path"),
            # s'assurer qu'il est bien dans 'data' sous la clé standard "participant_image_path".
            # Cela est utile si "image_path" a été trouvé mais pas "participant_image_path", 
            # ou pour s'assurer que la valeur de "participant_image_path" (si présente) est prioritaire et stockée.
            if image_path is not None:
                data["participant_image_path"] = image_path

    except Exception as e:
        print(f"Error loading metadata from {subject_file}: {e}")
    
    return data, image_path


def save_metadata(subject_file, data: dict):
    """Save metadata to an HDF5 file.
    Detects if the file uses the new structure (participant_ attributes at root)
    or old structure (/metadata group) and saves accordingly.
    """
    try:
        with h5py.File(subject_file, 'a') as f:
            # Set subject_created attribute if it doesn't exist
            if "subject_created" not in f.attrs:
                f.attrs['subject_created'] = True

            image_path_value = None
            if "image_path" in data:
                image_path_value = data.pop("image_path") # Retire pour éviter double écriture par la boucle

            for key, value in data.items():
                # Standardiser les noms de clés pour les attributs des participants
                # Si la clé est déjà préfixée (par ex. lors du chargement/modification), ne pas re-préfixer
                if key.startswith("participant_"):
                    attr_key = key
                else:
                    attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

                f.attrs[attr_key] = value

                # Si la clé normalisée correspond à participant_image_path, on stocke sa valeur
                # pour s'assurer qu'elle soit écrite sous "image_path" si ce n'est pas déjà fait.
                if attr_key == "participant_image_path" and image_path_value is None:
                    image_path_value = value

            # Sauvegarder image_path à la racine sous la clé "image_path" s'il existe
            if image_path_value is not None:
                f.attrs["image_path"] = image_path_value

            f.attrs['last_modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return True
    except Exception as e:
        print(f"Error saving metadata to {subject_file}: {e}")
        return False


def save_to_default(data: dict, custom_filename: str = None):
    """Save metadata to a default HDF5 file if no file is specified,
    with participant metadata at the root and sensor group structure.
    If custom_filename is provided, it is used instead of generating one.
    """
    try:
        if custom_filename:
            output_filename = custom_filename
            # Ensure the directory for custom_filename exists if it includes a path
            output_dir = os.path.dirname(output_filename)
            if output_dir: # If there's a directory part
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Create a default filename based on the current date/time
            default_dir = os.path.join(os.path.expanduser("~"), "Documents", "Monitoring-Data")
            os.makedirs(default_dir, exist_ok=True)
            output_filename = os.path.join(
                default_dir, 
                f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.h5"
            )
        
        with h5py.File(output_filename, 'w') as f: # 'w' pour créer un nouveau fichier
            # Attributs de base à la racine
            f.attrs['file_creation_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.attrs['subject_created'] = True # Réactivé pour compatibilité avec load_existing_subject

            # Sauvegarder les informations du participant (data) comme attributs à la racine
            image_path_value = None
            if "image_path" in data:
                image_path_value = data.pop("image_path") # Retire pour éviter double écriture

            for key, value in data.items():
                # Standardiser les noms de clés pour les attributs des participants
                attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                f.attrs[attr_key] = value
                # Si la clé normalisée correspond à participant_image_path et que image_path_value n'a pas été défini par data["image_path"]
                if attr_key == "participant_image_path" and image_path_value is None:
                    image_path_value = value
            
            # Sauvegarder image_path à la racine sous la clé "image_path" s'il a été trouvé
            if image_path_value is not None:
                f.attrs["image_path"] = image_path_value
            
            # Créer la structure de groupes pour les données de capteurs
            sensor_group = f.create_group('Sensor')
            sensor_group.create_group('EMG')
            sensor_group.create_group('IMU')
            sensor_group.create_group('LABEL')
            sensor_group.create_group('Time')

        print(f"New HDF5 file created with participant metadata and sensor structure: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Error saving to default file: {e}")
        return None


def extract_group_data(file_path, group_name):
    """
    Retourne un dictionnaire avec les données du sous-groupe spécifié (par exemple : 'EMG', 'Time', etc.)
    Exclut les datasets vides.
    """
    def read_group(group):
        result = {}
        for key, item in group.items():
            if isinstance(item, h5py.Dataset):
                if 0 in item.shape:
                    continue  # Ignorer les datasets vides
                try:
                    result[key] = item[()]
                except Exception as e:
                    result[key] = f"Erreur de lecture : {e}"
            elif isinstance(item, h5py.Group):
                child_data = read_group(item)
                if child_data:  # Ignorer les groupes vides
                    result[key] = child_data
        return result

    with h5py.File(file_path, "r") as f:
        sensor_group = f.get("Sensor")
        if sensor_group is None:
            raise ValueError("Le groupe 'Sensor' est introuvable dans le fichier.")

        target_group = sensor_group.get(group_name)
        if target_group is None:
            raise ValueError(f"Le groupe '{group_name}' est introuvable dans 'Sensor'.")

        return read_group(target_group)





def generate_hdf5_from_raw_data(raw_data, pmmg_ids, fsr_ids, imu_ids, emg_ids, output_path="output.h5"):

    raw_data = [
    "[sensor_ts=40 ms | recv_ts=40 ms] IMU5=(w=-0.7031,x=0.0088,y=0.0164,z=-0.7106) EMG25=0.949 EMG26=0.919 EMG27=0.935 EMG28=0.932 EMG29=0.938 EMG30=0.921 EMG32=0.979 Buttons: A=0 B=0 X=0 Y=0 OK=0 Joystick: X=0,Y=0",
    "[sensor_ts=90 ms | recv_ts=89 ms] IMU5=(w=-0.7027,x=0.0085,y=0.0163,z=-0.7111) EMG25=0.949 EMG26=0.918 EMG27=0.935 EMG28=0.931 EMG29=0.936 EMG30=0.926 EMG32=0.978 Buttons: A=0 B=0 X=0 Y=0 OK=0 Joystick: X=0,Y=0",
    "[sensor_ts=140 ms | recv_ts=141 ms] EMG26=0.920 EMG28=0.934 EMG32=0.980 FSR1=0.8 PMMG1=0.12"
    ]
    
    pmmg_ids = []
    fsr_ids = []
    imu_ids = [5, 6]
    emg_ids = [25, 26, 27, 28, 29, 30, 32]

    sensor_ids = {
        'pmmg_ids': pmmg_ids,
        'fsr_ids': fsr_ids,
        'imu_ids': imu_ids,
        'emg_ids': emg_ids
    }

    emg_data = {f"emg{id}": [] for id in sensor_ids['emg_ids']}
    imu_data = {f"imu{id}": [] for id in sensor_ids['imu_ids']}
    pmmg_data = {f"pmmg{id}": [] for id in sensor_ids['pmmg_ids']}
    fsr_data = {f"fsr{id}": [] for id in sensor_ids['fsr_ids']}
    timestamps = []

    ts_regex = re.compile(r"sensor_ts=(\d+)\s*ms")
    emg_regex = re.compile(r"EMG(\d+)=([0-9.]+)")
    imu_regex = re.compile(r"IMU(\d+)=\(w=([-0-9.]+),x=([-0-9.]+),y=([-0-9.]+),z=([-0-9.]+)\)")

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

    for d in [emg_data, imu_data, pmmg_data, fsr_data]:
        for key in d:
            if len(d[key]) == 0:
                if key.startswith("imu"):
                    d[key] = np.empty((0, 4), dtype=np.float32)
                else:
                    d[key] = np.empty((0,), dtype=np.float32)
            else:
                d[key] = np.array(d[key], dtype=np.float32)

    timestamps = np.array(timestamps, dtype=np.int32)
    labels = np.empty((0,), dtype=np.int32)

    # Ouvre en mode 'a' pour ne pas écraser tout le fichier
    with h5py.File(output_path, "a") as f:
        # Supprime le groupe Sensor s'il existe
        if "Sensor" in f:
            del f["Sensor"]

        sensor_group = f.create_group("Sensor")

        for group_name, group_data in [
            ("EMG", emg_data),
            ("IMU", imu_data),
            ("PMMG", pmmg_data),
            ("FSR", fsr_data)
        ]:
            g = sensor_group.create_group(group_name)
            for name, data in group_data.items():
                g.create_dataset(name, data=data)

        sensor_group.create_group("LABEL").create_dataset("label", data=labels, dtype=np.int32)
        sensor_group.create_group("Time").create_dataset("time", data=timestamps, dtype=np.int32)

    print(f"HDF5 file saved to {output_path} (Sensor group updated, metadata preserved)")

