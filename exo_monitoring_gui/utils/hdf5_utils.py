import h5py
import os
from datetime import datetime

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
                print(key)
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
    try:
        with h5py.File(subject_file, 'a') as f:
            # Écrire toujours à la racine
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