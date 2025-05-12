import h5py

# Ouvrir le fichier en lecture seule
with h5py.File('h.h5', 'r') as f:
    # Afficher les groupes et datasets à la racine
    print("Clés à la racine du fichier :")
    for key in f.keys():
        print(key)

