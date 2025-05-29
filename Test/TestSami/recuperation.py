# import datetime
# import h5py

# def show_h5_structure(file_path):
#     """HDF5 파일 구조를 트리(가지) 형식으로 출력하는 함수"""

#     def print_tree(name, obj, prefix=""):
#         parts = name.strip("/").split("/")
#         depth = len(parts)
#         is_dataset = isinstance(obj, h5py.Dataset)
#         label = f"[Dataset] {parts[-1]} - shape: {obj.shape}, dtype: {obj.dtype}" if is_dataset else f"[Group] {parts[-1] if parts[-1] else '/'}"
        
#         # 트리 기호 결정
#         tree_symbol = "└── " if depth == 0 or name == parts[-1] else "├── "
#         indent = "│   " * (depth - 1) + tree_symbol
#         print(indent + label)

#     with h5py.File(file_path, "r") as f:
#         print(f"HDF5 Structure for '{file_path}':\n")
#         f.visititems(lambda name, obj: print_tree(name, obj))


# show_h5_structure("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\datas\\recuperation\\sensor_20240618_054252_trial1.h5")



# def save_metadata(subject_file, data: dict):
#     """Save metadata to an HDF5 file.
#     Detects if the file uses the new structure (participant_ attributes at root)
#     or old structure (/metadata group) and saves accordingly.
#     """
#     try:
#         with h5py.File(subject_file, 'a') as f:
#             # Set subject_created attribute if it doesn't exist
#             if "subject_created" not in f.attrs:
#                 f.attrs['subject_created'] = True

#             image_path_value = None
#             if "image_path" in data:
#                 image_path_value = data.pop("image_path") # Retire pour éviter double écriture par la boucle

#             for key, value in data.items():
#                 # Standardiser les noms de clés pour les attributs des participants
#                 # Si la clé est déjà préfixée (par ex. lors du chargement/modification), ne pas re-préfixer
#                 if key.startswith("participant_"):
#                     attr_key = key
#                 else:
#                     attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

#                 f.attrs[attr_key] = value

#                 # Si la clé normalisée correspond à participant_image_path, on stocke sa valeur
#                 # pour s'assurer qu'elle soit écrite sous "image_path" si ce n'est pas déjà fait.
#                 if attr_key == "participant_image_path" and image_path_value is None:
#                     image_path_value = value

#             # Sauvegarder image_path à la racine sous la clé "image_path" s'il existe
#             if image_path_value is not None:
#                 f.attrs["image_path"] = image_path_value

#             f.attrs['last_modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#         return True
#     except Exception as e:
#         print(f"Error saving metadata to {subject_file}: {e}")
#         return False





# def get_root_metadata(h5_path):
#     with h5py.File(h5_path, "r") as f:
#         return {key: f.attrs[key] for key in f.attrs}
    

# print(get_root_metadata("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\d.h5"))


# save_metadata("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\data6.h5",get_root_metadata("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\d.h5"))


import h5py
import os

def copy_all_data_preserve_root_metadata(source_path, dest_path):
    """
    Copie tous les groupes/datasets d'un fichier HDF5 source vers un fichier destination,
    sans modifier les attributs à la racine du fichier destination.

    :param source_path: Chemin du fichier source HDF5
    :param dest_path: Chemin du fichier destination HDF5 (créé s'il n'existe pas)
    """
    # Créer le fichier destination s'il n'existe pas
    if not os.path.exists(dest_path):
        with h5py.File(dest_path, 'w') as _:
            pass  # fichier vide, sans attributs

    with h5py.File(source_path, 'r') as src_file, h5py.File(dest_path, 'a') as dst_file:
        for name in src_file:
            if name in dst_file:
                print(f"⚠️  '{name}' existe déjà dans le fichier destination, il ne sera pas écrasé.")
                continue
            src_file.copy(name, dst_file)

# Exemple d'utilisation
source_file = 'C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\datas\\recuperation\\sensor_20240618_062038_trial1.h5'
dest_file = 'C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\d.h5'

copy_all_data_preserve_root_metadata(source_file, dest_file)
