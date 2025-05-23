import h5py

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


show_h5_structure("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\data6.h5")

import h5py

# Remplace ce chemin par le chemin réel de ton fichier HDF5
h5_file_path = "C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\data6.h5"

# Ouvre le fichier HDF5 en mode lecture/écriture
with h5py.File(h5_file_path, 'r+') as f:
    # Ajoute ou modifie l'attribut à la racine
    f.attrs['subject_created'] = True

print("Attribut 'subject_current = True' ajouté à la racine du fichier.")
