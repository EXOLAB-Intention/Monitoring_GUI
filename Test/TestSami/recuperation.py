import datetime
import h5py

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


# show_h5_structure("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\d.h5")



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


def show_root_metadata(hdf5_file_path):
    try:
        with h5py.File(hdf5_file_path, 'r') as f:
            root_attrs = dict(f.attrs)
            if root_attrs:
                print(f"Métadonnées à la racine de '{hdf5_file_path}':")
                for key, value in root_attrs.items():
                    print(f"  - {key}: {value}")
            else:
                print(f"Aucune métadonnée à la racine du fichier '{hdf5_file_path}'.")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier HDF5 : {e}")

show_root_metadata("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\1.h5")

# import h5py

# def set_subject_file_true(h5_path):
#     try:
#         with h5py.File(h5_path, 'a') as f:  # 'a' = lecture/écriture sans écrasement
#             f.attrs['subject_created'] = True
#         print(f"✅ Attribut 'subject_file = True' ajouté à la racine de {h5_path}.")
#         return True
#     except Exception as e:
#         print(f"❌ Erreur lors de la modification du fichier : {e}")
#         return False

# set_subject_file_true("C:\\Users\\sidib\\Documents\\GitHub\\Monitoring_GUI\\datas\\recuperation\\sensor_20250604_224334_trial1.h5")
