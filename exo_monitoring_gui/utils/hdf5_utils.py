import h5py
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QTreeWidgetItem, QVBoxLayout
    )
from PyQt5.QtGui import QBrush, QColor
import numpy as np
import pyqtgraph as pg
import json


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
    
def plot_sensor_data(self, sensor_name, data_array):
    """Trace les données d'un capteur sur un graphique."""
    plot_widget = pg.PlotWidget()
    plot_widget.setBackground('w')
    plot_widget.setTitle(sensor_name, color='k', size='14pt')
    plot_widget.plot(self.time_axis, data_array, pen=pg.mkPen(color='b', width=2))
    plot_widget.setLabel('left', sensor_name)
    plot_widget.setLabel('bottom', 'Time (s)')
    plot_widget.showGrid(x=True, y=True)
    self.middle_layout.addWidget(plot_widget)


def load_hdf5_and_populate_tree(self, file_path):
    """Charge un fichier HDF5, met à jour le QTreeWidget, et trace automatiquement les capteurs disponibles."""
    self.connected_systems.clear()
    self.middle_layout.setParent(None)  # Efface les anciens graphes
    self.middle_layout = QVBoxLayout()
    self.middle_placeholder.setLayout(self.middle_layout)

    self.loaded_data.clear()
    data_structure = {}
    time_length = None

    with h5py.File(file_path, "r") as f:
        def visitor(name, obj):
            nonlocal time_length
            if isinstance(obj, h5py.Dataset):
                parts = name.strip("/").split("/")
                if len(parts) >= 2:
                    group_name, dataset_name = parts[-2], parts[-1]
                    group_upper = group_name.upper()
                    dataset_upper = dataset_name.upper()

                    if group_upper == "TIME":
                        time_length = len(obj[:])
                        return
                    if group_upper == "LABEL":
                        return

                    if group_upper not in data_structure:
                        data_structure[group_upper] = []
                    data_structure[group_upper].append(dataset_upper)
                    self.loaded_data[dataset_upper] = obj[:]

        f.visititems(visitor)

    # Génère X à partir de time_length et 40 ms entre chaque échantillon
    if time_length is not None:
        self.time_axis = np.arange(time_length) * 0.040
    else:
        any_key = next(iter(self.loaded_data), None)
        if any_key:
            length = len(self.loaded_data[any_key])
            self.time_axis = np.arange(length) * 0.040
        else:
            self.time_axis = []

    for group_name, dataset_list in data_structure.items():
        group_item = QTreeWidgetItem([f"{group_name} Data"])
        self.connected_systems.addTopLevelItem(group_item)

        for dataset_name in dataset_list:
            sensor_item = QTreeWidgetItem([dataset_name])
            sensor_item.setForeground(0, QBrush(QColor("black")))
            group_item.addChild(sensor_item)

            if dataset_name in self.loaded_data:
                plot_sensor_data(self, dataset_name, self.loaded_data[dataset_name])

        group_item.setExpanded(True)


def load_hdf5_data(file_path):

    loaded_data = {}
    data_structure = {}
    time_length = None

    with h5py.File(file_path, "r") as f:
        def visitor(name, obj):
            nonlocal time_length
            if isinstance(obj, h5py.Dataset):
                parts = name.strip("/").split("/")
                if len(parts) >= 2:
                    group_name, dataset_name = parts[-2], parts[-1]
                    group_upper = group_name.upper()
                    dataset_upper = dataset_name.upper()

                    if group_upper == "TIME":
                        time_length = len(obj[:])
                        return
                    if group_upper == "LABEL":
                        return

                    if group_upper not in data_structure:
                        data_structure[group_upper] = []
                    data_structure[group_upper].append(dataset_upper)
                    loaded_data[dataset_upper] = obj[:]

        f.visititems(visitor)

    if time_length is not None:
        time_axis = np.arange(time_length) * 0.040
    else:
        any_key = next(iter(loaded_data), None)
        if any_key:
            length = len(loaded_data[any_key])
            time_axis = np.arange(length) * 0.040
        else:
            time_axis = np.array([])

    return {
        "loaded_data": loaded_data,
        "data_structure": data_structure,
        "time_axis": time_axis
    }


def copy_all_data_preserve_root_metadata(source_path, dest_path):
    # Vérifier si le fichier source existe
    if not os.path.exists(source_path):
        print(f"Erreur : Le fichier source {source_path} n'existe pas.")
        return False

    # Vérifier si le fichier source est un fichier HDF5 valide
    try:
        with h5py.File(source_path, 'r') as test_file:
            test_file.attrs.keys()
    except (OSError, h5py.errors.HDF5Error) as e:
        print(f"Erreur : Le fichier source {source_path} est corrompu ou invalide : {e}")
        return False

    # Créer le fichier destination s'il n'existe pas
    if not os.path.exists(dest_path):
        with h5py.File(dest_path, 'w') as _:
            pass

    try:
        with h5py.File(source_path, 'r') as src_file, h5py.File(dest_path, 'a') as dst_file:
            # Copier les datasets/groupes
            for name in src_file:
                if name in dst_file:
                    print(f"⚠️  '{name}' existe déjà dans le fichier destination, il ne sera pas écrasé.")
                    continue
                src_file.copy(name, dst_file)

            # Copier les attributs de la racine
            for key, value in src_file.attrs.items():
                dst_file.attrs[key] = value

        return True
    except Exception as e:
        print(f"Erreur lors de la copie des données : {e}")
        return False



def copy_only_root_metadata(source_path, dest_path):
    # Vérifier si le fichier source existe
    if not os.path.exists(source_path):
        print(f"Erreur : Le fichier source {source_path} n'existe pas.")
        return False

    # Vérifier si le fichier source est un fichier HDF5 valide
    try:
        with h5py.File(source_path, 'r') as test_file:
            test_file.attrs.keys()
    except (OSError, h5py.errors.HDF5Error) as e:
        print(f"Erreur : Le fichier source {source_path} est corrompu ou invalide : {e}")
        return False

    try:
        # Créer ou ouvrir le fichier destination
        with h5py.File(source_path, 'r') as src_file, h5py.File(dest_path, 'w') as dst_file:
            # Copier uniquement les attributs de la racine
            for key, value in src_file.attrs.items():
                dst_file.attrs[key] = value
            print(f"✅ Métadonnées de la racine copiées avec succès vers {dest_path}.")
        return True
    except Exception as e:
        print(f"Erreur lors de la copie des métadonnées : {e}")
        return False

def inject_metadata_to_hdf(json_relative_path, hdf_path):
    base_dir = os.path.dirname(__file__)  # répertoire de ici.py
    json_full_path = os.path.join(base_dir, '..', 'plots', json_relative_path)
    json_full_path = os.path.abspath(json_full_path)

    # Charger le JSON
    with open(json_full_path, 'r') as f:
        metadata = json.load(f)

    # Injecter dans le HDF
    with h5py.File(hdf_path, 'a') as hdf:
        if "metadata" in hdf.attrs:
            del hdf.attrs["metadata"]
        hdf.attrs["metadata"] = json.dumps(metadata)
