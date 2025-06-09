"""
Script d'entraînement pour le modèle de prédiction de mouvement ML
Génère des données synthétiques et entraîne un modèle de prédiction de posture corporelle
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os
import math
import pickle
from torch.utils.data import DataLoader, TensorDataset
import matplotlib.pyplot as plt
from datetime import datetime

# Importer les classes du prédicteur
from utils.body_motion_predictor import (
    BodyMotionNetwork, 
    ImprovedBodyMotionNetwork,
    SequentialBodyMotionNetwork,
    MLBodyPredictor
)

class MotionDataGenerator:
    """Générateur de données pour l'entraînement du modèle de prédiction de mouvement"""
    
    def __init__(self):
        # Paramètres des poses
        self.num_joints = 20
        self.num_quaternions = 4
        self.sequence_length = 10
        
        # Limites pour les valeurs des quaternions
        self.quat_min = -1.0
        self.quat_max = 1.0
    
    def random_quaternion(self):
        """Génère un quaternion aléatoire normalisé"""
        quat = np.random.uniform(self.quat_min, self.quat_max, self.num_quaternions)
        norm = np.linalg.norm(quat)
        if norm > 0:
            quat /= norm
        return quat.tolist()
    
    def create_random_pose(self):
        """Crée une pose aléatoire avec des quaternions pour chaque articulation"""
        pose = {}
        for i in range(self.num_joints):
            pose[f'joint_{i+1}'] = self.random_quaternion()
        return pose
    
    def create_walking_sequence(self, num_frames):
        """Crée une séquence de marche avec des variations aléatoires"""
        sequence = []
        for _ in range(num_frames):
            pose = self.create_random_pose()
            sequence.append(pose)
        return sequence
    
    def create_training_dataset(self, num_walking_sequences=100, num_static_poses=100):
        """Crée le dataset d'entraînement complet"""
        print("🛠️  Création du dataset d'entraînement...")
        
        dataset = []
        
        # Séquences de marche
        for _ in range(num_walking_sequences):
            sequence = self.create_walking_sequence(self.sequence_length)
            dataset.append(sequence)
        
        # Postures statiques
        for _ in range(num_static_poses):
            pose = self.create_random_pose()
            dataset.append([pose] * self.sequence_length)  # Répéter la même pose
        
        print(f"✅ Dataset créé avec {len(dataset)} séquences")
        return dataset
    
    def poses_to_tensors(self, poses_data):
        """Convertit les données de poses en tenseurs PyTorch"""
        all_inputs = []
        all_targets = []
        
        for sequence in poses_data:
            for i in range(len(sequence) - 1):
                input_ = sequence[i]
                target = sequence[i + 1]
                
                # Aplatir les quaternions
                input_flat = []
                for quat in input_.values():
                    input_flat.extend(quat)
                
                target_flat = []
                for quat in target.values():
                    target_flat.extend(quat)
                
                all_inputs.append(input_flat)
                all_targets.append(target_flat)
        
        # Convertir en tenseurs
        inputs_tensor = torch.FloatTensor(all_inputs)
        targets_tensor = torch.FloatTensor(all_targets)
        
        print(f"📏 Tenseurs créés - Inputs: {inputs_tensor.shape}, Targets: {targets_tensor.shape}")
        return inputs_tensor, targets_tensor

class ModelTrainer:
    """Classe pour entraîner les modèles de prédiction de mouvement"""
    
    def __init__(self, model_type="improved"):
        self.model_type = model_type
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"🖥️  Device utilisé: {self.device}")
        
        # Dimensions du modèle
        self.input_size = 24   # 6 IMUs × 4 (quaternion WXYZ)
        self.output_size = 80  # 20 parties du corps × 4 (quaternion WXYZ)
        self.hidden_size = 128
        
        # Créer le modèle
        self.model = self._create_model()
        self.model.to(self.device)
        
        print(f"🧠 Modèle créé: {model_type}")
        print(f"📏 Architecture: {self.input_size} → {self.hidden_size} → {self.output_size}")
    
    def _create_model(self):
        """Crée le modèle selon le type spécifié"""
        if self.model_type == "improved":
            return ImprovedBodyMotionNetwork(self.input_size, self.hidden_size, self.output_size)
        elif self.model_type == "sequential":
            return SequentialBodyMotionNetwork(self.input_size, self.hidden_size, self.output_size)
        else:
            return BodyMotionNetwork(self.input_size, self.hidden_size, self.output_size)
    
    def train_model(self, train_data, val_data=None, epochs=100, batch_size=32, learning_rate=0.001):
        """Entraîne le modèle avec les données fournies"""
        print(f"🚀 Début de l'entraînement - {epochs} époques")
        
        # Préparer les données
        train_inputs, train_targets = train_data
        train_dataset = TensorDataset(train_inputs, train_targets)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        # Préparer la validation si fournie
        val_loader = None
        if val_data:
            val_inputs, val_targets = val_data
            val_dataset = TensorDataset(val_inputs, val_targets)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Optimiseur et fonction de perte
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate, weight_decay=1e-5)
        criterion = nn.MSELoss()
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
        
        # Historique d'entraînement
        train_losses = []
        val_losses = []
        best_val_loss = float('inf')
        
        self.model.train()
        
        for epoch in range(epochs):
            epoch_train_loss = 0.0
            num_batches = 0
            
            # Phase d'entraînement
            for batch_inputs, batch_targets in train_loader:
                batch_inputs = batch_inputs.to(self.device)
                batch_targets = batch_targets.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(batch_inputs)
                loss = criterion(outputs, batch_targets)
                loss.backward()
                optimizer.step()
                
                epoch_train_loss += loss.item()
                num_batches += 1
            
            avg_train_loss = epoch_train_loss / num_batches
            train_losses.append(avg_train_loss)
            
            # Phase de validation
            if val_loader:
                self.model.eval()
                epoch_val_loss = 0.0
                with torch.no_grad():
                    for batch_inputs, batch_targets in val_loader:
                        batch_inputs = batch_inputs.to(self.device)
                        batch_targets = batch_targets.to(self.device)
                        
                        outputs = self.model(batch_inputs)
                        loss = criterion(outputs, batch_targets)
                        epoch_val_loss += loss.item()
                
                avg_val_loss = epoch_val_loss / len(val_loader)
                val_losses.append(avg_val_loss)
                
                # Scheduler
                scheduler.step(avg_val_loss)
                
                print(f"Epoch [{epoch+1}/{epochs}] - "
                      f"Train Loss: {avg_train_loss:.6f}, "
                      f"Val Loss: {avg_val_loss:.6f}")
                
                # Sauvegarder le meilleur modèle
                if avg_val_loss < best_val_loss:
                    best_val_loss = avg_val_loss
                    self._save_best_model()
            else:
                print(f"Epoch [{epoch+1}/{epochs}] - Train Loss: {avg_train_loss:.6f}")
        
        print(f"✅ Entraînement terminé! Meilleure validation: {best_val_loss:.6f}")
        
        return {
            'train_losses': train_losses,
            'val_losses': val_losses,
            'best_val_loss': best_val_loss
        }
    
    def _save_best_model(self):
        """Sauvegarde le meilleur modèle"""
        model_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(model_dir, exist_ok=True)
        
        model_path = os.path.join(model_dir, 'motion_model.pth')
        torch.save(self.model.state_dict(), model_path)
        print(f"💾 Meilleur modèle sauvegardé: {model_path}")

def main():
    """Fonction principale d'entraînement"""
    print("🎯 === Entraînement du Modèle de Prédiction de Mouvement ===")
    
    # Créer le générateur de données
    data_generator = MotionDataGenerator()
    
    # Générer le dataset
    poses_data = data_generator.create_training_dataset(
        num_walking_sequences=50,
        num_static_poses=500
    )
    
    # Convertir en tenseurs
    inputs, targets = data_generator.poses_to_tensors(poses_data)
    
    # Division train/validation
    train_size = int(0.8 * len(inputs))
    train_inputs = inputs[:train_size]
    train_targets = targets[:train_size]
    val_inputs = inputs[train_size:]
    val_targets = targets[train_size:]
    
    print(f"📊 Dataset divisé - Train: {len(train_inputs)}, Validation: {len(val_inputs)}")
    
    # Créer et entraîner le modèle
    trainer = ModelTrainer("improved")
    
    # Entraînement
    history = trainer.train_model(
        train_data=(train_inputs, train_targets),
        val_data=(val_inputs, val_targets),
        epochs=50,
        batch_size=32,
        learning_rate=0.001
    )
    
    print("🎉 Entraînement terminé avec succès!")
    print(f"📈 Perte finale: {history['best_val_loss']:.6f}")

if __name__ == "__main__":
    main()