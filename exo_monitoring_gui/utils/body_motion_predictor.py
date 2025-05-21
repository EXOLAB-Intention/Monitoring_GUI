import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import os
import pickle
import math

class SimpleBodyPredictor:
    """
    Classe de prédiction simple basée sur des règles biomécaniques
    pour générer des mouvements cohérents des parties du corps sans capteurs.
    """
    def __init__(self):
        self.joint_relations = {
            # Relations entre articulations (parent -> enfants)
            'torso': ['neck', 'deltoid_l', 'deltoid_r', 'hip'],
            'neck': ['head'],
            'deltoid_l': ['biceps_l', 'pectorals_l'],
            'biceps_l': ['forearm_l'],
            'forearm_l': ['left_hand'],
            'deltoid_r': ['biceps_r', 'pectorals_r'],
            'biceps_r': ['forearm_r'],
            'forearm_r': ['right_hand'],
            'hip': ['quadriceps_l', 'quadriceps_r', 'glutes_l', 'glutes_r'],
            'quadriceps_l': ['calves_l', 'ishcio_hamstrings_l'],
            'quadriceps_r': ['calves_r', 'ishcio_hamstrings_r'],
            'calves_l': ['left_foot'],
            'calves_r': ['right_foot']
        }
        
        # Facteurs d'influence pour la propagation du mouvement
        self.influence_factors = {
            'torso': 1.0,
            'neck': 0.8,
            'head': 0.5,
            'deltoid_l': 0.9,
            'biceps_l': 0.8,
            'forearm_l': 0.7,
            'left_hand': 0.5,
            'deltoid_r': 0.9,
            'biceps_r': 0.8,
            'forearm_r': 0.7,
            'right_hand': 0.5,
            'hip': 0.9,
            'quadriceps_l': 0.8,
            'calves_l': 0.7,
            'left_foot': 0.5,
            'quadriceps_r': 0.8,
            'calves_r': 0.7,
            'right_foot': 0.5,
            'glutes_l': 0.6,
            'glutes_r': 0.6,
            'ishcio_hamstrings_l': 0.6,
            'ishcio_hamstrings_r': 0.6,
            'pectorals_l': 0.6,
            'pectorals_r': 0.6,
            'dorsalis_major_l': 0.6,
            'dorsalis_major_r': 0.6
        }
        
        # Contraintes angulaires pour éviter les mouvements impossibles
        self.joint_constraints = {
            'neck': {'x': (-30, 60), 'y': (-70, 70), 'z': (-50, 50)},
            'elbow': {'x': (0, 160)},  # Pour forearm_l et forearm_r
            'knee': {'x': (0, 160)},   # Pour calves_l et calves_r
            'ankle': {'x': (-20, 45)}, # Pour left_foot et right_foot
            'wrist': {'x': (-80, 80), 'y': (-20, 35), 'z': (-90, 90)}, # Pour les mains
            'shoulder': {'x': (-180, 60), 'y': (-90, 180), 'z': (-90, 90)}, # Pour deltoid_l et deltoid_r
            'hip_joint': {'x': (-120, 45), 'y': (-45, 45), 'z': (-30, 90)} # Pour quadriceps_l et quadriceps_r
        }
        
        # Cache pour mémoriser les mouvements récents
        self.movement_history = {}
        self.smoothing_factor = 0.3  # Pour lisser les mouvements
        
    def quaternion_to_euler(self, q):
        """Convertit un quaternion en angles d'Euler (degrés)"""
        w, x, y, z = q
        
        # Roll (rotation autour de X)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))
        
        # Pitch (rotation autour de Y)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.degrees(math.copysign(math.pi / 2, sinp))
        else:
            pitch = math.degrees(math.asin(sinp))
        
        # Yaw (rotation autour de Z)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))
        
        return np.array([roll, pitch, yaw])
    
    def euler_to_quaternion(self, euler_angles):
        """Convertit des angles d'Euler en quaternion"""
        roll, pitch, yaw = np.radians(euler_angles)
        
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        
        return np.array([w, x, y, z])
    
    def predict_joint_movement(self, body_parts, monitored_parts, is_walking=False):
        """
        Prédit les mouvements des articulations non surveillées en fonction des
        capteurs présents et du mouvement des articulations surveillées.
        
        Args:
            body_parts: Dictionnaire des parties du corps avec leurs positions et rotations
            monitored_parts: Liste des noms des parties surveillées par des capteurs
            is_walking: Booléen indiquant si le mode marche est activé
            
        Returns:
            Dictionnaire mis à jour avec les rotations prédites pour toutes les parties
        """
        # Copier les données d'entrée pour ne pas les modifier directement
        updated_body_parts = {k: {
            'pos': v['pos'].copy(), 
            'rot': v['rot'].copy()
        } for k, v in body_parts.items()}
        
        # Si l'animation de marche est active, ne pas interférer
        if is_walking:
            return updated_body_parts
            
        # Étape 1: Extraire les données capteurs comme base de prédiction
        sensor_data = {}
        for part_name in monitored_parts:
            if part_name in body_parts:
                # Convertir quaternion en angles d'Euler pour la prédiction
                quat = body_parts[part_name]['rot']
                euler = self.quaternion_to_euler(quat)
                sensor_data[part_name] = euler
        
        # Étape 2: Propager les mouvements aux articulations non surveillées
        # Effectuer plusieurs passes pour propager l'influence
        for _ in range(3):  # 3 passes de propagation
            for parent, children in self.joint_relations.items():
                # Si le parent est surveillé, propager son mouvement à ses enfants
                if parent in sensor_data:
                    parent_euler = sensor_data[parent]
                    parent_influence = self.influence_factors[parent]
                    
                    for child in children:
                        if child not in monitored_parts:
                            # Ne mettre à jour que si l'enfant n'est pas déjà surveillé
                            if child not in sensor_data:
                                # Initialiser les données de cet enfant ou obtenir sa valeur actuelle
                                child_euler = sensor_data.get(child, np.zeros(3))
                                
                                # Calculer le nouveau mouvement (avec un facteur d'influence)
                                child_influence = self.influence_factors[child]
                                influence_factor = parent_influence * child_influence
                                
                                # Appliquer l'influence du parent en tenant compte de l'historique
                                updated_euler = child_euler * (1 - influence_factor) + parent_euler * influence_factor
                                
                                # Appliquer les contraintes appropriées
                                updated_euler = self._apply_constraints(child, updated_euler)
                                
                                # Mettre à jour les données de capteur pour les prochaines passes
                                sensor_data[child] = updated_euler
            
        # Étape 3: Appliquer le lissage temporel en utilisant l'historique
        for part_name, euler in sensor_data.items():
            if part_name not in monitored_parts:
                if part_name in self.movement_history:
                    # Lisser le mouvement avec les valeurs précédentes
                    smoothed_euler = self.movement_history[part_name] * self.smoothing_factor + euler * (1 - self.smoothing_factor)
                    euler = smoothed_euler
                
                # Mettre à jour l'historique
                self.movement_history[part_name] = euler
                
                # Convertir en quaternion et mettre à jour la partie du corps
                quat = self.euler_to_quaternion(euler)
                updated_body_parts[part_name]['rot'] = quat
        
        return updated_body_parts
    
    def _apply_constraints(self, part_name, euler_angles):
        """Applique des contraintes biomécaniques aux angles d'Euler."""
        constrained_angles = euler_angles.copy()
        
        # Appliquer le type de contrainte approprié selon la partie du corps
        constraint_type = None
        if part_name in ['forearm_l', 'forearm_r']:
            constraint_type = 'elbow'
        elif part_name in ['calves_l', 'calves_r']:
            constraint_type = 'knee'
        elif part_name in ['left_foot', 'right_foot']:
            constraint_type = 'ankle'
        elif part_name in ['left_hand', 'right_hand']:
            constraint_type = 'wrist'
        elif part_name in ['deltoid_l', 'deltoid_r']:
            constraint_type = 'shoulder'
        elif part_name in ['quadriceps_l', 'quadriceps_r']:
            constraint_type = 'hip_joint'
        elif part_name == 'neck':
            constraint_type = 'neck'
        
        # Appliquer les contraintes si un type approprié a été trouvé
        if constraint_type and constraint_type in self.joint_constraints:
            constraints = self.joint_constraints[constraint_type]
            
            for axis, (min_val, max_val) in constraints.items():
                axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
                if axis_idx < len(constrained_angles):
                    angle = constrained_angles[axis_idx]
                    constrained_angles[axis_idx] = max(min_val, min(max_val, angle))
        
        return constrained_angles


class BodyMotionNetwork(nn.Module):
    """
    Réseau de neurones pour prédire les mouvements corporels à partir 
    d'un nombre limité de capteurs IMU.
    """
    def __init__(self, input_size, hidden_size, output_size):
        super(BodyMotionNetwork, self).__init__()
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.layer2 = nn.Linear(hidden_size, hidden_size)
        self.layer3 = nn.Linear(hidden_size, output_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        x = self.relu(self.layer1(x))
        x = self.dropout(x)
        x = self.relu(self.layer2(x))
        x = self.layer3(x)
        return x


class MLBodyPredictor:
    """
    Prédicteur de mouvement basé sur un modèle de réseau de neurones.
    Cette classe nécessite un entraînement préalable ou un modèle pré-entraîné.
    """
    def __init__(self, model_path=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Configuration du modèle
        self.input_size = 24  # 6 IMUs x 4 (quaternion WXYZ)
        self.hidden_size = 128
        self.output_size = 80  # 20 articulations x 4 (quaternion WXYZ)
        
        # Initialiser le modèle
        self.model = BodyMotionNetwork(self.input_size, self.hidden_size, self.output_size).to(self.device)
        
        # Tenter de charger un modèle pré-entraîné
        if model_path and os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            self.model_loaded = True
            print(f"Modèle chargé depuis {model_path}")
        else:
            self.model_loaded = False
            print("Aucun modèle pré-entraîné trouvé. Utilisant la prédiction par règles.")
        
        # Fallback au prédicteur simple si pas de modèle ML
        self.simple_predictor = SimpleBodyPredictor()
        
        # Mapper les noms des parties du corps aux indices du tenseur de sortie
        self.body_part_indices = {
            'head': 0,
            'neck': 1,
            'torso': 2,
            'deltoid_l': 3,
            'biceps_l': 4,
            'forearm_l': 5,
            'left_hand': 6,
            'deltoid_r': 7,
            'biceps_r': 8,
            'forearm_r': 9,
            'right_hand': 10,
            'hip': 11,
            'quadriceps_l': 12,
            'calves_l': 13,
            'left_foot': 14,
            'quadriceps_r': 15,
            'calves_r': 16,
            'right_foot': 17,
            'glutes_l': 18,
            'glutes_r': 19
        }
    
    def predict_joint_movement(self, body_parts, monitored_parts, is_walking=False):
        """
        Prédit les mouvements des articulations non surveillées.
        Utilise le modèle ML si disponible, sinon replie sur le simple predictor.
        
        Args:
            body_parts: Dictionnaire des parties du corps avec leurs positions et rotations
            monitored_parts: Liste des noms des parties surveillées par des capteurs
            is_walking: Booléen indiquant si le mode marche est activé
            
        Returns:
            Dictionnaire mis à jour avec les rotations prédites pour toutes les parties
        """
        if is_walking or not self.model_loaded:
            # Si l'animation de marche est active ou si aucun modèle n'est chargé,
            # utiliser le prédicteur simple
            return self.simple_predictor.predict_joint_movement(body_parts, monitored_parts, is_walking)
        
        # Préparer les données d'entrée pour le modèle
        input_data = torch.zeros(self.input_size, dtype=torch.float32, device=self.device)
        
        # Remplir le tenseur d'entrée avec les données des capteurs disponibles
        imu_count = 0
        for part_name in monitored_parts:
            if part_name in body_parts and imu_count < 6:  # Limité à 6 IMUs
                quat = body_parts[part_name]['rot']
                input_idx = imu_count * 4  # 4 valeurs quaternion par IMU
                input_data[input_idx:input_idx+4] = torch.tensor(quat, dtype=torch.float32, device=self.device)
                imu_count += 1
        
        # Prédire avec le modèle ML
        with torch.no_grad():
            output = self.model(input_data.unsqueeze(0)).squeeze(0)
        
        # Copier les données d'entrée pour ne pas les modifier directement
        updated_body_parts = {k: {
            'pos': v['pos'].copy(), 
            'rot': v['rot'].copy()
        } for k, v in body_parts.items()}
        
        # Mettre à jour les parties non surveillées avec les prédictions
        for part_name, idx in self.body_part_indices.items():
            if part_name not in monitored_parts:
                output_idx = idx * 4  # 4 valeurs quaternion par partie
                quat = output[output_idx:output_idx+4].cpu().numpy()
                # Normaliser le quaternion prédit
                quat_norm = np.linalg.norm(quat)
                if quat_norm > 0:
                    quat = quat / quat_norm
                updated_body_parts[part_name]['rot'] = quat
        
        return updated_body_parts
    
    def train_model(self, training_data, epochs=100, batch_size=32, learning_rate=0.001):
        """
        Entraîne le modèle avec des données de mouvement.
        
        Args:
            training_data: Tuple (inputs, targets) pour l'entraînement
            epochs: Nombre d'époques d'entraînement
            batch_size: Taille des batchs d'entraînement
            learning_rate: Taux d'apprentissage
            
        Returns:
            Historique des pertes d'entraînement
        """
        inputs, targets = training_data
        dataset = torch.utils.data.TensorDataset(inputs, targets)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        
        self.model.train()
        losses = []
        
        for epoch in range(epochs):
            epoch_loss = 0
            for batch_inputs, batch_targets in dataloader:
                batch_inputs = batch_inputs.to(self.device)
                batch_targets = batch_targets.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(batch_inputs)
                loss = criterion(outputs, batch_targets)
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(dataloader)
            losses.append(avg_loss)
            print(f"Époque {epoch+1}/{epochs}, Perte: {avg_loss:.6f}")
        
        # Marquer le modèle comme étant chargé
        self.model_loaded = True
        return losses
    
    def save_model(self, path):
        """Sauvegarde le modèle entraîné sur disque."""
        torch.save(self.model.state_dict(), path)
        print(f"Modèle sauvegardé à {path}")


class MotionPredictorFactory:
    """
    Factory pour créer et gérer les différents types de prédicteurs de mouvement.
    """
    @staticmethod
    def create_predictor(predictor_type="simple", model_path=None):
        """
        Crée une instance du prédicteur spécifié.
        
        Args:
            predictor_type: Type de prédicteur ("simple" ou "ml")
            model_path: Chemin vers un modèle pré-entraîné (pour "ml")
            
        Returns:
            Une instance du prédicteur demandé
        """
        if predictor_type.lower() == "ml":
            return MLBodyPredictor(model_path)
        else:
            return SimpleBodyPredictor()
