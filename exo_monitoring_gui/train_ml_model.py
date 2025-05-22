import os
import sys
import json
import pandas as pd
import numpy as np
import torch
import argparse
from datetime import datetime

# Ajouter le chemin du projet pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import modifié pour résoudre l'erreur
from utils.body_motion_predictor import MLBodyPredictor, BodyMotionNetwork
# Fix import issue by creating a local implementation
def convert_imu_csv_to_json(csv_path, json_output_path):
    """Convertit les données IMU de CSV vers JSON."""
    print(f"📊 Début de conversion CSV → JSON: {os.path.basename(csv_path)}")
    
    try:
        # Charger le fichier CSV
        print(f"   ┣ Lecture du fichier CSV...")
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()  # Supprimer les espaces dans les noms de colonnes
        print(f"   ┣ CSV chargé avec succès: {len(df)} lignes trouvées")
        
        # Mapping capteur -> partie du corps
        sensor_map = {
            1: "torso",
            2: "forearm_l",
            3: "forearm_r",
            4: "calves_l",
            5: "calves_r",
            6: "head"
        }
        
        # Création de la structure
        print(f"   ┣ Extraction des quaternions pour {len(sensor_map)} capteurs...")
        imu_data = []
        
        for _, row in df.iterrows():
            frame = {}
            for sensor_id, body_part in sensor_map.items():
                try:
                    w = float(row[f"QuatW_{sensor_id}"])
                    x = float(row[f"QuatX_{sensor_id}"])
                    y = float(row[f"QuatY_{sensor_id}"])
                    z = float(row[f"QuatZ_{sensor_id}"])
                    frame[body_part] = [round(w, 6), round(x, 6), round(y, 6), round(z, 6)]
                except (KeyError, ValueError) as e:
                    continue
            imu_data.append(frame)
        
        # Format final
        output = {
            "IMU": imu_data,
            "EMG": [],
            "pMMG": []
        }
        
        # Sauvegarde du JSON
        print(f"   ┣ Sauvegarde en JSON: {len(imu_data)} frames")
        with open(json_output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"   ┗ Conversion terminée ✅")
        return True
    except Exception as e:
        print(f"   ┗ ERREUR pendant la conversion: {e} ❌")
        return False

class AutoModelTrainer:
    """Classe pour automatiser l'entraînement du modèle de prédiction de mouvement."""
    
    def __init__(self, csv_dir=None, json_dir=None, output_dir=None):
        """
        Initialise l'entraîneur automatique de modèle.
        
        Args:
            csv_dir: Répertoire contenant les fichiers CSV des données de capteurs
            json_dir: Répertoire où stocker les fichiers JSON convertis
            output_dir: Répertoire où sauvegarder le modèle entraîné
        """
        print("\n🔧 INITIALISATION DE L'ENTRAÎNEUR AUTOMATIQUE")
        # Configuration des chemins
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_dir = csv_dir or os.path.join(self.base_dir, 'machinelearning')
        self.json_dir = json_dir or os.path.join(self.base_dir, 'data', 'recordings')
        self.output_dir = output_dir or os.path.join(self.base_dir, 'data')
        
        print(f"   ┣ Dossier CSV: {self.csv_dir}")
        print(f"   ┣ Dossier JSON: {self.json_dir}")
        print(f"   ┣ Dossier de sortie: {self.output_dir}")
        
        # Créer les répertoires s'ils n'existent pas
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Ajouter un répertoire pour les visualisations d'entraînement
        self.viz_dir = os.path.join(self.output_dir, 'training_viz')
        os.makedirs(self.viz_dir, exist_ok=True)
        print(f"   ┣ Dossier de visualisation: {self.viz_dir}")
        
        # Configuration du mapping des capteurs
        self.sensor_map = {
            1: "torso",
            2: "forearm_l",
            3: "forearm_r",
            4: "calves_l",
            5: "calves_r",
            6: "head"
        }
        
        # Liste des parties du corps pour l'entraînement
        self.body_parts_order = [
            'head', 'neck', 'torso', 'deltoid_l', 'biceps_l', 'forearm_l', 'left_hand',
            'deltoid_r', 'biceps_r', 'forearm_r', 'right_hand', 'hip',
            'quadriceps_l', 'calves_l', 'left_foot', 'quadriceps_r', 'calves_r', 'right_foot',
            'glutes_l', 'glutes_r'
        ]
        print(f"   ┣ Configuration: {len(self.body_parts_order)} parties du corps, {len(self.sensor_map)} capteurs IMU")
        
        # Parties du corps surveillées par des IMUs
        self.monitored_parts = list(self.sensor_map.values())
        
        # État interne
        self.csv_files = []
        self.json_files = []
        self.training_data = None
        print(f"   ┗ Initialisation terminée ✅")
    
    def find_csv_files(self):
        """Recherche tous les fichiers CSV dans le répertoire spécifié."""
        print("\n🔍 RECHERCHE DES FICHIERS CSV")
        print(f"   ┣ Dossier cible: {self.csv_dir}")
        self.csv_files = []
        
        if os.path.exists(self.csv_dir):
            for filename in os.listdir(self.csv_dir):
                if filename.endswith('.csv'):
                    self.csv_files.append(os.path.join(self.csv_dir, filename))
        
        if not self.csv_files:
            print("   ┗ ATTENTION: Aucun fichier CSV trouvé. ⚠️")
        else:
            print(f"   ┣ Trouvé {len(self.csv_files)} fichiers CSV:")
            for i, file in enumerate(self.csv_files, 1):
                print(f"   ┃  {i}. {os.path.basename(file)}")
            print(f"   ┗ Recherche terminée ✅")
        
        return self.csv_files
    
    def convert_all_csv_to_json(self):
        """Convertit tous les fichiers CSV trouvés en JSON."""
        print("\n🔄 CONVERSION CSV → JSON")
        if not self.csv_files:
            print("   ┣ Aucun fichier CSV trouvé, lancement de la recherche...")
            self.find_csv_files()
            
        if not self.csv_files:
            print("   ┗ ERREUR: Aucun fichier à convertir. ❌")
            return []
        
        print(f"   ┣ Début de la conversion de {len(self.csv_files)} fichiers vers {self.json_dir}")
        self.json_files = []
        
        for i, csv_file in enumerate(self.csv_files, 1):
            base_name = os.path.basename(csv_file).split('.')[0]
            json_file = os.path.join(self.json_dir, f"{base_name}.json")
            
            print(f"\n   ┣ [{i}/{len(self.csv_files)}] Conversion de {base_name}.csv")
            try:
                success = convert_imu_csv_to_json(csv_file, json_file)
                if success:
                    self.json_files.append(json_file)
                    print(f"      ┗ Fichier JSON créé: {os.path.basename(json_file)}")
            except Exception as e:
                print(f"      ┗ ERREUR pendant la conversion: {e} ❌")
        
        print(f"\n   ┗ Conversion terminée: {len(self.json_files)}/{len(self.csv_files)} fichiers convertis ✅")
        return self.json_files
    
    def load_json_data(self):
        """Charge les données JSON pour l'entraînement."""
        print("\n📂 CHARGEMENT DES DONNÉES JSON")
        if not self.json_files and os.path.exists(self.json_dir):
            print(f"   ┣ Recherche de fichiers JSON dans {self.json_dir}")
            self.json_files = [
                os.path.join(self.json_dir, f) for f in os.listdir(self.json_dir)
                if f.endswith('.json')
            ]
        
        if not self.json_files:
            print("   ┗ ERREUR: Aucun fichier JSON trouvé pour l'entraînement. ❌")
            return None
        
        print(f"   ┣ Chargement de {len(self.json_files)} fichiers JSON")
        sequences = []
        
        for i, json_file in enumerate(self.json_files, 1):
            print(f"   ┣ [{i}/{len(self.json_files)}] Chargement de {os.path.basename(json_file)}")
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                if 'IMU' in data and len(data['IMU']) > 0:
                    sequences.append(data['IMU'])
                    print(f"      ┗ Chargé {len(data['IMU'])} frames ✅")
                else:
                    print(f"      ┗ ATTENTION: Aucune donnée IMU trouvée dans le fichier ⚠️")
            except Exception as e:
                print(f"      ┗ ERREUR lors du chargement: {e} ❌")
        
        total_frames = sum(len(s) for s in sequences)
        print(f"\n   ┗ Chargement terminé: {len(sequences)} séquences, {total_frames} frames au total ✅")
        return sequences
    
    def preprocess_data(self, sequences):
        """Prépare les données pour l'entraînement du modèle."""
        print("\n🔧 PRÉTRAITEMENT DES DONNÉES")
        if not sequences:
            print("   ┗ ERREUR: Aucune séquence à prétraiter. ❌")
            return None, None
        
        print(f"   ┣ Préparation de {sum(len(seq) for seq in sequences)} frames pour l'entraînement")
        inputs = []
        targets = []
        
        total_frames = sum(len(seq) - 1 for seq in sequences)
        processed_frames = 0
        
        print(f"   ┣ Extraction des paires d'entrée/sortie (frame actuelle → frame suivante)")
        for seq_idx, sequence in enumerate(sequences, 1):
            print(f"   ┣ Séquence {seq_idx}/{len(sequences)}: {len(sequence)} frames")
            for i in range(len(sequence) - 1):
                # Frame actuelle -> entrée
                current_frame = sequence[i]
                # Frame suivante -> cible à prédire
                next_frame = sequence[i + 1]
                
                # Préparer l'entrée: quaternions des parties surveillées
                input_data = []
                for part in self.monitored_parts:
                    if part in current_frame:
                        input_data.extend(current_frame[part])
                    else:
                        # Si la partie n'est pas dans les données, ajouter quaternion identité
                        input_data.extend([1.0, 0.0, 0.0, 0.0])
                
                # S'assurer que l'entrée a la bonne taille (6 IMUs x 4 composantes)
                if len(input_data) < 24:
                    input_data.extend([0.0] * (24 - len(input_data)))
                elif len(input_data) > 24:
                    input_data = input_data[:24]
                
                # Préparer la sortie: quaternions de toutes les parties du corps
                target_data = []
                for part in self.body_parts_order:
                    if part in next_frame:
                        target_data.extend(next_frame[part])
                    else:
                        # Si la partie n'est pas dans les données, ajouter quaternion identité
                        target_data.extend([1.0, 0.0, 0.0, 0.0])
                
                # S'assurer que la cible a la bonne taille (20 parties x 4 composantes)
                if len(target_data) < 80:
                    target_data.extend([0.0] * (80 - len(target_data)))
                elif len(target_data) > 80:
                    target_data = target_data[:80]
                
                inputs.append(input_data)
                targets.append(target_data)
                
                processed_frames += 1
                if processed_frames % 1000 == 0 or processed_frames == total_frames:
                    print(f"   ┃  Progression: {processed_frames}/{total_frames} frames ({processed_frames/total_frames*100:.1f}%)")
        
        # Convertir en tensors PyTorch
        if inputs and targets:
            print(f"   ┣ Conversion en tenseurs PyTorch...")
            inputs_tensor = torch.tensor(inputs, dtype=torch.float32)
            targets_tensor = torch.tensor(targets, dtype=torch.float32)
            print(f"   ┣ Dimensions: entrée {inputs_tensor.shape}, sortie {targets_tensor.shape}")
            
            # Garder une référence aux données
            self.training_data = (inputs_tensor, targets_tensor)
            
            print(f"   ┗ Prétraitement terminé: {inputs_tensor.shape[0]} exemples d'entraînement ✅")
            return inputs_tensor, targets_tensor
        else:
            print("   ┗ ERREUR: Aucune donnée à prétraiter. ❌")
            return None, None
    
    def train_model(self, epochs=100, batch_size=32, learning_rate=0.001, use_gpu=True, model_path=None):
        """Entraîne le modèle avec les données prétraitées."""
        print("\n🚀 ENTRAÎNEMENT DU MODÈLE")
        # Charger et prétraiter les données si nécessaire
        if self.training_data is None:
            print("   ┣ Pas de données prétraitées, chargement...")
            sequences = self.load_json_data()
            if sequences:
                print("   ┣ Prétraitement des données...")
                self.preprocess_data(sequences)
        
        if self.training_data is None:
            print("   ┗ ERREUR: Pas de données d'entraînement disponibles. ❌")
            return False
        
        inputs_tensor, targets_tensor = self.training_data
        
        # Initialiser le prédicteur de mouvement
        use_gpu = use_gpu and torch.cuda.is_available()
        device_str = "GPU" if use_gpu else "CPU"
        print(f"   ┣ Début de l'entraînement sur {device_str} ({inputs_tensor.shape[0]} exemples)")
        print(f"   ┣ Configuration: {epochs} epochs, batch size {batch_size}, learning rate {learning_rate}")
        
        print("   ┣ Initialisation du modèle...")
        predictor = MLBodyPredictor(model_path if model_path else None)
        
        # Entraîner le modèle
        print(f"   ┣ Lancement de l'entraînement ({datetime.now().strftime('%H:%M:%S')})")
        start_time = datetime.now()
        success = predictor.train_model(
            (inputs_tensor, targets_tensor), 
            epochs=epochs, 
            batch_size=batch_size, 
            learning_rate=learning_rate
        )
        
        training_time = datetime.now() - start_time
        print(f"   ┣ Entraînement terminé en {training_time.total_seconds():.1f} secondes")
        
        if success:
            # Sauvegarder le modèle
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.output_dir, f"motion_model_{timestamp}.pth")
            standard_path = os.path.join(self.output_dir, "motion_model.pth")
            # Ajouter le chemin pour training_viz
            viz_path = os.path.join(self.viz_dir, "motion_model.pth")
            
            if predictor.save_model(output_path):
                print(f"Modèle sauvegardé à {output_path}")
                
                # Copier vers les chemins standards
                import shutil
                shutil.copy2(output_path, standard_path)
                print(f"Modèle copié vers le chemin standard: {standard_path}")
                
                # Ajouter une copie dans training_viz
                shutil.copy2(output_path, viz_path)
                print(f"Modèle copié vers training_viz: {viz_path}")
                
                return True
        else:
            print("   ┗ ERREUR: Échec de l'entraînement du modèle. ❌")
        
        return False
    
    def run_full_pipeline(self, epochs=100, batch_size=32, learning_rate=0.001, use_gpu=True, model_path=None):
        """Exécute le pipeline complet: conversion, chargement, prétraitement, entraînement."""
        print("\n🔄 DÉMARRAGE DU PIPELINE COMPLET D'ENTRAÎNEMENT")
        print("=" * 80)
        
        start_time = datetime.now()
        print(f"📅 Date et heure de début: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. Convertir les données CSV en JSON
        print("\n📊 ÉTAPE 1: CONVERSION DES FICHIERS CSV EN JSON")
        self.convert_all_csv_to_json()
        
        # 2. Charger les données JSON
        print("\n📋 ÉTAPE 2: CHARGEMENT DES DONNÉES JSON")
        sequences = self.load_json_data()
        
        # 3. Prétraiter les données
        if sequences:
            print("\n🔧 ÉTAPE 3: PRÉTRAITEMENT DES DONNÉES")
            inputs, targets = self.preprocess_data(sequences)
            
            # 4. Entraîner le modèle
            if inputs is not None and targets is not None:
                print("\n🧠 ÉTAPE 4: ENTRAÎNEMENT DU MODÈLE")
                success = self.train_model(epochs, batch_size, learning_rate, use_gpu, model_path)
                
                total_time = datetime.now() - start_time
                print("\n=" * 80)
                if success:
                    print(f"\n✅ PIPELINE D'ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS")
                    print(f"⏱️  Temps total: {total_time.total_seconds():.1f} secondes ({total_time})")
                    print(f"📂 Modèle sauvegardé dans: {self.output_dir}")
                else:
                    print(f"\n❌ ÉCHEC DE L'ENTRAÎNEMENT DU MODÈLE")
                    print(f"⏱️  Temps écoulé: {total_time.total_seconds():.1f} secondes ({total_time})")
            else:
                print("\n❌ ÉCHEC DU PRÉTRAITEMENT DES DONNÉES")
        else:
            print("\n❌ AUCUNE DONNÉE DISPONIBLE POUR L'ENTRAÎNEMENT")
        
        print("\n=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Entraîne le modèle de prédiction de mouvement")
    parser.add_argument('--csv_dir', help="Répertoire contenant les fichiers CSV", default=None)
    parser.add_argument('--json_dir', help="Répertoire où stocker les JSON convertis", default=None)
    parser.add_argument('--output_dir', help="Répertoire de sortie pour le modèle", default=None)
    parser.add_argument('--epochs', type=int, help="Nombre d'epochs d'entraînement", default=100)
    parser.add_argument('--batch_size', type=int, help="Taille des batchs d'entraînement", default=32)
    parser.add_argument('--lr', type=float, help="Taux d'apprentissage", default=0.001)
    parser.add_argument('--cpu', action='store_true', help="Forcer l'utilisation du CPU (défaut: GPU si disponible)")
    parser.add_argument('--continue_training', action='store_true', 
                        help="Continuer l'entraînement à partir du modèle existant")
    parser.add_argument('--model_path', 
                        help="Chemin vers un modèle spécifique à charger (si --continue_training)")
    parser.add_argument('--fresh_start', action='store_true',
                        help="Démarrer un entraînement à partir de zéro (ignorer modèle existant)")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🤖 PROGRAMME D'ENTRAÎNEMENT AUTOMATISÉ DU MODÈLE DE PRÉDICTION DE MOUVEMENT")
    print("=" * 80)
    
    trainer = AutoModelTrainer(
        csv_dir=args.csv_dir,
        json_dir=args.json_dir,
        output_dir=args.output_dir
    )
    
    # Détecter automatiquement le modèle existant, sauf si --fresh_start est spécifié
    model_path = args.model_path
    
    if not args.fresh_start and not model_path:
        # Chercher le modèle dans les emplacements par défaut
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_paths = [
            os.path.join(base_dir, 'data', 'motion_model.pth'),
            os.path.join(base_dir, 'data', 'training_viz', 'motion_model.pth')
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                model_path = path
                print(f"\n📦 Modèle existant détecté: {path}")
                print("   ┗ L'entraînement continuera à partir de ce modèle")
                break
    
    trainer.run_full_pipeline(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        use_gpu=not args.cpu,
        model_path=model_path
    )
    
    print("\n👋 Programme terminé.")

if __name__ == "__main__":
    main()