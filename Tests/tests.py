import h5py

file_path = "C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\exo_monitoring_gui\\datas\\data2.h5"

def explore_h5_metadata(filepath):
    metadata = {}

    with h5py.File(filepath, 'r') as f:
        def explore(name, obj):
            node_info = {
                "type": type(obj).__name__,
                "attributes": {key: val for key, val in obj.attrs.items()}
            }
            metadata[name] = node_info

        f.visititems(explore)

    return metadata

# Exemple d'utilisation :
meta = explore_h5_metadata("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\o.h5")
print(meta)



def show_h5_structure(file_path):
    """HDF5 파일 구조를 트리(가지) 형식으로 출력하는 함수"""

    def print_tree(name, obj, prefix=""):
        parts = name.strip("/").split("/")
        depth = len(parts)
        is_dataset = isinstance(obj, h5py.Dataset)
        label = f"[Dataset] {parts[-1]} - shape: {obj.shape}, dtype: {obj.dtype}" if is_dataset else f"[Group] {parts[-1] if parts[-1] else '/'}"
        
        # 트리 기호 결정
        tree_symbol = "└── " if depth == 0 or name == parts[-1] else "├── "
        indent = "│   " * (depth - 1) + tree_symbol
        print(indent + label)

    with h5py.File(file_path, "r") as f:
        print(f"HDF5 Structure for '{file_path}':\n")
        f.visititems(lambda name, obj: print_tree(name, obj))


show_h5_structure(file_path)



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


print(extract_group_data(file_path, "EMG")["emgL1"])


meta_dict = {
    'metadata': {
        'type': 'Group',
        'attributes': {
            'Age': '4',
            'Description': '',
            'Forearm length (cm)': '',
            'Height (cm)': '6',
            'Last Name': 'g',
            'Name': 'g',
            'Shank length (cm)': '',
            'Thigh length (cm)': '',
            'Upperarm length (cm)': '',
            'Weight (kg)': '6',
            'collection_date': '2025-05-14 12:19:33'
        }
    },
    'trials': {
        'type': 'Group',
        'attributes': {}
    }
}

def write_metadata_to_h5(file_path, meta_dict):
    with h5py.File(file_path, "a") as f:  # "a" pour append (lecture/écriture sans effacer)
        for group_name, group_info in meta_dict.items():
            # Créer le groupe s'il n'existe pas
            group = f.require_group(group_name)
            # Ajouter les attributs
            for attr_key, attr_val in group_info.get("attributes", {}).items():
                group.attrs[attr_key] = attr_val

# Exemple d'utilisation
write_metadata_to_h5(file_path, meta_dict)

