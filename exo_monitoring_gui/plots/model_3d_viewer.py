import sys
import os
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtOpenGL import QGLWidget, QGLFormat
from PyQt5.QtGui import QFont, QPainter, QColor  # Added QColor import
from OpenGL.GL import *
from OpenGL.GLU import *
import math

# Add parent directory to path for proper module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.body_motion_predictor import MotionPredictorFactory

# Définir la classe Model3DWidget au début pour qu'elle soit disponible lors des imports
class Model3DWidget(QWidget):
    """Widget wrapper for the 3D model viewer."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        
        # Forcer la transparence du widget
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the OpenGL viewer
        self.model_viewer = Model3DViewer(self)
        # Forcer la transparence du viewer OpenGL
        self.model_viewer.setAttribute(Qt.WA_TranslucentBackground)
        layout.addWidget(self.model_viewer)
        
        self.setLayout(layout)
        
        # Force visibility
        self.setVisible(True)
        self.show()
    
    def apply_imu_data(self, imu_id, quaternion_data):
        """Forward IMU data to the internal viewer."""
        return self.model_viewer.apply_imu_data(imu_id, quaternion_data)
    
    def map_imu_to_body_part(self, imu_id, body_part):
        """Forward IMU mapping to the internal viewer."""
        return self.model_viewer.map_imu_to_body_part(imu_id, body_part)
    
    def get_current_mappings(self):
        """Get current IMU mappings."""
        return self.model_viewer.get_current_mappings()
    
    def toggle_animation(self):
        """Toggle walking animation."""
        return self.model_viewer.toggle_walking()
    
    def reset_view(self):
        """Reset the 3D view."""
        self.model_viewer.reset_view()
    
    def toggle_motion_prediction(self):
        """Toggle motion prediction feature."""
        current_state = self.model_viewer.use_motion_prediction
        self.model_viewer.use_motion_prediction = not current_state
        return self.model_viewer.use_motion_prediction
    
    def start_tpose_calibration(self):
        """Start T-pose calibration."""
        return self.model_viewer.start_tpose_calibration()
    
    def stop_tpose_calibration(self):
        """Stop T-pose calibration."""
        return self.model_viewer.stop_tpose_calibration()
    
    def reset_calibration(self):
        """Reset T-pose calibration."""
        self.model_viewer.reset_calibration()
    
    def get_calibration_status(self):
        """Get calibration status."""
        return self.model_viewer.get_calibration_status()

# --- Quaternion Utility Functions ---
def normalize_quaternion(q):
    norm = np.linalg.norm(q)
    if norm < 1e-9:  # Avoid division by zero
        return np.array([1.0, 0.0, 0.0, 0.0])  # Identity quaternion
    return np.array(q) / norm

def quaternion_multiply(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    return normalize_quaternion(np.array([w, x, y, z]))

def quaternion_from_axis_angle(axis, angle_rad):
    axis = np.array(axis)
    axis = axis / np.linalg.norm(axis)
    half_angle = angle_rad / 2.0
    w = math.cos(half_angle)
    x, y, z = axis * math.sin(half_angle)
    return normalize_quaternion(np.array([w, x, y, z]))

def quaternion_to_matrix(q):
    """Converts a quaternion to a 4x4 rotation matrix (OpenGL format)"""
    w, x, y, z = q
    x2, y2, z2, w2 = x*x, y*y, z*z, w*w
    xy, xz, yz = x*y, x*z, y*z
    wx, wy, wz = w*x, w*y, w*z

    # Format compatible with OpenGL - column-major order
    m = np.array([
        [1-2*(y2+z2),   2*(xy-wz),    2*(xz+wy),  0],
        [2*(xy+wz),   1-2*(x2+z2),    2*(yz-wx),  0],
        [2*(xz-wy),     2*(yz+wx),  1-2*(x2+y2),  0],
        [0,             0,            0,          1]
    ], dtype=np.float32).flatten(order='F')  # 'F' corresponds to column-major order for OpenGL
    
    return m

class Model3DViewer(QGLWidget):
    def __init__(self, parent=None):
        fmt = QGLFormat()
        fmt.setDoubleBuffer(True)
        fmt.setSampleBuffers(True)
        fmt.setSwapInterval(1)
        # Très important: activer la transparence du format OpenGL
        fmt.setAlpha(True)
        
        # Try to set a standard OpenGL version
        try:
            fmt.setVersion(2, 1)  # OpenGL 2.1 est largement supporté
            fmt.setProfile(QGLFormat.CompatibilityProfile)
        except:
            pass  # Ignorer si la version n'est pas supportée
        
        super().__init__(fmt, parent)
        
        # Add flag to track widget destruction state
        self.is_being_destroyed = False
        
        # Add missing attributes to fix errors
        self._initialized = False
        self.is_visible_to_user = True
        
        # Force taille minimale pour assurer la visibilité
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        self.mouse_pressed = False  # Initialize mouse pressed state
        
        # Initialize camera distance for zoom functionality
        self.camera_distance = 3.5  # Reduced from 4.0 to bring model closer
        
        self.animation_phase = 0
        self.walking = False
        
        self.fps_timer = QElapsedTimer()
        self.fps_timer.start()
        self.frame_count = 0
        self.fps = 0
        self.show_fps = True

        identity_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        
        self.body_parts = {
            'head': {'pos': np.array([0, 1.7, 0]), 'rot': identity_quaternion.copy()},
            'neck': {'pos': np.array([0, 1.5, 0]), 'rot': identity_quaternion.copy()},
            'torso': {'pos': np.array([0, 0.9, 0]), 'rot': identity_quaternion.copy()},
            'deltoid_l': {'pos': np.array([-0.15, 1.4, 0]), 'rot': identity_quaternion.copy()},
            'biceps_l': {'pos': np.array([-0.3, 1.3, 0]), 'rot': identity_quaternion.copy()},
            'forearm_l': {'pos': np.array([-0.4, 1.1, 0]), 'rot': identity_quaternion.copy()},
            'dorsalis_major_l': {'pos': np.array([-0.1, 1.2, 0]), 'rot': identity_quaternion.copy()},
            'pectorals_l': {'pos': np.array([-0.1, 1.3, 0]), 'rot': identity_quaternion.copy()},
            'left_hand': {'pos': np.array([-0.5, 0.8, 0]), 'rot': identity_quaternion.copy()},
            'deltoid_r': {'pos': np.array([0.15, 1.4, 0]), 'rot': identity_quaternion.copy()},
            'biceps_r': {'pos': np.array([0.3, 1.3, 0]), 'rot': identity_quaternion.copy()},
            'forearm_r': {'pos': np.array([0.4, 1.1, 0]), 'rot': identity_quaternion.copy()},
            'dorsalis_major_r': {'pos': np.array([0.1, 1.2, 0]), 'rot': identity_quaternion.copy()},
            'pectorals_r': {'pos': np.array([0.1, 1.3, 0]), 'rot': identity_quaternion.copy()},
            'right_hand': {'pos': np.array([0.5, 0.8, 0]), 'rot': identity_quaternion.copy()},
            'hip': {'pos': np.array([0, 0.9, 0]), 'rot': identity_quaternion.copy()},
            'quadriceps_l': {'pos': np.array([-0.15, 0.7, 0]), 'rot': identity_quaternion.copy()},
            'quadriceps_r': {'pos': np.array([0.15, 0.7, 0]), 'rot': identity_quaternion.copy()},
            'ishcio_hamstrings_l': {'pos': np.array([-0.15, 0.6, 0]), 'rot': identity_quaternion.copy()},
            'ishcio_hamstrings_r': {'pos': np.array([0.15, 0.6, 0]), 'rot': identity_quaternion.copy()},
            'calves_l': {'pos': np.array([-0.2, 0.3, 0]), 'rot': identity_quaternion.copy()},
            'calves_r': {'pos': np.array([0.2, 0.3, 0]), 'rot': identity_quaternion.copy()},
            'glutes_l': {'pos': np.array([-0.15, 0.8, 0]), 'rot': identity_quaternion.copy()},
            'glutes_r': {'pos': np.array([0.15, 0.8, 0]), 'rot': identity_quaternion.copy()},
            'left_foot': {'pos': np.array([-0.2, 0.0, 0]), 'rot': identity_quaternion.copy()},
            'right_foot': {'pos': np.array([0.2, 0.0, 0]), 'rot': identity_quaternion.copy()}
        }
        
        self.initial_body_parts_state = {
            name: {'pos': data['pos'].copy(), 'rot': data['rot'].copy()}
            for name, data in self.body_parts.items()
        }

        self.imu_mapping = {}
        self.emg_mapping = {}  # Initialize EMG mapping dictionary
        self.pmmg_mapping = {}  # Initialize pMMG mapping dictionary
        
        self.legacy_mappings = {
            'left_elbow': 'forearm_l',
            'right_elbow': 'forearm_r',
            'left_knee': 'calves_l',
            'right_knee': 'calves_r'
        }
        
        self.num_precalc_frames = 120
        self.precalculated_animation_frames = self._precalculate_animation(self.num_precalc_frames)
        self.precalc_frame = 0
        
        self.display_list = 0
        self.quadric = None
        
        self.animation_main_timer = QTimer(self)
        self.animation_main_timer.timeout.connect(self.update_animation_frame)
        self.animation_main_timer.setInterval(16)

        self.fps_update_timer = QTimer(self)
        self.fps_update_timer.timeout.connect(self.update_fps)
        self.fps_update_timer.start(1000)
        
        # Initialize the motion predictor - CORRIGER LE CHEMIN DU MODÈLE
        base_dir = os.path.dirname(os.path.dirname(__file__))
        model_paths = [
            os.path.join(base_dir, 'data', 'motion_model.pth'),
            os.path.join(base_dir, 'data', 'training_viz', 'motion_model.pth')
        ]
        
        # Essayer les deux chemins possibles
        model_path = None
        for path in model_paths:
            if os.path.exists(path):
                model_path = path
                print(f"Modèle trouvé: {path}")
                break
        
        if not model_path:
            print("Attention: Aucun modèle trouvé dans les chemins standards.")
            model_path = model_paths[0]  # Utiliser le chemin par défaut pour afficher l'erreur
            
        self.motion_predictor = MotionPredictorFactory.create_predictor("simple", model_path)
        self.use_motion_prediction = True  # Enabled by default
        
        # État de calibration T-pose
        self.calibration_mode = False
        self.calibration_complete = False
        self.calibration_reference = {}
        self.calibration_timer = QTimer(self)
        self.calibration_timer.timeout.connect(self.update_calibration_status)
        self.calibration_duration = 0
        self.calibration_required_time = 3000  # 3 secondes en T-pose
        self.calibration_stability_threshold = 0.1  # Seuil de stabilité des quaternions
        self.calibration_samples = []
        self.calibration_status_text = "🔴 Calibration requise - Placez-vous en T-pose"
        
        # Offset de calibration pour chaque partie du corps
        self.calibration_offsets = {}
                
    def _precalculate_animation(self, num_frames):
        """Precalculate animation frames with quaternion rotations and positions."""
        print(f"Precalculating {num_frames} animation frames in quaternions...")
        animation_frames = []
        identity_quat = np.array([1.0, 0.0, 0.0, 0.0])

        for i in range(num_frames):
            phase = (i / float(num_frames)) * 2 * math.pi
            
            # Calculate key angles for animation
            arm_swing_angle_rad = math.radians(45.0 * math.sin(phase))
            leg_swing_angle_left_rad = math.radians(40.0 * math.sin(phase))
            leg_swing_angle_right_rad = math.radians(40.0 * math.sin(phase + math.pi))
            
            torso_sway_offset = 0.05 * math.sin(phase)
            vertical_bounce_offset = 0.03 * math.sin(phase * 2.0)
            torso_rotation_angle_y_rad = math.radians(10.0 * math.sin(phase))
            
            head_rotation_angle_x_rad = math.radians(5.0 * math.sin(phase + 0.2))
            head_rotation_angle_y_rad = torso_rotation_angle_y_rad * 0.5
            head_rotation_angle_z_rad = math.radians(3.0 * math.sin(phase))

            # Initialize frame data for all body parts
            frame_data = {}
            for part_name in self.body_parts.keys():
                frame_data[part_name] = {
                    'pos_offset': np.array([0.0, 0.0, 0.0]), 
                    'rot_quat': identity_quat.copy()
                }

            # --- Positions ---
            # Torso and head - lateral sway and vertical bounce
            frame_data['torso']['pos_offset'][0] = torso_sway_offset
            frame_data['head']['pos_offset'][0] = torso_sway_offset * 1.1
            frame_data['neck']['pos_offset'][0] = torso_sway_offset * 1.05
            
            frame_data['torso']['pos_offset'][1] = vertical_bounce_offset
            frame_data['head']['pos_offset'][1] = vertical_bounce_offset * 1.2
            frame_data['neck']['pos_offset'][1] = vertical_bounce_offset * 1.1
            frame_data['hip']['pos_offset'][0] = torso_sway_offset * 0.5
            frame_data['hip']['pos_offset'][1] = vertical_bounce_offset

            # --- Arm movement positions ---
            # Forward/backward arm movement
            frame_data['left_hand']['pos_offset'][2] = -0.3 * math.sin(phase)
            frame_data['forearm_l']['pos_offset'][2] = -0.2 * math.sin(phase)
            frame_data['biceps_l']['pos_offset'][2] = -0.1 * math.sin(phase)
            
            frame_data['right_hand']['pos_offset'][2] = 0.3 * math.sin(phase)
            frame_data['forearm_r']['pos_offset'][2] = 0.2 * math.sin(phase)
            frame_data['biceps_r']['pos_offset'][2] = 0.1 * math.sin(phase)
            
            # --- Leg movement positions ---
            frame_data['left_foot']['pos_offset'][2] = 0.3 * math.sin(phase)
            frame_data['calves_l']['pos_offset'][2] = 0.2 * math.sin(phase)
            frame_data['quadriceps_l']['pos_offset'][2] = 0.1 * math.sin(phase)
            
            frame_data['right_foot']['pos_offset'][2] = -0.3 * math.sin(phase)
            frame_data['calves_r']['pos_offset'][2] = -0.2 * math.sin(phase)
            frame_data['quadriceps_r']['pos_offset'][2] = -0.1 * math.sin(phase)

            # --- Quaternion rotations ---
            # Torso rotation around Y-axis (yaw)
            if abs(torso_rotation_angle_y_rad) > 1e-6:
                frame_data['torso']['rot_quat'] = quaternion_from_axis_angle([0, 1, 0], torso_rotation_angle_y_rad)

            # Combined head rotation (pitch, yaw, roll)
            q_head_x = quaternion_from_axis_angle([1, 0, 0], head_rotation_angle_x_rad)
            q_head_y = quaternion_from_axis_angle([0, 1, 0], head_rotation_angle_y_rad)
            q_head_z = quaternion_from_axis_angle([0, 0, 1], head_rotation_angle_z_rad)
            combined_head_rot = quaternion_multiply(q_head_y, q_head_x)
            combined_head_rot = quaternion_multiply(combined_head_rot, q_head_z)
            frame_data['head']['rot_quat'] = combined_head_rot

            # Arm rotations (pitch - rotation around X)
            if abs(arm_swing_angle_rad) > 1e-6:
                left_arm_swing_q = quaternion_from_axis_angle([1, 0, 0], arm_swing_angle_rad)
                right_arm_swing_q = quaternion_from_axis_angle([1, 0, 0], -arm_swing_angle_rad)

                # Left arm
                for part in ['deltoid_l', 'biceps_l', 'forearm_l', 'left_hand']:
                    if part in frame_data:
                        frame_data[part]['rot_quat'] = left_arm_swing_q
                
                # Right arm
                for part in ['deltoid_r', 'biceps_r', 'forearm_r', 'right_hand']:
                    if part in frame_data:
                        frame_data[part]['rot_quat'] = right_arm_swing_q
            
            # Leg rotations (pitch - rotation around X)
            # Left leg
            if abs(leg_swing_angle_left_rad) > 1e-6:
                q_leg_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad)
                q_knee_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad * 0.5)
                q_foot_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad * 0.2)

                frame_data['quadriceps_l']['rot_quat'] = q_leg_l
                frame_data['ishcio_hamstrings_l']['rot_quat'] = q_leg_l
                frame_data['calves_l']['rot_quat'] = q_knee_l
                frame_data['left_foot']['rot_quat'] = q_foot_l
            
            # Right leg
            if abs(leg_swing_angle_right_rad) > 1e-6:
                q_leg_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad)
                q_knee_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad * 0.5)
                q_foot_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad * 0.2)

                frame_data['quadriceps_r']['rot_quat'] = q_leg_r
                frame_data['ishcio_hamstrings_r']['rot_quat'] = q_leg_r
                frame_data['calves_r']['rot_quat'] = q_knee_r
                frame_data['right_foot']['rot_quat'] = q_foot_r
            
            animation_frames.append(frame_data)
        
        print(f"Animation precalculation completed: {len(animation_frames)} frames.")
        return animation_frames

    def get_default_state(self, part_name):
        if part_name in self.initial_body_parts_state:
            return self.initial_body_parts_state[part_name]['pos'], self.initial_body_parts_state[part_name]['rot']
        return np.array([0, 0, 0]), np.array([1.0, 0, 0, 0])

    def update_animation_frame(self):
        """Updates the walking animation using pre-calculated frames."""
        if not self.walking:
            return
        
        try:
            # Check the availability of animation frames
            if not self.precalculated_animation_frames:
                print("No animation frames available")
                return
            
            # Increment frame index and limit it to available frames
            self.precalc_frame = (self.precalc_frame + 1) % self.num_precalc_frames
            
            # Check the index is valid
            if self.precalc_frame >= len(self.precalculated_animation_frames):
                print(f"Invalid frame index: {self.precalc_frame}, max is {len(self.precalculated_animation_frames)-1}")
                return
            
            # Retrieve current frame data
            current_frame_data = self.precalculated_animation_frames[self.precalc_frame]
            
            # Store currently mapped IMU body parts to preserve their rotations if they have active data
            imu_controlled_parts = set(self.imu_mapping.values())
            imu_rotations = {}
            for part_name in imu_controlled_parts:
                if part_name in self.body_parts:
                    # Sauvegarder seulement si des données IMU récentes ont été reçues (moins de 1 seconde)
                    imu_rotations[part_name] = self.body_parts[part_name]['rot'].copy()
            
            # Apply data to each body part
            for part_name, data in self.body_parts.items():
                # Ne pas sauter les parties du corps mappées aux IMUs, appliquer l'animation
                # et restaurer ensuite les rotations IMU si nécessaire
                if part_name in current_frame_data:
                    # Appliquer les offsets de position
                    data['pos'] = self.initial_body_parts_state[part_name]['pos'].copy()
                    if 'pos_offset' in current_frame_data[part_name]:
                        data['pos'] += current_frame_data[part_name]['pos_offset']
                    
                    # Appliquer les rotations d'animation sauf si la partie a des données IMU actives
                    if part_name not in imu_controlled_parts or part_name not in imu_rotations:
                        if 'rot_quat' in current_frame_data[part_name]:
                            data['rot'] = current_frame_data[part_name]['rot_quat'].copy()
            
            # Restore IMU-controlled part rotations if they have active data
            for part_name, rotation in imu_rotations.items():
                if part_name in self.body_parts:
                    # Ne restaurer que si les données IMU sont récentes
                    self.body_parts[part_name]['rot'] = rotation
            
            # If walking animation is active and using motion prediction, apply prediction
            # only to non-IMU parts
            if self.use_motion_prediction:
                try:
                    # Predict and apply movements of unmonitored parts
                    updated_body_parts = self.motion_predictor.predict_joint_movement(
                        self.body_parts, imu_controlled_parts, self.walking)
                    
                    # Apply predictions only to parts not controlled by IMUs
                    for part_name, data in updated_body_parts.items():
                        if part_name not in imu_controlled_parts and part_name in self.body_parts:
                            self.body_parts[part_name]['rot'] = data['rot']
                except Exception as e:
                    print(f"Error in motion prediction: {e}")
        
            self.update()
        except Exception as e:
            print(f"Error in update_animation_frame: {e}")
            traceback.print_exc()

    def toggle_walking(self):
        self.walking = not self.walking
        if self.walking:
            self.precalc_frame = 0
            self.animation_main_timer.start()
        else:
            self.animation_main_timer.stop()
            # Do NOT reset body parts when stopping animation
            # This preserves IMU-controlled positions
            self.update()
        return self.walking
    
    def reset_body_parts_to_initial_state(self):
        for part_name, initial_state in self.initial_body_parts_state.items():
            if part_name in self.body_parts:
                self.body_parts[part_name]['pos'] = initial_state['pos'].copy()
                self.body_parts[part_name]['rot'] = initial_state['rot'].copy()
        if not self.walking:
            self.safely_update_display_list()

    def reset_view(self):
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.camera_distance = 4.0  # Reset camera distance
        
        if self.walking:
            self.toggle_walking()
        
        self.reset_body_parts_to_initial_state()
            
        # Force a redraw
        self.update()
        print("3D view reset complete")

    def initializeGL(self):
        if self._initialized:
            print("Skipping redundant OpenGL initialization")
            return
            
        try:
            # First check if we can safely initialize
            if not self.isValid():
                print("Warning: Widget not valid during initializeGL")
                return
                
            # Set the initial background color to clearly indicate initialization progress
            try:
                self.makeCurrent()
                glClearColor(0.1, 0.1, 0.2, 1.0)  # Dark blue background
                self.doneCurrent()
            except Exception as e:
                print(f"Warning: Pre-initialization color setting failed: {e}")
            
            print("Initialize GL started - setting up OpenGL context")
            
            # Capture the context before proceeding with initialization
            if not self.context() or not self.context().isValid():
                print("ERROR: OpenGL context is not valid during initialization")
                return
                
            self.makeCurrent()
            
            # Initialize OpenGL components with careful error checking
            try:
                glClearColor(0.2, 0.2, 0.2, 1.0)  # Standard dark gray background
                glEnable(GL_DEPTH_TEST)
                glEnable(GL_CULL_FACE)
                
                glShadeModel(GL_SMOOTH)
                glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_FASTEST)
                glHint(GL_POLYGON_SMOOTH_HINT, GL_FASTEST)
                glDisable(GL_LIGHTING)
                glDisable(GL_DITHER)
                
                self.quadric = gluNewQuadric()
                if not self.quadric:
                    print("ERROR: Failed to create quadric object")
                else:
                    print("Quadric object created successfully")
                    gluQuadricDrawStyle(self.quadric, GLU_FILL)
                    gluQuadricNormals(self.quadric, GLU_SMOOTH)
            except OpenGL.error.GLError as e:
                print(f"ERROR during OpenGL state setup: {e}")
                
            # Make sure display list is initialized to 0
            self.display_list = 0
            
            # Defer resize and display list creation to the event queue
            # to ensure it happens after the context is fully established
            QTimer.singleShot(50, self.initialize_viewport_and_display_list)
            
            self.doneCurrent()
            print("Initialize GL completed - deferred viewport setup scheduled")
        
        except OpenGL.error.GLError as e:
            print(f"OpenGL initialization error: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"General error in initializeGL: {e}")
            import traceback
            traceback.print_exc()

    def initialize_viewport_and_display_list(self):
        """Deferred initialization for viewport and display list to ensure context is ready."""
        try:
            if not self.isValid() or not self.context() or not self.context().isValid():
                print("ERROR: Context not valid during deferred initialization")
                # Schedule another attempt if we're still in startup phase
                QTimer.singleShot(100, self.initialize_viewport_and_display_list)
                return
                
            self.makeCurrent()
            
            # Now setup the viewport with dimensions
            width, height = self.width(), self.height()
            print(f"Setting up viewport with dimensions: {width}x{height}")
            
            try:
                glViewport(0, 0, width, height)
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                
                aspect = width / float(max(1, height))  # Prevent division by zero
                gluPerspective(45.0, aspect, 0.1, 100.0)
                
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                
                print("Viewport setup complete")
            except OpenGL.error.GLError as e:
                print(f"ERROR during viewport setup: {e}")
            
            # Now create the display list
            try:
                print("Creating initial display list")
                if self.safely_update_display_list(force=True):
                    print(f"Display list created successfully, ID: {self.display_list}")
                else:
                    print("WARNING: Failed to create initial display list")
            except Exception as e:
                print(f"ERROR creating display list: {e}")
            
            self.doneCurrent()
            
            # Force a redraw
            self.update()
        except Exception as e:
            print(f"Error in initialize_viewport_and_display_list: {e}")
            import traceback
            traceback.print_exc()

    def paintGL(self):
        # Skip rendering if conditions aren't right
        if self.is_being_destroyed or not self.isVisible() or not self.is_visible_to_user:
            return
            
        try:
            # Make sure we have a valid context before proceeding
            if not self.context() or not self.context().isValid():
                if self.frame_count % 100 == 0:  # Limit log spam
                    print("Warning: Invalid OpenGL context during paint")
                return
                
            self.makeCurrent()
            self.frame_count += 1
            
            # Only log occasionally to reduce console spam
            if self.frame_count % 300 == 0:
                print(f"Rendering frame {self.frame_count}")
            
            try:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                glLoadIdentity()
                
                # Position the camera using the camera_distance parameter
                gluLookAt(0, 1.0, self.camera_distance, 0, 1.0, 0.0, 0, 1.0, 0.0)
                
                # Apply global rotations
                glRotatef(self.rotation_x, 1, 0, 0)
                glRotatef(self.rotation_y, 0, 1, 0)
                glRotatef(self.rotation_z, 0, 0, 1)
                
                # Draw the floor with transparency handling
                try:
                    glDepthMask(GL_FALSE)  # Disable depth writing for transparent floor
                    self.create_floor()
                    glDepthMask(GL_TRUE)   # Re-enable depth writing
                except Exception as e:
                    if self.frame_count % 100 == 0:  # Limit log spam
                        print(f"Error drawing floor: {e}")
                
                # Force direct drawing to ensure the model is visible
                self.draw_limbs_internal()
                self.draw_joints_internal()
                
                # Draw the legend UI elements
                try:
                    self._draw_legend()
                except Exception as e:
                    if self.frame_count % 100 == 0:  # Limit log spam
                        print(f"Error drawing legend: {e}")
                        
            except OpenGL.error.GLError as e:
                if self.frame_count % 30 == 0:  # Limit log spam
                    print(f"OpenGL error during rendering: {e}")
        except Exception as e:
            if self.frame_count % 30 == 0:  # Limit log spam
                print(f"General error in paintGL: {e}")
        finally:
            try:
                if not self.is_being_destroyed and self.isValid():
                    self.doneCurrent()
            except Exception:
                pass  # Suppress errors in cleanup

    def create_floor(self):
        """Draw a floor grid for reference."""
        # Use a lighter color with transparency for the floor
        glColor4f(0.3, 0.3, 0.3, 0.6)  # Darker with more transparency
        
        floor_size = 10.0
        grid_size = 0.5
        
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Draw floor surface
        glBegin(GL_QUADS)
        glVertex3f(-floor_size, 0, -floor_size)
        glVertex3f(-floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, -floor_size)
        glEnd()
        
        # Draw grid lines
        glLineWidth(1.0)
        glBegin(GL_LINES)
        
        glColor3f(0.5, 0.5, 0.5)
        for x in np.arange(-floor_size, floor_size + grid_size, grid_size):
            glVertex3f(x, 0.01, -floor_size)
            glVertex3f(x, 0.01, floor_size)
        
        for z in np.arange(-floor_size, floor_size + grid_size, grid_size):
            glVertex3f(-floor_size, 0.01, z)
            glVertex3f(floor_size, 0.01, z)
        
        glEnd()
        
        # Draw coordinate markers for reference
        self.draw_direction_marker(0, 0.02, 0, 1.5)
        self.draw_direction_marker(-floor_size + 0.5, 0.02, -floor_size + 0.5, 0.5)
        self.draw_direction_marker(floor_size - 0.5, 0.02, -floor_size + 0.5, 0.5)
        self.draw_direction_marker(-floor_size + 0.5, 0.02, floor_size - 0.5, 0.5)
        self.draw_direction_marker(floor_size - 0.5, 0.02, floor_size - 0.5, 0.5)

    def _draw_legend(self):
        """Draws a legend showing the different sensor types."""
        try:
            # Use QPainter for drawing text overlays
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            
            # Set up the font
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            
            # Draw legend title
            painter.setPen(Qt.white)
            painter.drawText(10, 20, "Legend:")
            
            # Draw sensor types with colors
            font.setBold(False)
            painter.setFont(font)
            
            # Correction: Le problème est que les coordonnées Y sont inversées par rapport au texte
            # QPainter utilise le coin supérieur gauche comme origine (0,0)
            
            # IMU sensors - green
            rect_height = 16
            rect_width = 24
            margin = 4
            
            base_y = 30  # Position Y de départ
            spacing = 20  # Espacement entre les lignes
            
            # IMU sensors - green (avec bordure pour une meilleure visibilité)
            painter.setPen(Qt.darkGray)  # Bordure grise foncée
            painter.setBrush(QColor(0, 204, 51, 255))  # Vert avec opacité complète
            painter.drawRect(10, base_y, rect_width, rect_height)
            
            painter.setPen(Qt.white)
            painter.drawText(10 + rect_width + margin, base_y + rect_height - 4, "IMU Sensors")
            
            # EMG sensors - red (avec bordure)
            painter.setPen(Qt.darkGray)
            painter.setBrush(QColor(204, 51, 0, 255))  # Rouge avec opacité complète
            painter.drawRect(10, base_y + spacing, rect_width, rect_height)
            
            painter.setPen(Qt.white)
            painter.drawText(10 + rect_width + margin, base_y + spacing + rect_height - 4, "EMG Sensors")
            
            # pMMG sensors - blue (avec bordure)
            painter.setPen(Qt.darkGray)
            painter.setBrush(QColor(0, 51, 204, 255))  # Bleu avec opacité complète
            painter.drawRect(10, base_y + spacing * 2, rect_width, rect_height)
            
            painter.setPen(Qt.white)
            painter.drawText(10 + rect_width + margin, base_y + spacing * 2 + rect_height - 4, "pMMG Sensors")
            
            # Show FPS counter if enabled
            if self.show_fps:
                fps_text = f"FPS: {self.fps}"
                text_width = 80
                painter.drawText(self.width() - text_width - 10, 20, fps_text)
            
            # Draw a border around the legend
            painter.setPen(QColor(180, 180, 180))
            legend_height = base_y + spacing * 2 + rect_height + 10
            painter.drawRect(5, 5, 150, legend_height)
            
            painter.end()
        except Exception as e:
            print(f"Error drawing legend: {e}")

    def set_color(self, r, g, b):
        """Set the color for the following vertices."""
        glColor3f(r, g, b)

    def set_normal(self, x, y, z):
        """Set the normal vector for the following vertices."""
        glNormal3f(x, y, z)

    def vertex(self, x, y, z):
        """Define a vertex for the following primitive."""
        glVertex3f(x, y, z)

    def draw_fps_counter(self):
        """Draw the FPS counter on the screen."""
        try:
            self.makeCurrent()
            painter = QPainter(self)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 10))
            
            # Afficher le texte avec un fond semi-transparent
            painter.setOpacity(0.7)
            painter.fillRect(10, 10, 100, 40, Qt.black)
            painter.setOpacity(1.0)
            
            # Calculer et afficher le FPS
            self.frame_count += 1
            if self.fps_timer.elapsed() > 1000:
                self.fps = self.frame_count
                self.frame_count = 0
                self.fps_timer.restart()
            
            painter.drawText(15, 25, f"FPS: {self.fps}")
            
            painter.end()
        except Exception as e:
            print(f"Error in draw_fps_counter: {e}")

    def update_fps(self):
        """Update the FPS counter."""
        self.frame_count += 1
        if self.fps_timer.elapsed() > 1000:
            self.fps = self.frame_count
            self.frame_count = 0
            self.fps_timer.restart()

    def closeEvent(self, event):
        """Handle the widget close event."""
        self.is_being_destroyed = True
        try:
            # Stop any ongoing timers
            self.animation_main_timer.stop()
            self.fps_update_timer.stop()
            
            # Perform any necessary cleanup here
            # For example, freeing OpenGL resources or stopping threads
            
            print("Cleanup before close")
        except Exception as e:
            print(f"Error during closeEvent cleanup: {e}")
            import traceback
            traceback.print_exc()
        
        event.accept()

    def check_opengl_state(self):
        """Check and print the current OpenGL state for debugging."""
        try:
            if not self.isValid() or not self.context() or not self.context().isValid():
                print("ERROR: OpenGL context is not valid")
                return
            
            self.makeCurrent()
            
            # Check some basic OpenGL states
            clear_color = glGetFloatv(GL_COLOR_CLEAR_VALUE)
            depth_func = glGetIntegerv(GL_DEPTH_FUNC)
            cull_face = glIsEnabled(GL_CULL_FACE)
            depth_test = glIsEnabled(GL_DEPTH_TEST)
            
            print(f"OpenGL State:")
            print(f"  Clear Color: {clear_color}")
            print(f"  Depth Func: {depth_func}")
            print(f"  Cull Face: {'Enabled' if cull_face else 'Disabled'}")
            print(f"  Depth Test: {'Enabled' if depth_test else 'Disabled'}")
            
            # You can add more state checks here as needed
            
            self.doneCurrent()
        except Exception as e:
            print(f"Error checking OpenGL state: {e}")
            import traceback
            traceback.print_exc()

    def get_calibration_status(self):
        """Returns current calibration status."""
        progress = 0
        if self.calibration_mode and len(self.calibration_samples) > 0:
            progress = min(100, (len(self.calibration_samples) * 100) // 30)
        elif self.calibration_complete:
            progress = 100
        
        return {
            'mode': self.calibration_mode,
            'complete': self.calibration_complete,
            'progress': progress,
            'status_text': self.calibration_status_text
        }

    def update_calibration_status(self):
        """Updates calibration status in real-time."""
        if not self.calibration_mode:
            return
        
        self.calibration_duration += 100
        
        # Collect current data from mapped IMUs
        current_sample = {}
        stability_check = True
        
        for imu_id, body_part in self.imu_mapping.items():
            if body_part in self.body_parts:
                current_quat = self.body_parts[body_part]['rot'].copy()
                current_sample[body_part] = current_quat
                
                # Check stability
                if len(self.calibration_samples) > 5:
                    last_sample = self.calibration_samples[-1].get(body_part)
                    if last_sample is not None:
                        # Calculate angular difference
                        diff = np.linalg.norm(current_quat - last_sample)
                        if diff > self.calibration_stability_threshold:
                            stability_check = False
        
        # Add sample if stable
        if stability_check and current_sample:
            self.calibration_samples.append(current_sample)
            
            # Update status text
            progress = min(100, (len(self.calibration_samples) * 100) // 30)  # 30 samples = 3 seconds
            self.calibration_status_text = f"🟡 Calibration: {progress}% - Maintain T-pose"
        else:
            # If not stable, slightly reduce samples
            if len(self.calibration_samples) > 2:
                self.calibration_samples = self.calibration_samples[:-1]
            self.calibration_status_text = "🟠 Move less - Keep T-pose stable"
        
        # Check if calibration is complete
        if len(self.calibration_samples) >= 30:  # 3 seconds of stable data
            self.stop_tpose_calibration()
        
        # Timeout after 30 seconds
        if self.calibration_duration > 30000:
            self.calibration_status_text = "⏰ Timeout - Restart calibration"
            self.calibration_mode = False
            self.calibration_timer.stop()
        
        self.update()

    def safely_update_display_list(self, force=False):
        """Updates the OpenGL display list with proper error checking."""
        # Don't update if widget is being destroyed
        if self.is_being_destroyed:
            return False
        
        if not hasattr(self, 'last_update_time'):
            self.last_update_time = 0
        
        try:
            current_time = self.fps_timer.elapsed()
            if not force and current_time - self.last_update_time < 100:
                return False
            
            self.last_update_time = current_time
            
            if not self.check_context():
                print("Warning: OpenGL context check failed in safely_update_display_list")
                return False
            
            try:
                self.makeCurrent()
                
                # We'll just skip display lists completely for now to ensure the model is visible
                print("Skipping display list creation - using direct rendering for stability")
                return True
                
            except OpenGL.error.GLError as e:
                print(f"[ERROR] OpenGL error in display list creation: {e}")
                self.display_list = 0
                return False
            finally:
                try:
                    if not self.is_being_destroyed and self.isValid() and self.context() and self.context().isValid():
                        self.doneCurrent()
                except Exception as e:
                    print(f"Error in doneCurrent: {e}")
        except Exception as e:
            print(f"General error in safely_update_display_list: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_context(self):
        """Checks if the OpenGL context is valid with detailed error reporting."""
        # Skip if widget is being destroyed
        if self.is_being_destroyed:
            return False
            
        try:
            if not hasattr(self, 'context'):
                print("Error: Widget has no OpenGL context attribute")
                return False
                
            if not self.isValid():
                print("Warning: OpenGL widget not valid")
                return False
            
            context = self.context()
            if not context:
                print("Error: Unable to get OpenGL context")
                return False
                
            if not context.isValid():
                print("Warning: OpenGL context not valid")
                reason = "Unknown reason"
                if hasattr(context, 'errorString'):
                    reason = context.errorString()
                print(f"Context invalid reason: {reason}")
                return False
        
            try:
                self.makeCurrent()
                return True
            except Exception as e:
                print(f"Error activating OpenGL context: {e}")
                return False
        except Exception as e:
            print(f"Exception in check_context: {e}")
            return False

    # Also need to add the missing draw_limbs_internal and draw_joints_internal methods
    def draw_limbs_internal(self):
        glLineWidth(4.0)  # Increased from 3.0 to make limbs more visible
        glBegin(GL_LINES)
        
        glColor3f(1.0, 0.8, 0.6)
        self.draw_line_from_parts('head', 'neck')
        
        glColor3f(0.2, 0.4, 0.8)
        self.draw_line_from_parts('neck', 'torso')
        self.draw_line_from_parts('torso', 'hip')
        
        glColor3f(0.0, 0.5, 1.0)
        self.draw_line_from_parts('neck', 'deltoid_l')
        self.draw_line_from_parts('deltoid_l', 'biceps_l')
        self.draw_line_from_parts('biceps_l', 'forearm_l')
        self.draw_line_from_parts('forearm_l', 'left_hand')
        self.draw_line_from_parts('torso', 'dorsalis_major_l')
        self.draw_line_from_parts('torso', 'pectorals_l')
        self.draw_line_from_parts('pectorals_l', 'deltoid_l')
        
        glColor3f(1.0, 0.5, 0.0)
        self.draw_line_from_parts('neck', 'deltoid_r')
        self.draw_line_from_parts('deltoid_r', 'biceps_r')
        self.draw_line_from_parts('biceps_r', 'forearm_r')
        self.draw_line_from_parts('forearm_r', 'right_hand')
        self.draw_line_from_parts('torso', 'dorsalis_major_r')
        self.draw_line_from_parts('torso', 'pectorals_r')
        self.draw_line_from_parts('pectorals_r', 'deltoid_r')
        
        glColor3f(0.0, 0.7, 0.3)
        self.draw_line_from_parts('hip', 'quadriceps_l')
        self.draw_line_from_parts('hip', 'glutes_l')
        self.draw_line_from_parts('hip', 'ishcio_hamstrings_l')
        self.draw_line_from_parts('quadriceps_l', 'calves_l')
        self.draw_line_from_parts('ishcio_hamstrings_l', 'calves_l')
        self.draw_line_from_parts('calves_l', 'left_foot')
        
        glColor3f(0.7, 0.0, 0.3)
        self.draw_line_from_parts('hip', 'quadriceps_r')
        self.draw_line_from_parts('hip', 'glutes_r')
        self.draw_line_from_parts('hip', 'ishcio_hamstrings_r')
        self.draw_line_from_parts('quadriceps_r', 'calves_r')
        self.draw_line_from_parts('ishcio_hamstrings_r', 'calves_r')
        self.draw_line_from_parts('calves_r', 'right_foot')
        
        glEnd()
    
    def draw_line_from_parts(self, part1, part2):
        p1 = self.body_parts[part1]['pos']
        p2 = self.body_parts[part2]['pos']
        glVertex3f(p1[0], p1[1], p1[2])
        glVertex3f(p2[0], p2[1], p2[2])

    def draw_joints_internal(self):
        """Draws joints with rotations via quaternions."""
        for part_name, data in self.body_parts.items():
            pos = data['pos']
            
            # Définir des tailles simplifiées et plus cohérentes pour le modèle
            # Réduction supplémentaire de la taille de la hanche
            joint_sizes = {
                # Tête et torse - plus grands
                'head': 0.114,      # Réduit de 0.12 à 0.114
                'neck': 0.076,      # Réduit de 0.08 à 0.076
                'torso': 0.114,     # Réduit de 0.12 à 0.114
                'hip': 0.06,        # Réduit davantage (0.077 à 0.06) - environ la moitié de la tête
                
                # Bras et jambes - taille moyenne
                'deltoid_l': 0.0665,  # Réduit de 0.07 à 0.0665
                'deltoid_r': 0.0665,  # Réduit de 0.07 à 0.0665
                'biceps_l': 0.0665,   # Réduit de 0.07 à 0.0665
                'biceps_r': 0.0665,   # Réduit de 0.07 à 0.0665
                'quadriceps_l': 0.0665, # Réduit de 0.07 à 0.0665
                'quadriceps_r': 0.0665, # Réduit de 0.07 à 0.0665
                
                # Articulations secondaires - plus petites
                'forearm_l': 0.057,   # Réduit de 0.06 à 0.057
                'forearm_r': 0.057,   # Réduit de 0.06 à 0.057
                'calves_l': 0.057,    # Réduit de 0.06 à 0.057
                'calves_r': 0.057,    # Réduit de 0.06 à 0.057
                
                # Extrémités - très petites
                'left_hand': 0.0475,  # Réduit de 0.05 à 0.0475
                'right_hand': 0.0475, # Réduit de 0.05 à 0.0475
                'left_foot': 0.0475,  # Réduit de 0.05 à 0.0475
                'right_foot': 0.0475, # Réduit de 0.05 à 0.0475
                
                # Autres parties (valeur par défaut également réduite)
                'dorsalis_major_l': 0.057,
                'dorsalis_major_r': 0.057,
                'pectorals_l': 0.057,
                'pectorals_r': 0.057,
                'glutes_l': 0.057,
                'glutes_r': 0.057,
                'ishcio_hamstrings_l': 0.057,
                'ishcio_hamstrings_r': 0.057
            }
            
            # Taille par défaut pour les parties non spécifiées
            sphere_size = joint_sizes.get(part_name, 0.057)  # Réduits de 0.06 à 0.057
            
            # Obtenez le type de capteur mappé
            sensor_type = self._get_mapped_sensor_type(part_name)
            
            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])
            
            # Appliquer la rotation
            rot = data['rot']
            if not np.array_equal(rot, [1.0, 0.0, 0.0, 0.0]):
                matrix = quaternion_to_matrix(rot)
                glMultMatrixf(matrix)
            
            # Couleurs plus vives et distinctes
            if sensor_type == "IMU":
                glColor3f(0, 0.9, 0.3)  # Vert plus vif
            elif sensor_type == "EMG":
                glColor3f(0.9, 0.2, 0)  # Rouge plus vif
            elif sensor_type == "pMMG":
                glColor3f(0.1, 0.4, 0.9)  # Bleu plus vif
            else:
                glColor3f(0.75, 0.75, 0.75)  # Gris clair
            
            # Réduire la qualité des sphères pour plus de performance
            gluSphere(self.quadric, sphere_size, 12, 12)  # Réduits de 16,16 à 12,12
            glPopMatrix()

    def _get_mapped_sensor_type(self, part_name):
        for imu_id, mapped_part in self.imu_mapping.items():
            if mapped_part == part_name:
                return "IMU"
        
        if hasattr(self, 'emg_mapping'):
            for emg_id, mapped_part in self.emg_mapping.items():
                if mapped_part == part_name:
                    return "EMG"
                    
        if hasattr(self, 'pmmg_mapping'):
            for pmmg_id, mapped_part in self.pmmg_mapping.items():
                if mapped_part == part_name:
                    return "pMMG"
        
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()
            self.mouse_pressed = True
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = False
    
    def mouseMoveEvent(self, event):
        if self.mouse_pressed and self.last_pos:
            dx = event.x() - self.last_pos.x()
            dy = event.y() - self.last_pos.y()
            
            # Update rotation based on mouse movement
            self.rotation_y += dx * 0.5  # horizontal movement controls y-rotation
            self.rotation_x += dy * 0.5  # vertical movement controls x-rotation
            
            # Keep rotations within reasonable bounds
            self.rotation_x = max(-90, min(90, self.rotation_x))
            
            self.last_pos = event.pos()
            self.update()  # Trigger a redraw

    def wheelEvent(self, event):
        # Implement zoom with mouse wheel
        zoom_factor = event.angleDelta().y() / 120.0  # 120 units per wheel notch
        # Zoom by changing the camera position in gluLookAt
        # We'll adjust this in paintGL by modifying the camera distance
        self.camera_distance = max(1.5, min(10.0, self.camera_distance - zoom_factor * 0.5))
        self.update()

    def map_imu_to_body_part(self, imu_id, body_part):
        """Maps an IMU sensor to a body part."""
        print(f"Mapping IMU {imu_id} to {body_part}")
        
        # Handle legacy mappings (convert old names to new ones)
        if body_part in self.legacy_mappings:
            body_part = self.legacy_mappings[body_part]
            print(f"Using legacy mapping: {body_part}")
        
        # Verify body part exists in our model
        if body_part not in self.body_parts:
            print(f"WARNING: Body part '{body_part}' not found in model")
            return False
        
        # Update the mapping
        self.imu_mapping[imu_id] = body_part
        
        # Force update of the display list to show the new mapping
        # Réduire les mises à jour de display list qui causent des problèmes
        # Mettre à jour seulement si le widget est visible
        if self.isVisible() and self.is_visible_to_user:
            self.safely_update_display_list(force=True)
            self.update()
        return True
    
    def apply_imu_data(self, imu_id, quaternion_data):
        """Applies IMU quaternion data to the mapped body part."""
        if imu_id not in self.imu_mapping:
            return False
            
        body_part = self.imu_mapping[imu_id]
        if body_part not in self.body_parts:
            return False
            
        # Normalize the quaternion to ensure valid rotation
        normalized_quat = normalize_quaternion(quaternion_data)
        
        # Apply calibration if available
        if self.calibration_complete and body_part in self.calibration_offsets:
            # Rotation finale = rotation de calibration * rotation IMU
            offset_quat = self.calibration_offsets[body_part]
            final_quat = quaternion_multiply(offset_quat, normalized_quat)
            self.body_parts[body_part]['rot'] = final_quat
        else:
            # Appliquer directement la rotation IMU
            self.body_parts[body_part]['rot'] = normalized_quat
            
        # Marquer cette partie du corps comme ayant des données IMU récentes
        if not hasattr(self, 'imu_data_timestamp'):
            self.imu_data_timestamp = {}
        self.imu_data_timestamp[body_part] = time.time()
            
        return True
    
    def get_current_mappings(self):
        """Returns the current IMU to body part mappings."""
        return self.imu_mapping

    def set_emg_mapping(self, emg_mapping):
        """Set EMG sensor mappings."""
        self.emg_mapping = emg_mapping
        
    def set_pmmg_mapping(self, pmmg_mapping):
        """Set pMMG sensor mappings."""
        self.pmmg_mapping = pmmg_mapping
    
    def start_tpose_calibration(self):
        """Start T-pose calibration."""
        if not self.imu_mapping:
            print("Cannot start calibration - no IMUs are mapped")
            return False
            
        print("Starting T-pose calibration...")
        self.calibration_mode = True
        self.calibration_complete = False
        self.calibration_samples = []
        self.calibration_duration = 0
        self.calibration_status_text = "Starting calibration - Assume T-pose and hold still"
        
        # Start the timer for regular status updates
        self.calibration_timer.start(100)  # 100ms interval
        return True
        
    def stop_tpose_calibration(self):
        """Stop T-pose calibration and calculate offsets."""
        if not self.calibration_mode:
            return False
            
        self.calibration_timer.stop()
        self.calibration_mode = False
        
        # Check if we have enough data
        if len(self.calibration_samples) < 10:
            print("Insufficient calibration data collected")
            self.calibration_status_text = "Calibration failed - insufficient data"
            return False
            
        # Calculate the average quaternion for each body part
        average_quats = {}
        for body_part in self.imu_mapping.values():
            samples = []
            for sample in self.calibration_samples:
                if body_part in sample:
                    samples.append(sample[body_part])
            
            if samples:
                # Simple averaging for quaternions (not ideal but works for small variations)
                avg_quat = np.mean(samples, axis=0)
                avg_quat = normalize_quaternion(avg_quat)
                average_quats[body_part] = avg_quat
        
        # Now calculate the offset quaternions 
        # The offset is what needs to be applied to go from the calibrated T-pose to the ideal T-pose
        self.calibration_offsets = {}
        for body_part, avg_quat in average_quats.items():
            # For a T-pose, we'd expect identity quaternion in the ideal case
            # So the offset is the inverse of the average quaternion
            # For quaternions, the inverse is the conjugate when normalized
            w, x, y, z = avg_quat
            # Conjugate: w, -x, -y, -z
            offset_quat = normalize_quaternion(np.array([w, -x, -y, -z]))
            self.calibration_offsets[body_part] = offset_quat
        
        self.calibration_complete = True
        self.calibration_status_text = "✅ Calibration complete - T-pose correction active"
        print(f"Calibration complete for {len(self.calibration_offsets)} body parts")
        
        # Apply calibration to current pose
        for imu_id, body_part in self.imu_mapping.items():
            if body_part in self.body_parts and body_part in self.calibration_offsets:
                current_quat = self.body_parts[body_part]['rot']
                offset_quat = self.calibration_offsets[body_part]
                corrected_quat = quaternion_multiply(current_quat, offset_quat)
                self.body_parts[body_part]['rot'] = corrected_quat
        
        # Update the display
        self.safely_update_display_list(force=True)
        self.update()
        return True
    
    def reset_calibration(self):
        """Reset calibration data."""
        self.calibration_mode = False
        self.calibration_complete = False
        self.calibration_timer.stop()
        self.calibration_samples = []
        self.calibration_offsets = {}
        self.calibration_status_text = "🔄 Calibration reset - No correction active"
        
        # Update the display
        self.safely_update_display_list(force=True)
        self.update()
        return True

    def draw_direction_marker(self, x, y, z, size=1.0):
        """Draws a direction marker at the specified position."""
        glPushMatrix()
        glTranslatef(x, y, z)
        
        # X axis - Red
        glColor3f(1.0, 0.0, 0.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(size, 0, 0)
        glEnd()
        
        # Y axis - Green
        glColor3f(0.0, 1.0, 0.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, size, 0)
        glEnd()
        
        # Z axis - Blue
        glColor3f(0.0, 0.0, 1.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, size)
        glEnd()
        
        glPopMatrix()
