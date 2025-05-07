import h5py

# Ouvre le fichier en lecture seule ('r')
with h5py.File("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\sa.h5", "r") as f:    # Affiche tous les groupes et datasets à la racine
    print("Contenu du fichier :")
    for key in f.keys():
        print(f" - {key}: {type(f[key])}")

    # Exemple : accéder à un dataset s’il existe
    if "mon_dataset" in f:
        data = f["mon_dataset"][:]
        print("Données :", data)

    # Lire un attribut global (s'il existe)
    if "subject_created" in f.attrs:
        print("Attribut subject_created :", f.attrs["subject_created"])
