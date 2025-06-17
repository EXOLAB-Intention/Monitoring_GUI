import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import os

class SimpleBodyPredictor:
    """A simple predictor for body movement based on parts with IMUs."""
    
    def __init__(self, model_path=None):
        self.model_path = model_path
        # Define relationships between body parts
        self.body_relations = {
            # The head follows the neck
            'head': ['neck'],
            # Hands follow the forearms
            'left_hand': ['forearm_l'],
            'right_hand': ['forearm_r'],
            # Forearms follow the biceps
            'forearm_l': ['biceps_l'],
            'forearm_r': ['biceps_r'],
            # Biceps follow the deltoids
            'biceps_l': ['deltoid_l', 'torso'],
            'biceps_r': ['deltoid_r', 'torso'],
            # Deltoids follow the torso
            'deltoid_l': ['torso'],
            'deltoid_r': ['torso'],
            # Back and chest muscles follow the torso
            'dorsalis_major_l': ['torso'],
            'dorsalis_major_r': ['torso'],
            'pectorals_l': ['torso'],
            'pectorals_r': ['torso'],
            # The neck follows the torso
            'neck': ['torso'],
            # Legs follow the hips
            'quadriceps_l': ['hip'],
            'quadriceps_r': ['hip'],
            'ishcio_hamstrings_l': ['hip'],
            'ishcio_hamstrings_r': ['hip'],
            'glutes_l': ['hip'],
            'glutes_r': ['hip'],
            # Calves follow the legs
            'calves_l': ['quadriceps_l', 'ishcio_hamstrings_l'],
            'calves_r': ['quadriceps_r', 'ishcio_hamstrings_r'],
            # Feet follow the calves
            'left_foot': ['calves_l'],
            'right_foot': ['calves_r'],
            # Hips follow the torso
            'hip': ['torso']
        }
        
        # Load an ML model if available
        self.ml_model = None
        if model_path and os.path.exists(model_path):
            try:
                self.ml_model = torch.load(model_path)
                self.ml_model.eval()
                print(f"[INFO] Prediction model loaded: {model_path}")
            except Exception as e:
                print(f"[WARNING] Unable to load ML model: {e}")
    
    def predict_from_partial_state(self, imu_data):
        """
        Predicts the positions of body parts without IMUs from those with IMUs.
        
        Args:
            imu_data: Dictionary {part_name: {'pos': np.array, 'rot': np.array}}
                for parts with IMUs
                
        Returns:
            Dictionary of predicted positions/rotations for parts without IMUs
        """
        # If no IMU data is available, return an empty dict
        if not imu_data:
            return {}
            
        # Try the ML model first if available
        if self.ml_model:
            try:
                ml_predictions = self._predict_with_ml(imu_data)
                if ml_predictions:
                    return ml_predictions
            except Exception as e:
                print(f"[WARNING] ML prediction error: {e}, using fallback")
        
        # Fallback: Use the simple propagation algorithm
        predictions = {}
        
        # For each body part in the relations
        for part_name, related_parts in self.body_relations.items():
            # If the part already has an IMU, skip it
            if part_name in imu_data:
                continue
                
            # Look for related parts that have IMUs
            available_related = [p for p in related_parts if p in imu_data]
            
            if available_related:
                # Average the rotations of the related parts
                rot_sum = np.zeros(4)
                for rel_part in available_related:
                    rot_sum += imu_data[rel_part]['rot']
                
                avg_rot = rot_sum / len(available_related)
                predictions[part_name] = {'rot': avg_rot}
                
        return predictions
    
    def _predict_with_ml(self, imu_data):
        """Uses the ML model to predict movements."""
        if not self.ml_model:
            return {}
            
        try:
            # Prepare input data
            input_features = []
            
            # Body parts expected as input to the model
            expected_parts = ['torso', 'head', 'left_hand', 'right_hand', 
                              'left_foot', 'right_foot']
            
            # Convert IMU data to feature vectors
            for part in expected_parts:
                if part in imu_data:
                    # Add quaternion rotation [w,x,y,z]
                    input_features.extend(imu_data[part]['rot'])
                else:
                    # If no data, add zeros
                    input_features.extend([0.0, 0.0, 0.0, 0.0])
            
            # Convert to PyTorch tensor
            input_tensor = torch.tensor(input_features, dtype=torch.float32).unsqueeze(0)
            
            # Prediction
            with torch.no_grad():
                output = self.ml_model(input_tensor)
            
            # Process results
            predictions = {}
            output = output.squeeze(0).numpy()
            
            # Map outputs to body parts
            # Output format depends on model architecture
            idx = 0
            all_parts = list(self.body_relations.keys())
            
            for part_name in all_parts:
                if part_name not in imu_data:  # Only parts without IMUs
                    # Each part has a quaternion rotation [w,x,y,z]
                    if idx + 4 <= len(output):
                        rot = output[idx:idx+4]
                        # Normalize quaternion
                        norm = np.linalg.norm(rot)
                        if norm > 1e-6:  # Avoid division by zero
                            rot = rot / norm
                        predictions[part_name] = {'rot': rot}
                        idx += 4
            
            return predictions
        except Exception as e:
            print(f"[ERROR] Error during ML prediction: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def predict_joint_movement(self, body_parts, monitored_parts, is_walking=False):
        """
        Predicts the movements of unmonitored joints.
        Uses the ML model if available, otherwise falls back to the simple predictor.
        
        Args:
            body_parts: Dictionary of body parts with their positions and rotations
            monitored_parts: List of names of parts monitored by sensors
            is_walking: Boolean indicating if walking mode is enabled
            
        Returns:
            Updated dictionary with predicted rotations for all parts
        """
        imu_data = {k: v for k, v in body_parts.items() if k in monitored_parts}
        predictions = self.predict_from_partial_state(imu_data)
        
        # Copy input data to avoid modifying directly
        updated_body_parts = {k: {
            'pos': v['pos'].copy(), 
            'rot': v['rot'].copy()
        } for k, v in body_parts.items()}
        
        # Update unmonitored parts with predictions
        for part_name, pred in predictions.items():
            if part_name in updated_body_parts:
                updated_body_parts[part_name]['rot'] = pred['rot']
        
        return updated_body_parts


class ImprovedBodyMotionNetwork(nn.Module):
    """Improved version of the network for better predictions."""
    def __init__(self, input_size, hidden_size, output_size):
        super(ImprovedBodyMotionNetwork, self).__init__()
        # Deeper architecture
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.layer2 = nn.Linear(hidden_size, hidden_size*2)
        self.bn2 = nn.BatchNorm1d(hidden_size*2)
        self.layer3 = nn.Linear(hidden_size*2, hidden_size)
        self.bn3 = nn.BatchNorm1d(hidden_size)
        self.layer4 = nn.Linear(hidden_size, output_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)  # Slightly increased dropout
        
    def forward(self, x):
        # Improved flow with batch normalization
        x = self.layer1(x)
        if x.shape[0] > 1:  # BatchNorm1d requires more than one example
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
    """LSTM network to model temporal movement sequences."""
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
        # Take only the last output of the sequence
        output = self.fc(lstm_out[:, -1, :])
        return output


class BodyMotionNetwork(nn.Module):
    """
    Neural network to predict body movements from
    a limited number of IMU sensors.
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
    Movement predictor based on a neural network model.
    This class requires prior training or a pre-trained model.
    """
    def __init__(self, model_path=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Model configuration
        self.input_size = 24  # 6 IMUs x 4 (quaternion WXYZ)
        self.hidden_size = 128
        self.output_size = 80  # 20 joints x 4 (quaternion WXYZ)
        
        # Initialize the model
        self.model = BodyMotionNetwork(self.input_size, self.hidden_size, self.output_size).to(self.device)
        
        # Try to load a pre-trained model
        if model_path and os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            self.model_loaded = True
        else:
            self.model_loaded = False
            print("No pre-trained model found. Using rule-based prediction.")
        # Fallback to simple predictor if no ML model
        self.simple_predictor = SimpleBodyPredictor()
        
        # Map body part names to output tensor indices
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
        Predicts the movements of unmonitored joints.
        Uses the ML model if available, otherwise falls back to the simple predictor.
        
        Args:
            body_parts: Dictionary of body parts with their positions and rotations
            monitored_parts: List of names of parts monitored by sensors
            is_walking: Boolean indicating if walking mode is enabled
            
        Returns:
            Updated dictionary with predicted rotations for all parts
        """
        if is_walking or not self.model_loaded:
            # If walking animation is active or no model is loaded,
            # use the simple predictor
            return self.simple_predictor.predict_joint_movement(body_parts, monitored_parts, is_walking)
        
        # Prepare input data for the model
        input_data = torch.zeros(self.input_size, dtype=torch.float32, device=self.device)
        
        # Fill the input tensor with available sensor data
        imu_count = 0
        for part_name in monitored_parts:
            if part_name in body_parts and imu_count < 6:  # Limited to 6 IMUs
                quat = body_parts[part_name]['rot']
                input_idx = imu_count * 4  # 4 quaternion values per IMU
                input_data[input_idx:input_idx+4] = torch.tensor(quat, dtype=torch.float32, device=self.device)
                imu_count += 1
        
        # Predict with the ML model
        with torch.no_grad():
            output = self.model(input_data.unsqueeze(0)).squeeze(0)
        
        # Copy input data to avoid modifying directly
        updated_body_parts = {k: {
            'pos': v['pos'].copy(), 
            'rot': v['rot'].copy()
        } for k, v in body_parts.items()}
        
        # Update unmonitored parts with predictions
        for part_name, idx in self.body_part_indices.items():
            if part_name not in monitored_parts:
                output_idx = idx * 4  # 4 quaternion values per part
                quat = output[output_idx:output_idx+4].cpu().numpy()
                # Normalize the predicted quaternion
                quat_norm = np.linalg.norm(quat)
                if quat_norm > 0:
                    quat = quat / quat_norm
                updated_body_parts[part_name]['rot'] = quat
        
        return updated_body_parts
    
    def train_model(self, training_data, epochs=100, batch_size=32, learning_rate=0.001):
        """
        Trains the model with movement data.
        
        Args:
            training_data: Tuple (inputs, targets) for training
            epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            
        Returns:
            Training loss history
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
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}")
        
        # Mark the model as loaded
        self.model_loaded = True
        return True  # Return True to indicate training was successful
    
    def save_model(self, path):
        """Saves the trained model to disk."""
        torch.save(self.model.state_dict(), path)
        print(f"Model saved to {path}")
        return True


class MotionPredictorFactory:
    """
    Factory to create and manage different types of motion predictors.
    """
    @staticmethod
    def create_predictor(predictor_type="simple", model_path=None):
        """
        Creates an instance of the specified predictor.
        
        Args:
            predictor_type: Type of predictor ("simple" or "ml")
            model_path: Path to a pre-trained model (for "ml")
            
        Returns:
            An instance of the requested predictor
        """
        if predictor_type.lower() == "ml":
            return MLBodyPredictor(model_path)
        else:
            return SimpleBodyPredictor()