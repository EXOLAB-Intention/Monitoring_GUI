import h5py

file_path = "C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\1.h5"


def read_root_metadata(hdf5_path):
    with h5py.File(hdf5_path, 'r') as f:
        print("Métadonnées à la racine du fichier :")
        for key, value in f.attrs.items():
            print(f"{key}: {value}")


print(read_root_metadata(file_path))

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



def read_time_dataset(hdf5_path):
    with h5py.File(hdf5_path, 'r') as f:
        time_data = f['Sensor']['Time']['time'][:]  # Lecture des données
        print("Contenu du dataset 'time' :", time_data)

read_time_dataset(file_path)