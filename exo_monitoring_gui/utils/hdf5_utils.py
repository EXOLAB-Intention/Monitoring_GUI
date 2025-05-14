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
            # Attempt to read from root (new structure)
            root_attrs = dict(f.attrs)
            participant_data_from_root = {}
            for key, value in root_attrs.items():
                if key.startswith("participant_"):
                    # Store with original key or strip prefix, depending on desired return format
                    # Storing with original key for now, as it includes the "participant_" prefix
                    participant_data_from_root[key] = value
                if key == "image_path": # Check for image_path at root as well
                     image_path = value


            if participant_data_from_root:
                data = participant_data_from_root
                # If image_path was specifically named 'participant_image_path'
                if 'participant_image_path' in data and image_path is None:
                    image_path = data['participant_image_path']
                elif 'image_path' in root_attrs : # if image_path is at root and not prefixed
                     image_path = root_attrs['image_path']


            # Fallback to /metadata group if no participant data found at root
            # or if explicitly needed (e.g. if data is still empty)
            if not data and 'metadata' in f:
                metadata_group = f['metadata']
                legacy_data = {}
                for key in metadata_group.attrs:
                    legacy_data[key] = metadata_group.attrs[key]
                
                if legacy_data:
                    data = legacy_data # Overwrite data with legacy data
                    if 'image_path' in metadata_group.attrs:
                        image_path = metadata_group.attrs['image_path']
            elif not data and not participant_data_from_root:
                 # If neither participant_ data at root nor /metadata group, data remains empty.
                 pass


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
            is_new_structure = False
            # Check for new structure indicators (e.g., presence of participant_ prefixed attrs at root)
            for key in f.attrs.keys():
                if key.startswith("participant_"):
                    is_new_structure = True
                    break
            
            # Or, if no /metadata group exists but it's not an empty file (has other root attrs perhaps)
            if not is_new_structure and 'metadata' not in f and len(f.attrs) > 0:
                 # This condition is a bit ambiguous, could be a new file being created by another process
                 # For simplicity, if /metadata does not exist, assume we should write to root if data is participant data
                 # A more robust check might be needed depending on file creation lifecycle
                 # For now, if any key in `data` implies it's participant data, lean towards new structure
                 for data_key in data.keys():
                     if data_key.lower().replace(' ', '_') in ['name', 'age', 'last_name', 'description']:
                         is_new_structure = True # Tentatively new if it looks like participant data
                         break

            if is_new_structure:
                for key, value in data.items():
                    attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                    f.attrs[attr_key] = value
                    if key.lower() == 'image_path': # Also save unprefixed image_path if provided that way
                        f.attrs['image_path'] = value
            else:
                if 'metadata' in f:
                    metadata_group = f['metadata']
                else:
                    metadata_group = f.create_group('metadata')
                
                for key, value in data.items():
                    metadata_group.attrs[key] = value
            
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
            for key, value in data.items():
                # Standardiser les noms de clés pour les attributs des participants
                attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                f.attrs[attr_key] = value
            
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