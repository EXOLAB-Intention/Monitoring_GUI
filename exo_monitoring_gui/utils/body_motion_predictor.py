import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import os

class SimpleBodyPredictor:
    """Un prédicteur simple pour le mouvement du corps basé sur les parties avec des IMUs"""
    
    def __init__(self, model_path=None):
        self.model_path = model_path
        # Définir les relations entre les parties du corps
        self.body_relations = {
            # La tête suit le cou
            'head': ['neck'],
            # Les mains suivent les avant-bras
            'left_hand': ['forearm_l'],
            'right_hand': ['forearm_r'],
            # Les avant-bras suivent les biceps
            'forearm_l': ['biceps_l'],
            'forearm_r': ['biceps_r'],
            # Les biceps suivent les deltoïdes
            'biceps_l': ['deltoid_l', 'torso'],
            'biceps_r': ['deltoid_r', 'torso'],
            # Les deltoïdes suivent le torse
            'deltoid_l': ['torso'],
            'deltoid_r': ['torso'],
            # Les muscles du dos et de la poitrine suivent le torse
            'dorsalis_major_l': ['torso'],
            'dorsalis_major_r': ['torso'],
            'pectorals_l': ['torso'],
            'pectorals_r': ['torso'],
            # Le cou suit le torse
            'neck': ['torso'],
            # Les jambes suivent les hanches
            'quadriceps_l': ['hip'],
            'quadriceps_r': ['hip'],
            'ishcio_hamstrings_l': ['hip'],
            'ishcio_hamstrings_r': ['hip'],
            'glutes_l': ['hip'],
            'glutes_r': ['hip'],
            # Les mollets suivent les jambes
            'calves_l': ['quadriceps_l', 'ishcio_hamstrings_l'],
            'calves_r': ['quadriceps_r', 'ishcio_hamstrings_r'],
            # Les pieds suivent les mollets
            'left_foot': ['calves_l'],
            'right_foot': ['calves_r'],
            # Les hanches suivent le torse
            'hip': ['torso']
        }
        
        # Chargement d'un modèle ML si disponible
        self.ml_model = None
        if model_path and os.path.exists(model_path):
            try:
                self.ml_model = torch.load(model_path)
                self.ml_model.eval()
                print(f"[INFO] Modèle de prédiction chargé: {model_path}")
            except Exception as e:
                print(f"[WARNING] Impossible de charger le modèle ML: {e}")
    
    def predict_from_partial_state(self, imu_data):
        """
        Prédit les positions des parties du corps sans IMU à partir des parties avec IMU.
        
        Args:
            imu_data: Dictionnaire {part_name: {'pos': np.array, 'rot': np.array}}
                pour les parties avec des IMUs
                
        Returns:
            Dictionnaire des positions/rotations prédites pour les parties sans IMU
        """
        # Si aucune donnée IMU n'est disponible, retourner un dict vide
        if not imu_data:
            return {}
            
        # Essayer d'abord le modèle ML si disponible
        if self.ml_model:
            try:
                ml_predictions = self._predict_with_ml(imu_data)
                if ml_predictions:
                    return ml_predictions
            except Exception as e:
                print(f"[WARNING] Erreur de prédiction ML: {e}, utilisation du fallback")
        
        # Fallback: Utiliser l'algorithme de propagation simple
        predictions = {}
        
        # Pour chaque partie du corps dans les relations
        for part_name, related_parts in self.body_relations.items():
            # Si la partie a déjà un IMU, on l'ignore
            if part_name in imu_data:
                continue
                
            # Chercher des parties liées qui ont des IMUs
            available_related = [p for p in related_parts if p in imu_data]
            
            if available_related:
                # Moyenne des rotations des parties liées
                rot_sum = np.zeros(4)
                for rel_part in available_related:
                    rot_sum += imu_data[rel_part]['rot']
                
                avg_rot = rot_sum / len(available_related)
                predictions[part_name] = {'rot': avg_rot}
                
        return predictions
    
    def _predict_with_ml(self, imu_data):
        """Utilise le modèle ML pour prédire les mouvements."""
        if not self.ml_model:
            return {}
            
        try:
            # Préparation des données d'entrée
            input_features = []
            
            # Parties du corps que nous attendons en entrée du modèle
            expected_parts = ['torso', 'head', 'left_hand', 'right_hand', 
                              'left_foot', 'right_foot']
            
            # Convertir les données IMU en vecteurs de caractéristiques
            for part in expected_parts:
                if part in imu_data:
                    # Ajouter la rotation quaternion [w,x,y,z]
                    input_features.extend(imu_data[part]['rot'])
                else:
                    # Si pas de données, ajouter des zéros
                    input_features.extend([0.0, 0.0, 0.0, 0.0])
            
            # Convertir en tenseur PyTorch
            input_tensor = torch.tensor(input_features, dtype=torch.float32).unsqueeze(0)
            
            # Prédiction
            with torch.no_grad():
                output = self.ml_model(input_tensor)
            
            # Traiter les résultats
            predictions = {}
            output = output.squeeze(0).numpy()
            
            # Mapper les sorties aux parties du corps
            # Le format de sortie dépend de l'architecture du modèle
            idx = 0
            all_parts = list(self.body_relations.keys())
            
            for part_name in all_parts:
                if part_name not in imu_data:  # Uniquement les parties sans IMU
                    # Chaque partie a une rotation quaternion [w,x,y,z]
                    if idx + 4 <= len(output):
                        rot = output[idx:idx+4]
                        # Normaliser le quaternion
                        norm = np.linalg.norm(rot)
                        if norm > 1e-6:  # Éviter division par zéro
                            rot = rot / norm
                        predictions[part_name] = {'rot': rot}
                        idx += 4
            
            return predictions
        except Exception as e:
            print(f"[ERROR] Erreur lors de la prédiction ML: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
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
        imu_data = {k: v for k, v in body_parts.items() if k in monitored_parts}
        predictions = self.predict_from_partial_state(imu_data)
        
        # Copier les données d'entrée pour ne pas les modifier directement
        updated_body_parts = {k: {
            'pos': v['pos'].copy(), 
            'rot': v['rot'].copy()
        } for k, v in body_parts.items()}
        
        # Mettre à jour les parties non surveillées avec les prédictions
        for part_name, pred in predictions.items():
            if part_name in updated_body_parts:
                updated_body_parts[part_name]['rot'] = pred['rot']
        
        return updated_body_parts


class ImprovedBodyMotionNetwork(nn.Module):
    """Version améliorée du réseau pour de meilleures prédictions."""
    def __init__(self, input_size, hidden_size, output_size):
        super(ImprovedBodyMotionNetwork, self).__init__()
        # Architecture plus profonde
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.layer2 = nn.Linear(hidden_size, hidden_size*2)
        self.bn2 = nn.BatchNorm1d(hidden_size*2)
        self.layer3 = nn.Linear(hidden_size*2, hidden_size)
        self.bn3 = nn.BatchNorm1d(hidden_size)
        self.layer4 = nn.Linear(hidden_size, output_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)  # Augmenter légèrement le dropout
        
    def forward(self, x):
        # Flux amélioré avec normalisation par lots
        x = self.layer1(x)
        if x.shape[0] > 1:  # BatchNorm1d nécessite plus d'un exemple
            x = self.bn1(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer2(x)
        if x.shape[0] > 1:
            x = self.bn2(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer3(x)
        if x.shape[0] > 1:
            x = self.bn3(x)
        x = self.relu(x)
        
        x = self.layer4(x)
        return x


class SequentialBodyMotionNetwork(nn.Module):
    """Réseau LSTM pour modéliser les séquences temporelles de mouvements."""
    def __init__(self, input_size, hidden_size, output_size, num_layers=2):
        super(SequentialBodyMotionNetwork, self).__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        # x shape: [batch_size, sequence_length, input_size]
        lstm_out, _ = self.lstm(x)
        # Prendre seulement la dernière sortie de la séquence
        output = self.fc(lstm_out[:, -1, :])
        return output


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
        return True  # Retourne True pour indiquer que l'entraînement s'est bien déroulé
    
    def save_model(self, path):
        """Sauvegarde le modèle entraîné sur disque."""
        torch.save(self.model.state_dict(), path)
        print(f"Modèle sauvegardé à {path}")
        return True


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