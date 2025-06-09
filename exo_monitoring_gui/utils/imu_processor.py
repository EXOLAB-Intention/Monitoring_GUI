"""
Processeur IMU avancé avec filtrage, conversion de formats et gestion d'erreurs.
Implémente les filtres Kalman, Madgwick et autres algorithmes de fusion de capteurs.
"""
import numpy as np
import math
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
from enum import Enum
from dataclasses import dataclass
import warnings

# === Types et énumérations ===
class IMUDataQuality(Enum):
    """Qualité des données IMU."""
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    LOST = "lost"

class FilterType(Enum):
    """Types de filtres disponibles."""
    NONE = "none"
    LOW_PASS = "low_pass"
    KALMAN = "kalman"
    MADGWICK = "madgwick"
    COMPLEMENTARY = "complementary"
    ADAPTIVE = "adaptive"

@dataclass
class IMUReading:
    """Structure pour une lecture IMU complète."""
    timestamp: float
    quaternion: np.ndarray  # [w, x, y, z]
    angular_velocity: Optional[np.ndarray] = None  # [wx, wy, wz] rad/s
    linear_acceleration: Optional[np.ndarray] = None  # [ax, ay, az] m/s²
    quality: IMUDataQuality = IMUDataQuality.GOOD
    sensor_id: int = 0

@dataclass
class FilterConfig:
    """Configuration pour les filtres IMU."""
    filter_type: FilterType = FilterType.ADAPTIVE
    cutoff_frequency: float = 10.0  # Hz
    sample_rate: float = 100.0  # Hz
    beta: float = 0.1  # Paramètre Madgwick
    kalman_q: float = 0.001  # Bruit de processus Kalman
    kalman_r: float = 0.1  # Bruit de mesure Kalman
    adaptive_threshold: float = 0.05
    outlier_threshold: float = 3.0  # Écarts-types

# === Utilitaires quaternion ===
class QuaternionUtils:
    """Utilitaires pour les opérations quaternion."""
    
    @staticmethod
    def normalize(q: np.ndarray) -> np.ndarray:
        """Normalise un quaternion."""
        norm = np.linalg.norm(q)
        if norm < 1e-9:
            return np.array([1.0, 0.0, 0.0, 0.0])  # Identité
        return q / norm
    
    @staticmethod
    def multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiplie deux quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        
        return QuaternionUtils.normalize(np.array([w, x, y, z]))
    
    @staticmethod
    def conjugate(q: np.ndarray) -> np.ndarray:
        """Calcule le conjugué d'un quaternion."""
        return np.array([q[0], -q[1], -q[2], -q[3]])
    
    @staticmethod
    def to_euler(q: np.ndarray, degrees: bool = False) -> np.ndarray:
        """Convertit un quaternion en angles d'Euler (roll, pitch, yaw)."""
        w, x, y, z = q
        
        # Roll (rotation autour de l'axe X)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (rotation autour de l'axe Y)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # ±90°
        else:
            pitch = math.asin(sinp)
        
        # Yaw (rotation autour de l'axe Z)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        angles = np.array([roll, pitch, yaw])
        return np.degrees(angles) if degrees else angles
    
    @staticmethod
    def from_euler(roll: float, pitch: float, yaw: float, degrees: bool = False) -> np.ndarray:
        """Convertit des angles d'Euler en quaternion."""
        if degrees:
            roll = math.radians(roll)
            pitch = math.radians(pitch)
            yaw = math.radians(yaw)
        
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
        
        return QuaternionUtils.normalize(np.array([w, x, y, z]))
    
    @staticmethod
    def slerp(q1: np.ndarray, q2: np.ndarray, t: float) -> np.ndarray:
        """Interpolation sphérique entre deux quaternions."""
        # Calculer le produit scalaire
        dot = np.dot(q1, q2)
        
        # Si le produit scalaire est négatif, utiliser -q2 pour prendre le chemin le plus court
        if dot < 0.0:
            q2 = -q2
            dot = -dot
        
        # Si les quaternions sont très proches, utiliser l'interpolation linéaire
        if dot > 0.9995:
            result = q1 + t * (q2 - q1)
            return QuaternionUtils.normalize(result)
        
        # Calculer l'angle entre les quaternions
        theta_0 = math.acos(abs(dot))
        sin_theta_0 = math.sin(theta_0)
        
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        
        s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0
        
        return QuaternionUtils.normalize(s0 * q1 + s1 * q2)
    
    @staticmethod
    def angular_distance(q1: np.ndarray, q2: np.ndarray) -> float:
        """Calcule la distance angulaire entre deux quaternions en radians."""
        dot = abs(np.dot(q1, q2))
        # Limiter la valeur pour éviter les erreurs numériques
        dot = min(1.0, max(-1.0, dot))
        return 2 * math.acos(dot)

# === Filtres de base ===
class IMUFilter(ABC):
    """Interface de base pour les filtres IMU."""
    
    @abstractmethod
    def process(self, quaternion: np.ndarray, timestamp: float) -> np.ndarray:
        """Traite une mesure quaternion."""
        pass
    
    @abstractmethod
    def reset(self):
        """Remet le filtre à zéro."""
        pass

class LowPassFilter(IMUFilter):
    """Filtre passe-bas pour quaternions."""
    
    def __init__(self, cutoff_freq: float, sample_rate: float):
        self.cutoff_freq = cutoff_freq
        self.sample_rate = sample_rate
        self.alpha = self._calculate_alpha(cutoff_freq, sample_rate)
        self.filtered_quat = None
        
    def _calculate_alpha(self, cutoff_freq: float, sample_rate: float) -> float:
        """Calcule le coefficient alpha pour le filtre passe-bas."""
        dt = 1.0 / sample_rate
        rc = 1.0 / (2.0 * math.pi * cutoff_freq)
        return dt / (dt + rc)
    
    def process(self, quaternion: np.ndarray, timestamp: float) -> np.ndarray:
        if self.filtered_quat is None:
            self.filtered_quat = quaternion.copy()
            return self.filtered_quat
        
        # Utiliser SLERP pour l'interpolation des quaternions
        self.filtered_quat = QuaternionUtils.slerp(
            self.filtered_quat, quaternion, self.alpha
        )
        
        return self.filtered_quat
    
    def reset(self):
        self.filtered_quat = None

class KalmanQuaternionFilter(IMUFilter):
    """Filtre de Kalman adapté pour les quaternions."""
    
    def __init__(self, process_noise: float = 0.001, measurement_noise: float = 0.1):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        
        # État: quaternion [w, x, y, z]
        self.state = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Matrice de covariance de l'erreur
        self.P = np.eye(4) * 1.0
        
        # Matrice de bruit de processus
        self.Q = np.eye(4) * process_noise
        
        # Matrice de bruit de mesure
        self.R = np.eye(4) * measurement_noise
        
        self.last_timestamp = None
    
    def process(self, quaternion: np.ndarray, timestamp: float) -> np.ndarray:
        if self.last_timestamp is None:
            self.state = QuaternionUtils.normalize(quaternion)
            self.last_timestamp = timestamp
            return self.state
        
        dt = timestamp - self.last_timestamp
        self.last_timestamp = timestamp
        
        # Prédiction (modèle d'évolution simple)
        # F = I (pas de modèle dynamique)
        F = np.eye(4)
        
        # Prédiction de l'état
        predicted_state = self.state
        
        # Prédiction de la covariance
        predicted_P = F @ self.P @ F.T + self.Q * dt
        
        # Correction (mise à jour avec la mesure)
        H = np.eye(4)  # Matrice d'observation
        
        # Innovation
        z = QuaternionUtils.normalize(quaternion)  # Mesure normalisée
        y = z - predicted_state  # Innovation
        
        # Covariance de l'innovation
        S = H @ predicted_P @ H.T + self.R
        
        # Gain de Kalman
        try:
            K = predicted_P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # Si la matrice n'est pas inversible, utiliser la pseudo-inverse
            K = predicted_P @ H.T @ np.linalg.pinv(S)
        
        # Mise à jour de l'état
        self.state = predicted_state + K @ y
        self.state = QuaternionUtils.normalize(self.state)
        
        # Mise à jour de la covariance
        I_KH = np.eye(4) - K @ H
        self.P = I_KH @ predicted_P
        
        return self.state
    
    def reset(self):
        self.state = np.array([1.0, 0.0, 0.0, 0.0])
        self.P = np.eye(4) * 1.0
        self.last_timestamp = None

class MadgwickFilter(IMUFilter):
    """Filtre Madgwick pour fusion IMU."""
    
    def __init__(self, beta: float = 0.1, sample_rate: float = 100.0):
        self.beta = beta  # Gain du filtre
        self.sample_rate = sample_rate
        self.q = np.array([1.0, 0.0, 0.0, 0.0])  # Quaternion d'orientation
        self.last_timestamp = None
    
    def process(self, quaternion: np.ndarray, timestamp: float, 
                gyro: Optional[np.ndarray] = None, 
                accel: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Traite les données IMU avec l'algorithme Madgwick.
        
        Args:
            quaternion: Quaternion de mesure
            timestamp: Timestamp de la mesure
            gyro: Données gyroscope [wx, wy, wz] (optionnel)
            accel: Données accéléromètre [ax, ay, az] (optionnel)
        """
        if self.last_timestamp is None:
            self.q = QuaternionUtils.normalize(quaternion)
            self.last_timestamp = timestamp
            return self.q
        
        dt = timestamp - self.last_timestamp
        self.last_timestamp = timestamp
        
        # Si on a des données gyroscope et accéléromètre, utiliser l'algorithme complet
        if gyro is not None and accel is not None:
            self.q = self._madgwick_ahrs_update(self.q, gyro, accel, dt)
        else:
            # Sinon, utiliser seulement le quaternion de mesure avec lissage
            self.q = QuaternionUtils.slerp(self.q, quaternion, self.beta * dt * self.sample_rate)
        
        return self.q
    
    def _madgwick_ahrs_update(self, q: np.ndarray, gyro: np.ndarray, 
                             accel: np.ndarray, dt: float) -> np.ndarray:
        """Implémentation de l'algorithme Madgwick AHRS."""
        q0, q1, q2, q3 = q
        gx, gy, gz = gyro
        ax, ay, az = accel
        
        # Normaliser l'accéléromètre
        norm = math.sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return q  # Éviter division par zéro
        ax /= norm
        ay /= norm
        az /= norm
        
        # Fonction objective et gradient
        f1 = 2*(q1*q3 - q0*q2) - ax
        f2 = 2*(q0*q1 + q2*q3) - ay
        f3 = 2*(0.5 - q1*q1 - q2*q2) - az
        
        J_11or24 = 2*q2
        J_12or23 = 2*q3
        J_13or22 = 2*q0
        J_14or21 = 2*q1
        J_32 = 2*J_14or21
        J_33 = 2*J_11or24
        
        # Gradient
        step = np.array([
            J_13or22*f2 - J_12or23*f1,
            J_12or23*f2 + J_13or22*f1 - J_32*f3,
            J_11or24*f1 + J_33*f3 - J_13or22*f2,
            J_14or21*f1 + J_11or24*f2
        ])
        
        # Normaliser le gradient
        norm = math.sqrt(step[0]*step[0] + step[1]*step[1] + step[2]*step[2] + step[3]*step[3])
        if norm != 0:
            step /= norm
        
        # Intégration du gyroscope
        qDot1 = 0.5 * (-q1*gx - q2*gy - q3*gz)
        qDot2 = 0.5 * (q0*gx + q2*gz - q3*gy)
        qDot3 = 0.5 * (q0*gy - q1*gz + q3*gx)
        qDot4 = 0.5 * (q0*gz + q1*gy - q2*gx)
        
        # Appliquer la correction du gradient
        qDot1 -= self.beta * step[0]
        qDot2 -= self.beta * step[1]
        qDot3 -= self.beta * step[2]
        qDot4 -= self.beta * step[3]
        
        # Intégrer pour obtenir le quaternion
        q0 += qDot1 * dt
        q1 += qDot2 * dt
        q2 += qDot3 * dt
        q3 += qDot4 * dt
        
        return QuaternionUtils.normalize(np.array([q0, q1, q2, q3]))
    
    def reset(self):
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.last_timestamp = None

class AdaptiveFilter(IMUFilter):
    """Filtre adaptatif qui ajuste ses paramètres selon la qualité des données."""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.primary_filter = MadgwickFilter(config.beta, config.sample_rate)
        self.backup_filter = LowPassFilter(config.cutoff_frequency, config.sample_rate)
        
        self.quality_history = deque(maxlen=50)
        self.last_good_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        self.degraded_mode = False
        
    def process(self, quaternion: np.ndarray, timestamp: float) -> np.ndarray:
        # Évaluer la qualité des données
        quality = self._assess_data_quality(quaternion)
        self.quality_history.append(quality)
        
        # Déterminer le mode de fonctionnement
        avg_quality = np.mean(self.quality_history) if self.quality_history else 1.0
        
        if avg_quality < self.config.adaptive_threshold:
            if not self.degraded_mode:
                print(f"[IMU] Basculement en mode dégradé (qualité: {avg_quality:.3f})")
                self.degraded_mode = True
            
            # Utiliser le filtre de secours avec lissage plus fort
            result = self.backup_filter.process(quaternion, timestamp)
        else:
            if self.degraded_mode:
                print(f"[IMU] Retour en mode normal (qualité: {avg_quality:.3f})")
                self.degraded_mode = False
            
            # Utiliser le filtre principal
            result = self.primary_filter.process(quaternion, timestamp)
        
        # Sauvegarder le dernier bon quaternion
        if quality > 0.5:
            self.last_good_quaternion = result.copy()
        
        return result
    
    def _assess_data_quality(self, quaternion: np.ndarray) -> float:
        """Évalue la qualité d'un quaternion (0.0 = mauvais, 1.0 = excellent)."""
        # Vérifier la norme
        norm = np.linalg.norm(quaternion)
        if abs(norm - 1.0) > 0.1:  # Quaternion mal normalisé
            return 0.0
        
        # Vérifier les valeurs NaN/Inf
        if not np.isfinite(quaternion).all():
            return 0.0
        
        # Vérifier la cohérence avec l'historique
        if len(self.quality_history) > 0:
            angular_change = QuaternionUtils.angular_distance(
                quaternion, self.last_good_quaternion
            )
            
            # Si le changement est trop important, c'est suspect
            max_change_per_frame = math.radians(30)  # 30° max par frame
            if angular_change > max_change_per_frame:
                return 0.2
        
        # Score basé sur la stabilité
        stability_score = 1.0 - min(1.0, abs(norm - 1.0) * 10)
        
        return stability_score
    
    def reset(self):
        self.primary_filter.reset()
        self.backup_filter.reset()
        self.quality_history.clear()
        self.last_good_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        self.degraded_mode = False

# === Détecteur d'anomalies ===
class OutlierDetector:
    """Détecteur d'anomalies pour les données IMU."""
    
    def __init__(self, window_size: int = 20, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        self.history = deque(maxlen=window_size)
        
    def is_outlier(self, quaternion: np.ndarray) -> bool:
        """Détermine si un quaternion est une valeur aberrante."""
        if len(self.history) < self.window_size // 2:
            self.history.append(quaternion)
            return False
        
        # Calculer les distances angulaires avec l'historique récent
        distances = []
        for hist_quat in list(self.history)[-10:]:  # Utiliser les 10 dernières mesures
            dist = QuaternionUtils.angular_distance(quaternion, hist_quat)
            distances.append(dist)
        
        if not distances:
            return False
        
        # Calculer la moyenne et l'écart-type
        mean_dist = np.mean(distances)
        std_dist = np.std(distances)
        
        # Vérifier si c'est un outlier
        current_dist = min(distances)  # Distance minimale
        is_outlier = False
        
        if std_dist > 0:
            z_score = (current_dist - mean_dist) / std_dist
            is_outlier = abs(z_score) > self.threshold
        
        # Ajouter à l'historique seulement si ce n'est pas un outlier
        if not is_outlier:
            self.history.append(quaternion)
        
        return is_outlier

# === Processeur principal ===
class IMUProcessor:
    """Processeur principal pour les données IMU avec filtrage et gestion d'erreurs."""
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        
        # Initialiser les filtres selon la configuration
        self.filters = {}
        self.outlier_detectors = {}
        self.signal_lost_counters = {}
        self.last_good_readings = {}
        
        # Statistiques
        self.stats = {
            'total_readings': 0,
            'outliers_detected': 0,
            'signal_losses': 0,
            'filter_switches': 0
        }
        
        print(f"[IMU] Processeur initialisé avec filtre: {self.config.filter_type.value}")
    
    def _create_filter(self, sensor_id: int) -> IMUFilter:
        """Crée un filtre pour un capteur spécifique."""
        if self.config.filter_type == FilterType.NONE:
            return LowPassFilter(1000.0, self.config.sample_rate)  # Filtre transparent
        elif self.config.filter_type == FilterType.LOW_PASS:
            return LowPassFilter(self.config.cutoff_frequency, self.config.sample_rate)
        elif self.config.filter_type == FilterType.KALMAN:
            return KalmanQuaternionFilter(self.config.kalman_q, self.config.kalman_r)
        elif self.config.filter_type == FilterType.MADGWICK:
            return MadgwickFilter(self.config.beta, self.config.sample_rate)
        elif self.config.filter_type == FilterType.ADAPTIVE:
            return AdaptiveFilter(self.config)
        else:
            return LowPassFilter(self.config.cutoff_frequency, self.config.sample_rate)
    
    def process_imu_data(self, sensor_id: int, quaternion: np.ndarray, 
                        timestamp: float = None, 
                        gyro: Optional[np.ndarray] = None,
                        accel: Optional[np.ndarray] = None) -> IMUReading:
        """
        Traite les données d'un capteur IMU.
        
        Args:
            sensor_id: ID du capteur IMU
            quaternion: Quaternion [w, x, y, z]
            timestamp: Timestamp de la mesure (utilise time.time() si None)
            gyro: Données gyroscope [wx, wy, wz] (optionnel)
            accel: Données accéléromètre [ax, ay, az] (optionnel)
            
        Returns:
            IMUReading: Lecture IMU traitée avec qualité évaluée
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.stats['total_readings'] += 1
        
        # Initialiser les structures pour ce capteur si nécessaire
        if sensor_id not in self.filters:
            self.filters[sensor_id] = self._create_filter(sensor_id)
            self.outlier_detectors[sensor_id] = OutlierDetector(
                threshold=self.config.outlier_threshold
            )
            self.signal_lost_counters[sensor_id] = 0
            self.last_good_readings[sensor_id] = None
        
        # Vérifier la validité des données
        if not self._is_valid_quaternion(quaternion):
            self.signal_lost_counters[sensor_id] += 1
            return self._handle_invalid_data(sensor_id, timestamp)
        
        # Normaliser le quaternion
        normalized_quat = QuaternionUtils.normalize(quaternion)
        
        # Détecter les valeurs aberrantes
        is_outlier = self.outlier_detectors[sensor_id].is_outlier(normalized_quat)
        if is_outlier:
            self.stats['outliers_detected'] += 1
            print(f"[IMU{sensor_id}] Valeur aberrante détectée, utilisation de la dernière valeur valide")
            
            # Utiliser la dernière lecture valide avec interpolation
            if self.last_good_readings[sensor_id] is not None:
                last_reading = self.last_good_readings[sensor_id]
                # Interpolation temporelle simple
                time_diff = timestamp - last_reading.timestamp
                if time_diff < 1.0:  # Moins d'une seconde
                    interpolated_quat = last_reading.quaternion
                    quality = IMUDataQuality.DEGRADED
                else:
                    interpolated_quat = normalized_quat  # Utiliser quand même la nouvelle valeur
                    quality = IMUDataQuality.POOR
            else:
                interpolated_quat = normalized_quat
                quality = IMUDataQuality.POOR
        else:
            interpolated_quat = normalized_quat
            quality = IMUDataQuality.GOOD
            self.signal_lost_counters[sensor_id] = 0  # Reset du compteur
        
        # Appliquer le filtrage
        try:
            filtered_quat = self.filters[sensor_id].process(interpolated_quat, timestamp)
            
            # Pour le filtre Madgwick, passer les données supplémentaires si disponibles
            if isinstance(self.filters[sensor_id], MadgwickFilter) and gyro is not None and accel is not None:
                filtered_quat = self.filters[sensor_id].process(
                    interpolated_quat, timestamp, gyro, accel
                )
            
        except Exception as e:
            print(f"[IMU{sensor_id}] Erreur de filtrage: {e}")
            filtered_quat = interpolated_quat
            quality = IMUDataQuality.DEGRADED
        
        # Créer la lecture IMU
        reading = IMUReading(
            timestamp=timestamp,
            quaternion=filtered_quat,
            angular_velocity=gyro,
            linear_acceleration=accel,
            quality=quality,
            sensor_id=sensor_id
        )
        
        # Sauvegarder comme dernière lecture valide si la qualité est suffisante
        if quality in [IMUDataQuality.EXCELLENT, IMUDataQuality.GOOD]:
            self.last_good_readings[sensor_id] = reading
        
        return reading
    
    def _is_valid_quaternion(self, quaternion: np.ndarray) -> bool:
        """Vérifie si un quaternion est valide."""
        if quaternion is None or len(quaternion) != 4:
            return False
        
        if not np.isfinite(quaternion).all():
            return False
        
        norm = np.linalg.norm(quaternion)
        if norm < 1e-6 or norm > 10.0:  # Norme trop petite ou trop grande
            return False
        
        return True
    
    def _handle_invalid_data(self, sensor_id: int, timestamp: float) -> IMUReading:
        """Gère les données invalides en utilisant la dernière valeur connue."""
        # Incrémenter le compteur de perte de signal
        if self.signal_lost_counters[sensor_id] > 10:  # Signal perdu depuis trop longtemps
            self.stats['signal_losses'] += 1
            quality = IMUDataQuality.LOST
            quaternion = np.array([1.0, 0.0, 0.0, 0.0])  # Quaternion identité
        else:
            quality = IMUDataQuality.POOR
            # Utiliser la dernière lecture valide si disponible
            if self.last_good_readings[sensor_id] is not None:
                quaternion = self.last_good_readings[sensor_id].quaternion
            else:
                quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        
        return IMUReading(
            timestamp=timestamp,
            quaternion=quaternion,
            quality=quality,
            sensor_id=sensor_id
        )
    
    def get_conversion_formats(self, reading: IMUReading) -> Dict[str, Any]:
        """Convertit une lecture IMU en différents formats."""
        quat = reading.quaternion
        
        formats = {
            'quaternion_wxyz': quat.tolist(),
            'quaternion_xyzw': [quat[1], quat[2], quat[3], quat[0]],  # Format alternatif
            'euler_rad': QuaternionUtils.to_euler(quat, degrees=False).tolist(),
            'euler_deg': QuaternionUtils.to_euler(quat, degrees=True).tolist(),
            'rotation_matrix': self._quaternion_to_rotation_matrix(quat).tolist(),
            'axis_angle': self._quaternion_to_axis_angle(quat),
            'quality': reading.quality.value,
            'timestamp': reading.timestamp
        }
        
        return formats
    
    def _quaternion_to_rotation_matrix(self, q: np.ndarray) -> np.ndarray:
        """Convertit un quaternion en matrice de rotation 3x3."""
        w, x, y, z = q
        
        # Première ligne
        r00 = 1 - 2*(y*y + z*z)
        r01 = 2*(x*y - w*z)
        r02 = 2*(x*z + w*y)
        
        # Deuxième ligne  
        r10 = 2*(x*y + w*z)
        r11 = 1 - 2*(x*x + z*z)
        r12 = 2*(y*z - w*x)
        
        # Troisième ligne
        r20 = 2*(x*z - w*y)
        r21 = 2*(y*z + w*x)
        r22 = 1 - 2*(x*x + y*y)
        
        return np.array([
            [r00, r01, r02],
            [r10, r11, r12],
            [r20, r21, r22]
        ])
    
    def _quaternion_to_axis_angle(self, q: np.ndarray) -> Dict[str, Any]:
        """Convertit un quaternion en représentation axe-angle."""
        w, x, y, z = q
        
        # Calculer l'angle
        angle = 2 * math.acos(abs(w))
        
        # Calculer l'axe
        sin_half_angle = math.sqrt(1 - w*w)
        if sin_half_angle < 1e-6:
            # Pas de rotation
            axis = [1.0, 0.0, 0.0]
        else:
            axis = [x / sin_half_angle, y / sin_half_angle, z / sin_half_angle]
        
        return {
            'axis': axis,
            'angle_rad': angle,
            'angle_deg': math.degrees(angle)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques du processeur."""
        total = max(1, self.stats['total_readings'])  # Éviter division par zéro
        
        return {
            'total_readings': self.stats['total_readings'],
            'outliers_detected': self.stats['outliers_detected'],
            'outlier_rate': self.stats['outliers_detected'] / total,
            'signal_losses': self.stats['signal_losses'],
            'signal_loss_rate': self.stats['signal_losses'] / total,
            'filter_type': self.config.filter_type.value,
            'active_sensors': len(self.filters),
            'sensors_with_data': len([s for s in self.last_good_readings.values() if s is not None])
        }
    
    def update_config(self, new_config: FilterConfig):
        """Met à jour la configuration et recrée les filtres si nécessaire."""
        old_filter_type = self.config.filter_type
        self.config = new_config
        
        if old_filter_type != new_config.filter_type:
            print(f"[IMU] Changement de filtre: {old_filter_type.value} -> {new_config.filter_type.value}")
            
            # Recréer tous les filtres
            for sensor_id in self.filters:
                self.filters[sensor_id] = self._create_filter(sensor_id)
            
            self.stats['filter_switches'] += 1
    
    def reset_sensor(self, sensor_id: int):
        """Remet à zéro un capteur spécifique."""
        if sensor_id in self.filters:
            self.filters[sensor_id].reset()
            self.signal_lost_counters[sensor_id] = 0
            self.last_good_readings[sensor_id] = None
            print(f"[IMU] Capteur {sensor_id} remis à zéro")
    
    def reset_all(self):
        """Remet à zéro tous les capteurs."""
        for sensor_id in list(self.filters.keys()):
            self.reset_sensor(sensor_id)
        
        self.stats = {
            'total_readings': 0,
            'outliers_detected': 0,
            'signal_losses': 0,
            'filter_switches': 0
        }
        print("[IMU] Tous les capteurs remis à zéro")

# === Factory pour création simplifiée ===
class IMUProcessorFactory:
    """Factory pour créer des processeurs IMU préconfigurés."""
    
    @staticmethod
    def create_default() -> IMUProcessor:
        """Crée un processeur avec configuration par défaut."""
        config = FilterConfig(
            filter_type=FilterType.ADAPTIVE,
            cutoff_frequency=15.0,
            sample_rate=100.0,
            beta=0.1
        )
        return IMUProcessor(config)
    
    @staticmethod
    def create_high_precision() -> IMUProcessor:
        """Crée un processeur haute précision."""
        config = FilterConfig(
            filter_type=FilterType.KALMAN,
            cutoff_frequency=25.0,
            sample_rate=100.0,
            kalman_q=0.0001,
            kalman_r=0.01,
            outlier_threshold=2.0
        )
        return IMUProcessor(config)
    
    @staticmethod
    def create_low_latency() -> IMUProcessor:
        """Crée un processeur faible latence."""
        config = FilterConfig(
            filter_type=FilterType.LOW_PASS,
            cutoff_frequency=50.0,
            sample_rate=100.0,
            outlier_threshold=4.0
        )
        return IMUProcessor(config)
    
    @staticmethod
    def create_robust() -> IMUProcessor:
        """Crée un processeur robuste pour environnements difficiles."""
        config = FilterConfig(
            filter_type=FilterType.ADAPTIVE,
            cutoff_frequency=10.0,
            sample_rate=100.0,
            beta=0.05,
            adaptive_threshold=0.1,
            outlier_threshold=2.5
        )
        return IMUProcessor(config)

# === Fonction de test ===
def test_imu_processor():
    """Teste le processeur IMU avec des données simulées."""
    print("=== Test du processeur IMU ===")
    
    # Créer un processeur
    processor = IMUProcessorFactory.create_default()
    
    # Simuler des données IMU
    for i in range(100):
        # Créer un quaternion de test (rotation lente autour de Z)
        angle = i * 0.1
        quat = QuaternionUtils.from_euler(0, 0, angle)
        
        # Ajouter du bruit
        noise = np.random.normal(0, 0.01, 4)
        noisy_quat = QuaternionUtils.normalize(quat + noise)
        
        # Traiter la donnée
        reading = processor.process_imu_data(1, noisy_quat, time.time())
        
        if i % 20 == 0:
            print(f"Frame {i}: Qualité = {reading.quality.value}, "
                  f"Quaternion = [{reading.quaternion[0]:.3f}, {reading.quaternion[1]:.3f}, "
                  f"{reading.quaternion[2]:.3f}, {reading.quaternion[3]:.3f}]")
    
    # Afficher les statistiques
    stats = processor.get_statistics()
    print(f"\nStatistiques finales:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("=== Test terminé ===")

if __name__ == "__main__":
    test_imu_processor()
