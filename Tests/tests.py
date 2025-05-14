import h5py

file_path = "C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\exo_monitoring_gui\\datas\\data1.h5"


# Ouvrir le fichier HDF5 en mode lecture
with h5py.File(file_path, 'r') as file:
    # Parcourir et afficher les groupes et les datasets dans le fichier
    def print_dataset(name, obj):
        if isinstance(obj, h5py.Dataset):
            print(f"Dataset: {name}")
            print("Contenu du dataset (premières 10 lignes):")
            print(obj[:100])  # Affiche les 10 premières lignes du dataset

    # Visiter tous les éléments dans le fichier
    file.visititems(print_dataset)

