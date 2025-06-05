import sys
import os
import math
import numpy as np
import traceback

# Add required PyQt5 imports
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtOpenGL import QGLWidget, QGLFormat
from PyQt5.QtGui import QFont, QPainter, QColor

# Add OpenGL imports
try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
except ImportError:
    print("Warning: OpenGL not available. 3D model will not function.")

# Add parent directory to path for proper module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.body_motion_predictor import MotionPredictorFactory

# Define module-level variables to avoid NameError
stability_check = True  # Default: stability check is on. Set to False if not needed.
current_sample = None    # Default: no current sample. Initialize as appropriate for your application.

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
        if self.model_viewer.calibration_mode:
            print("[WARNING] T-pose calibration already in progress")
            return False
        
        if not self.model_viewer.imu_mapping:
            print("[WARNING] No IMU mappings defined. Cannot start calibration.")
            return False
        
        print("[INFO] Starting T-pose calibration")
        self.model_viewer.calibration_mode = True
        self.model_viewer.calibration_complete = False
        self.model_viewer.calibration_duration = 0
        self.model_viewer.calibration_samples = []
        self.model_viewer.calibration_status_text = "🟡 Waiting for stable T-pose position"
        
        # Start the calibration timer
        self.model_viewer.calibration_timer.start(100)
        
        # Set calibration state for UI feedback
        self.model_viewer.calibration_progress = 0
        
        print("[INFO] T-pose calibration started")
        return True

    def stop_tpose_calibration(self):
        """Stop T-pose calibration."""
        if not self.model_viewer.calibration_mode and not self.model_viewer.calibration_complete:
            print("[WARNING] No T-pose calibration in progress")
            return False
        
        # Force completion with current samples
        if self.model_viewer.calibration_mode:
            if self.model_viewer.calibration_samples:
                self.model_viewer.compute_calibration_offsets()
                self.model_viewer.calibration_complete = True
                self.model_viewer.calibration_status_text = "🟢 Calibration complete!"
            else:
                self.model_viewer.calibration_status_text = "🔴 Calibration failed - no samples"
        
        # Stop the calibration timer
        self.model_viewer.calibration_timer.stop()
        self.model_viewer.calibration_mode = False
        
        return self.model_viewer.calibration_complete

    def reset_calibration(self):
        """Reset calibration state."""
        if hasattr(self, 'model_viewer'):
            self.model_viewer.calibration_mode = False
            self.model_viewer.calibration_complete = False
            self.model_viewer.calibration_samples = []
            self.model_viewer.calibration_offsets = {}
            self.model_viewer.calibration_status_text = "🔴 Calibration required"
            if hasattr(self.model_viewer, 'calibration_timer'):
                self.model_viewer.calibration_timer.stop()

    def update_calibration_status(self):
        """Updates calibration status in real-time."""
        if not self.calibration_mode:
            return
        
        self.calibration_duration += 100
        
        # Collect current data from mapped IMUs
        current_sample = {}
        stability_check = True  # Initialize stability check as True
        
        # Check if we have any IMU mappings
        if not self.imu_mapping:
            print("[ERROR] No IMU mappings defined. Stopping calibration.")
            self.calibration_timer.stop()
            self.calibration_mode = False
            return
        
        for imu_id, body_part in self.imu_mapping.items():
            if body_part in self.body_parts:
                # Get current rotation for this body part
                current_rotation = self.body_parts[body_part]['rot']
                
                # Add to current sample
                if current_rotation is not None:
                    current_sample[body_part] = current_rotation.copy()
                    
                    # Check stability if we have previous samples
                    if len(self.calibration_samples) > 0:
                        # Get last sample for this body part
                        last_sample = self.calibration_samples[-1].get(body_part)
                        if last_sample is not None:
                            # Calculate difference between current and last rotation
                            diff = sum(abs(a - b) for a, b in zip(current_rotation, last_sample))
                            
                            # If difference is too large, pose is not stable
                            if diff > self.calibration_stability_threshold:
                                stability_check = False
                                break

        # Add sample if stable
        if stability_check and current_sample:
            self.calibration_samples.append(current_sample)
            progress = min(100, int((len(self.calibration_samples) / 30) * 100))
            self.calibration_status_text = f"🟡 Hold T-pose... {progress}%"
            print(f"[INFO] Calibration progress: {progress}%")
        else:
            # If not stable, give feedback
            self.calibration_status_text = "🟠 Movement detected. Please hold T-pose still."
            print("[INFO] Movement detected during calibration")
        
        # Check if calibration is complete
        if len(self.calibration_samples) >= 30:
            self.compute_calibration_offsets()
            self.calibration_timer.stop()
            self.calibration_mode = False
            self.calibration_complete = True
            self.calibration_status_text = "🟢 Calibration complete! T-pose reference saved."
            print("[INFO] T-pose calibration completed successfully")
        
        # Timeout after 30 seconds
        if self.calibration_duration > 30000:
            self.calibration_timer.stop()
            self.calibration_mode = False
            self.calibration_status_text = "🔴 Calibration timed out. Please try again."
            print("[WARNING] T-pose calibration timed out")
        
        # Force update to show calibration progress
        self.update()

    def compute_calibration_offsets(self):
        """Computes calibration offsets from collected samples."""
        if not self.calibration_samples:
            print("[ERROR] No calibration samples to compute offsets from")
            return
        
        self.calibration_offsets = {}
        
        # Compute average quaternion for each body part
        for body_part in self.body_parts:
            samples = []
            for sample in self.calibration_samples:
                if body_part in sample:
                    samples.append(sample[body_part])
            
            if samples:
                # Calculate average quaternion (simple average for now)
                avg_quat = [0, 0, 0, 0]
                for quat in samples:
                    for i in range(4):
                        avg_quat[i] += quat[i]
                
                for i in range(4):
                    avg_quat[i] /= len(samples)
                
                # Normalize the average quaternion
                self.calibration_offsets[body_part] = normalize_quaternion(avg_quat)
        
        print(f"[INFO] Calibration offsets computed for {len(self.calibration_offsets)} body parts")

    def get_current_mappings(self):
        """Returns the current IMU to body part mappings."""
        return self.model_viewer.imu_mapping

    def set_emg_mapping(self, emg_mapping):
        """Sets the EMG to body part mappings."""
        self.model_viewer.emg_mapping = emg_mapping
        
    def set_pmmg_mapping(self, pmmg_mapping):
        """Sets the pMMG to body part mappings."""
        self.model_viewer.pmmg_mapping = pmmg_mapping

    def get_calibration_status(self):
        """Returns current calibration status."""
        progress = 0
        if self.model_viewer.calibration_mode and len(self.model_viewer.calibration_samples) > 0:
            progress = min(100, int((len(self.model_viewer.calibration_samples) / 30) * 100))
        elif self.model_viewer.calibration_complete:
            progress = 100
        
        return {
            'mode': self.model_viewer.calibration_mode,
            'complete': self.model_viewer.calibration_complete,
            'progress': progress,
            'status_text': self.model_viewer.calibration_status_text
        }

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
        fmt.setAlpha(True)
        
        try:
            fmt.setVersion(2, 1)
            fmt.setProfile(QGLFormat.CompatibilityProfile)
        except:
            pass
        
        super().__init__(fmt, parent)
        
        # Initialize all required attributes
        self.is_being_destroyed = False
        self._initialized = False
        self.is_visible_to_user = True
        
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        self.mouse_pressed = False
        
        self.camera_distance = 3.5
        
        self.animation_phase = 0
        self.walking = False
        
        self.fps_timer = QElapsedTimer()
        self.fps_timer.start()
        self.frame_count = 0
        self.fps = 0
        self.show_fps = True

        identity_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Initialize body parts dictionary
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
        self.emg_mapping = {}
        self.pmmg_mapping = {}
        
        # Initialize motion predictor
        base_dir = os.path.dirname(os.path.dirname(__file__))
        model_path = os.path.join(base_dir, 'data', 'motion_model.pth')
        
        self.motion_predictor = MotionPredictorFactory.create_predictor("simple", model_path)
        self.use_motion_prediction = True
        
        # Calibration state
        self.calibration_mode = False
        self.calibration_complete = False
        self.calibration_reference = {}
        self.calibration_timer = QTimer(self)
        self.calibration_timer.timeout.connect(self.update_calibration_status)
        self.calibration_duration = 0
        self.calibration_required_time = 3000
        self.calibration_stability_threshold = 0.1
        self.calibration_samples = []
        self.calibration_status_text = "🔴 Calibration requise - Placez-vous en T-pose"
        self.calibration_offsets = {}

    def _precalculate_animation(self, num_frames):
        """Precalculate animation frames"""
        return []

    def get_default_state(self, part_name):
        """Get default state for a body part"""
        if part_name in self.initial_body_parts_state:
            return self.initial_body_parts_state[part_name]['pos'], self.initial_body_parts_state[part_name]['rot']
        return np.array([0, 0, 0]), np.array([1.0, 0, 0, 0])

    def update_animation_frame(self):
        """Update animation frame"""
        pass

    def toggle_walking(self):
        """Toggle walking animation"""
        self.walking = not self.walking
        return self.walking
    
    def reset_body_parts_to_initial_state(self):
        """Reset body parts to initial state"""
        for part_name, initial_state in self.initial_body_parts_state.items():
            if part_name in self.body_parts:
                self.body_parts[part_name]['pos'] = initial_state['pos'].copy()
                self.body_parts[part_name]['rot'] = initial_state['rot'].copy()

    def reset_view(self):
        """Reset view"""
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.camera_distance = 4.0

    def initializeGL(self):
        """Initialize OpenGL"""
        if self._initialized:
            return
        try:
            glClearColor(0.0, 0.0, 0.0, 0.0)
            glEnable(GL_DEPTH_TEST)
            self._initialized = True
        except Exception as e:
            print(f"Error initializing OpenGL: {e}")

    def initialize_viewport_and_display_list(self):
        """Initialize viewport and display list"""
        pass

    def paintGL(self):
        """Paint OpenGL scene"""
        if self.is_being_destroyed or not self.isVisible():
            return
        try:
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            # Basic rendering would go here
        except Exception as e:
            print(f"Error in paintGL: {e}")

    def create_floor(self):
        """Create floor"""
        pass

    def draw_direction_marker(self, x, y, z, size=1.0):
        """Draw direction marker"""
        pass
    
    def get_current_mappings(self):
        """Get current mappings"""
        return self.imu_mapping

    def set_emg_mapping(self, emg_mapping):
        """Set EMG mapping"""
        self.emg_mapping = emg_mapping
        
    def set_pmmg_mapping(self, pmmg_mapping):
        """Set pMMG mapping"""
        self.pmmg_mapping = pmmg_mapping

    def _draw_legend(self):
        """Draw legend"""
        pass

    def set_color(self, r, g, b):
        """Set color"""
        glColor3f(r, g, b)

    def set_normal(self, x, y, z):
        """Set normal"""
        glNormal3f(x, y, z)

    def vertex(self, x, y, z):
        """Set vertex"""
        glVertex3f(x, y, z)

    def draw_fps_counter(self):
        """Draw FPS counter"""
        pass

    def update_fps(self):
        """Update FPS"""
        pass

    def closeEvent(self, event):
        """Close event"""
        event.accept()

    def check_opengl_state(self):
        """Check OpenGL state"""
        pass

    def get_calibration_status(self):
        """Get calibration status"""
        progress = 0
        if self.calibration_mode and len(self.calibration_samples) > 0:
            progress = min(100, int((len(self.calibration_samples) / 30) * 100))
        elif self.calibration_complete:
            progress = 100
        
        return {
            'mode': self.calibration_mode,
            'complete': self.calibration_complete,
            'progress': progress,
            'status_text': self.calibration_status_text
        }

    def safely_update_display_list(self, force=False):
        """Safely update display list"""
        pass

    def check_context(self):
        """Check context"""
        pass

    def draw_limbs_internal(self):
        """Draw limbs internal"""
        pass
    
    def draw_line_from_parts(self, part1, part2):
        """Draw line from parts"""
        pass

    def draw_joints_internal(self):
        """Draw joints internal"""
        pass

    def _get_mapped_sensor_type(self, part_name):
        """Get mapped sensor type"""
        return None

    def mousePressEvent(self, event):
        """Mouse press event"""
        pass
    
    def mouseReleaseEvent(self, event):
        """Mouse release event"""
        pass
    
    def mouseMoveEvent(self, event):
        """Mouse move event"""
        pass

    def wheelEvent(self, event):
        """Wheel event"""
        pass

    def map_imu_to_body_part(self, imu_id, body_part):
        """Map IMU to body part"""
        self.imu_mapping[imu_id] = body_part
        return True
    
    def apply_imu_data(self, imu_id, quaternion_data):
        """Apply IMU data"""
        try:
            if imu_id in self.imu_mapping:
                body_part = self.imu_mapping[imu_id]
                if body_part in self.body_parts:
                    self.body_parts[body_part]['rot'] = np.array(quaternion_data)
                    return True
        except Exception as e:
            print(f"Error applying IMU data: {e}")
        return False

    def update_calibration_status(self):
        """Update calibration status"""
        if not self.calibration_mode:
            return
        
        self.calibration_duration += 100
        
        # Simplified calibration logic
        current_sample = {}
        stability_check = True
        
        if not self.imu_mapping:
            print("[ERROR] No IMU mappings defined. Stopping calibration.")
            self.calibration_timer.stop()
            self.calibration_mode = False
            return
        
        for imu_id, body_part in self.imu_mapping.items():
            if body_part in self.body_parts:
                current_rotation = self.body_parts[body_part]['rot']
                if current_rotation is not None:
                    current_sample[body_part] = current_rotation.copy()
        
        if stability_check and current_sample:
            self.calibration_samples.append(current_sample)
            progress = min(100, int((len(self.calibration_samples) / 30) * 100))
            self.calibration_status_text = f"🟡 Hold T-pose... {progress}%"
        else:
            self.calibration_status_text = "🟠 Movement detected. Please hold T-pose still."
        
        if len(self.calibration_samples) >= 30:
            self.compute_calibration_offsets()
            self.calibration_timer.stop()
            self.calibration_mode = False
            self.calibration_complete = True
            self.calibration_status_text = "🟢 Calibration complete!"
        
        if self.calibration_duration > 30000:
            self.calibration_timer.stop()
            self.calibration_mode = False
            self.calibration_status_text = "🔴 Calibration timed out."

    def compute_calibration_offsets(self):
        """Compute calibration offsets"""
        if not self.calibration_samples:
            print("[ERROR] No calibration samples to compute offsets from")
            return
        
        self.calibration_offsets = {}
        
        for body_part in self.body_parts:
            samples = []
            for sample in self.calibration_samples:
                if body_part in sample:
                    samples.append(sample[body_part])
            
            if samples:
                avg_quat = [0, 0, 0, 0]
                for quat in samples:
                    for i in range(4):
                        avg_quat[i] += quat[i]
                
                for i in range(4):
                    avg_quat[i] /= len(samples)
                
                self.calibration_offsets[body_part] = normalize_quaternion(avg_quat)
        
        print(f"[INFO] Calibration offsets computed for {len(self.calibration_offsets)} body parts")