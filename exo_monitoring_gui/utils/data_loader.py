import os
import h5py
import pandas as pd

def load_metadata(subject_file):
    data = {}
    image_path = None
    try:
        with h5py.File(subject_file, 'r') as f:
            if 'metadata' in f:
                metadata = f['metadata']
                data = dict(metadata.attrs)
                image_path = data.get('image_path', None)
    except Exception as e:
        print(f"Erreur lors du chargement des données existantes : {e}")
    return data, image_path

def save_metadata(subject_file, data):
    try:
        with h5py.File(subject_file, 'a') as f:
            if 'metadata' in f:
                metadata = f['metadata']
            else:
                metadata = f.create_group('metadata')
            for key, value in data.items():
                metadata.attrs[key] = value
        return True
    except Exception as e:
        print(f"Erreur lors de l'enregistrement des données : {e}")
        return False

def save_to_default(data, path="participants.h5"):
    try:
        df = pd.DataFrame([data])
        df.to_hdf(path, key="participants", mode="w")
        return True
    except Exception as e:
        print(f"Erreur lors de l'enregistrement local : {e}")
        return False
