import sys
import os
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtOpenGL import QGLWidget, QGLFormat
from PyQt5.QtGui import QFont, QPainter
from OpenGL.GL import *
from OpenGL.GLU import *
import math
from utils.body_motion_predictor import MotionPredictorFactory

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
    """Convertit un quaternion en matrice de rotation 4x4 (format OpenGL)"""
    w, x, y, z = q
    x2, y2, z2, w2 = x*x, y*y, z*z, w*w
    xy, xz, yz = x*y, x*z, y*z
    wx, wy, wz = w*x, w*y, w*z

    # Format compatible avec OpenGL - ordre colonne-major
    m = np.array([
        [1-2*(y2+z2),   2*(xy-wz),    2*(xz+wy),  0],
        [2*(xy+wz),   1-2*(x2+z2),    2*(yz-wx),  0],
        [2*(xz-wy),     2*(yz+wx),  1-2*(x2+y2),  0],
        [0,             0,            0,          1]
    ], dtype=np.float32).flatten(order='F')  # 'F' correspond à l'ordre colonne-major pour OpenGL
    
    return m

class Model3DViewer(QGLWidget):
    def __init__(self, parent=None):
        fmt = QGLFormat()
        fmt.setDoubleBuffer(True)
        fmt.setSampleBuffers(True)
        fmt.setSwapInterval(1)
        super().__init__(fmt, parent)
        
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        
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
        
        # Initialiser le prédicteur de mouvement
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                 'data', 'motion_model.pth')
        self.motion_predictor = MotionPredictorFactory.create_predictor("simple", model_path)
        self.use_motion_prediction = True  # Activer par défaut
                
    def _precalculate_animation(self, num_frames):
        """Precalculate animation frames with quaternion rotations and positions."""
        print(f"Précalcul des {num_frames} frames d'animation en quaternions...")
        animation_frames = []
        identity_quat = np.array([1.0, 0.0, 0.0, 0.0])

        for i in range(num_frames):
            phase = (i / float(num_frames)) * 2 * math.pi
            
            # Calculs des angles clés pour l'animation
            arm_swing_angle_rad = math.radians(45.0 * math.sin(phase))
            leg_swing_angle_left_rad = math.radians(40.0 * math.sin(phase))
            leg_swing_angle_right_rad = math.radians(40.0 * math.sin(phase + math.pi))
            
            torso_sway_offset = 0.05 * math.sin(phase)
            vertical_bounce_offset = 0.03 * math.sin(phase * 2.0)
            torso_rotation_angle_y_rad = math.radians(10.0 * math.sin(phase))
            
            head_rotation_angle_x_rad = math.radians(5.0 * math.sin(phase + 0.2))
            head_rotation_angle_y_rad = torso_rotation_angle_y_rad * 0.5
            head_rotation_angle_z_rad = math.radians(3.0 * math.sin(phase))

            # Initialisation des données de frame pour toutes les parties du corps
            frame_data = {}
            for part_name in self.body_parts.keys():
                frame_data[part_name] = {
                    'pos_offset': np.array([0.0, 0.0, 0.0]), 
                    'rot_quat': identity_quat.copy()
                }

            # --- Positions ---
            # Torse et tête - oscillation latérale et rebond vertical
            frame_data['torso']['pos_offset'][0] = torso_sway_offset
            frame_data['head']['pos_offset'][0] = torso_sway_offset * 1.1
            frame_data['neck']['pos_offset'][0] = torso_sway_offset * 1.05
            
            frame_data['torso']['pos_offset'][1] = vertical_bounce_offset
            frame_data['head']['pos_offset'][1] = vertical_bounce_offset * 1.2
            frame_data['neck']['pos_offset'][1] = vertical_bounce_offset * 1.1
            frame_data['hip']['pos_offset'][0] = torso_sway_offset * 0.5
            frame_data['hip']['pos_offset'][1] = vertical_bounce_offset

            # --- Position des bras en mouvement ---
            # Mouvement avant/arrière des bras
            frame_data['left_hand']['pos_offset'][2] = -0.3 * math.sin(phase)
            frame_data['forearm_l']['pos_offset'][2] = -0.2 * math.sin(phase)
            frame_data['biceps_l']['pos_offset'][2] = -0.1 * math.sin(phase)
            
            frame_data['right_hand']['pos_offset'][2] = 0.3 * math.sin(phase)
            frame_data['forearm_r']['pos_offset'][2] = 0.2 * math.sin(phase)
            frame_data['biceps_r']['pos_offset'][2] = 0.1 * math.sin(phase)
            
            # --- Position des jambes en mouvement ---
            frame_data['left_foot']['pos_offset'][2] = 0.3 * math.sin(phase)
            frame_data['calves_l']['pos_offset'][2] = 0.2 * math.sin(phase)
            frame_data['quadriceps_l']['pos_offset'][2] = 0.1 * math.sin(phase)
            
            frame_data['right_foot']['pos_offset'][2] = -0.3 * math.sin(phase)
            frame_data['calves_r']['pos_offset'][2] = -0.2 * math.sin(phase)
            frame_data['quadriceps_r']['pos_offset'][2] = -0.1 * math.sin(phase)

            # --- Rotations en quaternions ---
            # Rotation du torse autour de l'axe Y (yaw)
            if abs(torso_rotation_angle_y_rad) > 1e-6:
                frame_data['torso']['rot_quat'] = quaternion_from_axis_angle([0, 1, 0], torso_rotation_angle_y_rad)

            # Rotation combinée de la tête (pitch, yaw, roll)
            q_head_x = quaternion_from_axis_angle([1, 0, 0], head_rotation_angle_x_rad)
            q_head_y = quaternion_from_axis_angle([0, 1, 0], head_rotation_angle_y_rad)
            q_head_z = quaternion_from_axis_angle([0, 0, 1], head_rotation_angle_z_rad)
            combined_head_rot = quaternion_multiply(q_head_y, q_head_x)
            combined_head_rot = quaternion_multiply(combined_head_rot, q_head_z)
            frame_data['head']['rot_quat'] = combined_head_rot

            # Rotation des bras (pitch - rotation autour de X)
            if abs(arm_swing_angle_rad) > 1e-6:
                left_arm_swing_q = quaternion_from_axis_angle([1, 0, 0], arm_swing_angle_rad)
                right_arm_swing_q = quaternion_from_axis_angle([1, 0, 0], -arm_swing_angle_rad)

                # Bras gauche
                for part in ['deltoid_l', 'biceps_l', 'forearm_l', 'left_hand']:
                    if part in frame_data:
                        frame_data[part]['rot_quat'] = left_arm_swing_q
                
                # Bras droit
                for part in ['deltoid_r', 'biceps_r', 'forearm_r', 'right_hand']:
                    if part in frame_data:
                        frame_data[part]['rot_quat'] = right_arm_swing_q
            
            # Rotation des jambes (pitch - rotation autour de X)
            # Jambe gauche
            if abs(leg_swing_angle_left_rad) > 1e-6:
                q_leg_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad)
                q_knee_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad * 0.5)
                q_foot_l = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_left_rad * 0.2)

                frame_data['quadriceps_l']['rot_quat'] = q_leg_l
                frame_data['ishcio_hamstrings_l']['rot_quat'] = q_leg_l
                frame_data['calves_l']['rot_quat'] = q_knee_l
                frame_data['left_foot']['rot_quat'] = q_foot_l
            
            # Jambe droite
            if abs(leg_swing_angle_right_rad) > 1e-6:
                q_leg_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad)
                q_knee_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad * 0.5)
                q_foot_r = quaternion_from_axis_angle([1, 0, 0], leg_swing_angle_right_rad * 0.2)

                frame_data['quadriceps_r']['rot_quat'] = q_leg_r
                frame_data['ishcio_hamstrings_r']['rot_quat'] = q_leg_r
                frame_data['calves_r']['rot_quat'] = q_knee_r
                frame_data['right_foot']['rot_quat'] = q_foot_r
            
            animation_frames.append(frame_data)
        
        print(f"Animation précalculée terminée: {len(animation_frames)} frames.")
        return animation_frames

    def get_default_state(self, part_name):
        if part_name in self.initial_body_parts_state:
            return self.initial_body_parts_state[part_name]['pos'], self.initial_body_parts_state[part_name]['rot']
        return np.array([0, 0, 0]), np.array([1.0, 0, 0, 0])

    def update_animation_frame(self):
        """Met à jour l'animation de marche en utilisant les frames pré-calculées."""
        if not self.walking:
            return
        
        # Vérifier la disponibilité des frames d'animation
        if not self.precalculated_animation_frames:
            print("Erreur: Aucune frame d'animation précalculée disponible.")
            return
        
        # Incrémenter l'index de frame et le limiter au nombre de frames disponibles
        self.precalc_frame = (self.precalc_frame + 1) % self.num_precalc_frames
        
        # Vérifier que l'index est valide
        if self.precalc_frame >= len(self.precalculated_animation_frames):
            print(f"Erreur: Index de frame {self.precalc_frame} hors limites (max: {len(self.precalculated_animation_frames)-1})")
            self.precalc_frame = 0  # Réinitialiser à 0 pour éviter une erreur
        
        # Récupérer les données de la frame courante
        current_frame_data = self.precalculated_animation_frames[self.precalc_frame]
        
        # Appliquer les données à chaque partie du corps
        for part_name, data in self.body_parts.items():
            # Vérifier que cette partie existe dans les données de frame
            if part_name in current_frame_data:
                # Récupérer la position et rotation de base (sans animation)
                base_pos, _ = self.get_default_state(part_name)
                
                # Récupérer les offsets et rotations de l'animation
                anim_data = current_frame_data[part_name]
                pos_offset = anim_data.get('pos_offset', np.array([0.0, 0.0, 0.0]))
                rot_quat = anim_data.get('rot_quat', np.array([1.0, 0.0, 0.0, 0.0]))
                
                # Appliquer les offsets de position à la position de base
                data['pos'] = base_pos + pos_offset
                
                # Appliquer le quaternion de rotation directement
                data['rot'] = rot_quat.copy()  # Copie importante pour éviter les références partagées
        
        # Si l'animation de marche n'est pas active, appliquer la prédiction de mouvement
        if self.use_motion_prediction and not self.walking:
            # Identifier les parties du corps surveillées par des IMUs
            monitored_parts = set()
            for imu_id, body_part in self.imu_mapping.items():
                monitored_parts.add(body_part)
            
            # Prédire et appliquer les mouvements des parties non surveillées
            updated_body_parts = self.motion_predictor.predict_joint_movement(
                self.body_parts, monitored_parts, self.walking)
            
            # Appliquer les prédictions
            for part_name, data in updated_body_parts.items():
                if part_name not in monitored_parts:
                    self.body_parts[part_name]['rot'] = data['rot']
        
        self.update()

    def toggle_walking(self):
        self.walking = not self.walking
        if self.walking:
            self.precalc_frame = 0
            self.animation_main_timer.start()
        else:
            self.animation_main_timer.stop()
            self.reset_body_parts_to_initial_state()
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
        
        if self.walking:
            self.toggle_walking()
        else:
            self.reset_body_parts_to_initial_state()
            
        self.update()

    def initializeGL(self):
        try:
            self.makeCurrent()
            
            glClearColor(0.2, 0.2, 0.2, 1.0)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_CULL_FACE)
            
            glShadeModel(GL_SMOOTH)
            glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_FASTEST)
            glHint(GL_POLYGON_SMOOTH_HINT, GL_FASTEST)
            glDisable(GL_LIGHTING)
            glDisable(GL_DITHER)
            
            self.quadric = gluNewQuadric()
            gluQuadricDrawStyle(self.quadric, GLU_FILL)
            gluQuadricNormals(self.quadric, GLU_SMOOTH)
            
            self.safely_update_display_list()
            
            self.update()
        
        except OpenGL.error.GLError as e:
            print(f"OpenGL initialization error: {e}")

    def create_floor(self):
        glColor3f(0.3, 0.3, 0.3)
        
        floor_size = 10.0
        grid_size = 0.5
        
        glBegin(GL_QUADS)
        glVertex3f(-floor_size, 0, -floor_size)
        glVertex3f(-floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, -floor_size)
        glEnd()
        
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
        
        self.draw_direction_marker(0, 0.02, 0, 1.5)
        
        self.draw_direction_marker(-floor_size + 0.5, 0.02, -floor_size + 0.5, 0.5)
        self.draw_direction_marker(floor_size - 0.5, 0.02, -floor_size + 0.5, 0.5)
        self.draw_direction_marker(-floor_size + 0.5, 0.02, floor_size - 0.5, 0.5)
        self.draw_direction_marker(floor_size - 0.5, 0.02, floor_size - 0.5, 0.5)

    def draw_direction_marker(self, x, y, z, size):
        glBegin(GL_LINES)
        
        glColor3f(0.0, 0.7, 0.0)
        glVertex3f(x, y, z)
        glVertex3f(x, y, z + size)
        
        glVertex3f(x, y, z + size)
        glVertex3f(x - size/5, y, z + size - size/5)
        
        glVertex3f(x, y, z + size)
        glVertex3f(x + size/5, y, z + size - size/5)
        
        glColor3f(0.7, 0.0, 0.0)
        glVertex3f(x, y, z)
        glVertex3f(x + size, y, z)
        
        glVertex3f(x + size, y, z)
        glVertex3f(x + size - size/5, y, z - size/5)
        
        glVertex3f(x + size, y, z)
        glVertex3f(x + size - size/5, y, z + size/5)
        
        glEnd()

    def safely_update_display_list(self):
        if not hasattr(self, 'last_update_time'):
            self.last_update_time = 0
        
        current_time = self.fps_timer.elapsed()
        if current_time - self.last_update_time < 100:
            return
        
        self.last_update_time = current_time
        
        if not self.check_context():
            return
        
        try:
            self.makeCurrent()
            
            if hasattr(self, 'display_list') and self.display_list != 0:
                try:
                    glDeleteLists(self.display_list, 1)
                except OpenGL.error.GLError:
                    print("Warning: Failed to delete previous display list")
            
            self.display_list = glGenLists(1)
            if self.display_list == 0:
                print("Error: Could not generate a valid display list ID")
                return
                
            glNewList(self.display_list, GL_COMPILE)
            self.draw_limbs_internal()
            self.draw_joints_internal()
            glEndList()
            
        except OpenGL.error.GLError as e:
            print(f"OpenGL error in safely_update_display_list: {e}")
            self.display_list = 0
        finally:
            self.doneCurrent()

    def resizeGL(self, width, height):
        if width <= 0 or height <= 0:
            return
            
        try:
            self.makeCurrent()
            
            glViewport(0, 0, width, height)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            aspect = width / float(height) if height > 0 else 1.0
            gluPerspective(45.0, aspect, 0.1, 100.0)
            glMatrixMode(GL_MODELVIEW)
        except OpenGL.error.GLError as e:
            print(f"OpenGL resize error: {e}")
        except Exception as e:
            print(f"Error in resizeGL: {e}")

    def paintGL(self):
        """Rendu de la scène OpenGL."""
        if not self.isValid() or not self.context().isValid():
            print("Warning: OpenGL context not valid during paint")
            return
        
        try:
            self.makeCurrent()
            self.frame_count += 1
            
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
            
            gluLookAt(0, 1.0, 5.0, 0, 1.0, 0.0, 0, 1.0, 0.0)
            
            # Rotation globale de la vue
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)
            glRotatef(self.rotation_z, 0, 0, 1)
            
            # Dessiner le sol
            self.create_floor()
            
            # Choisir la méthode de rendu en fonction du mode d'animation
            if self.walking:
                # En mode animation, dessiner directement pour une meilleure fluidité
                # et pour éviter d'avoir à recréer la display list à chaque frame
                self.draw_limbs_internal()
                self.draw_joints_internal()
            else:
                # Sinon utiliser la display list (plus performant)
                if hasattr(self, 'display_list') and self.display_list != 0:
                    try:
                        glCallList(self.display_list)
                    except OpenGL.error.GLError as e:
                        print(f"Error drawing model: {e}")
                        # Fallback en cas d'erreur
                        self.draw_limbs_internal()
                        self.draw_joints_internal()
                else:
                    # Si la display list n'est pas disponible, dessiner directement
                    self.draw_limbs_internal()
                    self.draw_joints_internal()
            
            # Afficher la légende
            self._draw_legend()
        except OpenGL.error.GLError as e:
            print(f"OpenGL rendering error: {e}")

    def draw_limbs_internal(self):
        glLineWidth(3.0)
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
        """Dessine les articulations avec rotations via quaternions."""
        for part_name, data in self.body_parts.items():
            pos = data['pos']
            quat_rotation = data['rot']
            
            glPushMatrix()
            # Déplacement à la position de la partie du corps
            glTranslatef(pos[0], pos[1], pos[2])
            
            # Application de la rotation quaternion via une matrice
            try:
                rotation_matrix = quaternion_to_matrix(quat_rotation)
                glMultMatrixf(rotation_matrix)
            except Exception as e:
                print(f"Error applying rotation for {part_name}: {e}")
                # En cas d'erreur, ne pas appliquer de rotation
            
            # Déterminer la couleur de l'articulation selon le type de capteur
            sensor_type = self._get_mapped_sensor_type(part_name)
            
            if sensor_type == "IMU":
                glColor3f(0.0, 0.8, 0.2)  # Vert
            elif sensor_type == "EMG":
                glColor3f(0.8, 0.2, 0.0)  # Rouge
            elif sensor_type == "pMMG":
                glColor3f(0.0, 0.2, 0.8)  # Bleu
            else:
                glColor3f(0.9, 0.9, 0.9)  # Gris

            # Dessiner la sphère de l'articulation
            if self.quadric:
                if part_name == 'head':
                    gluSphere(self.quadric, 0.15, 12, 12)  # Tête plus grosse
                else:
                    gluSphere(self.quadric, 0.05, 6, 6)  # Autres articulations
            
            # Ajouter une étiquette si c'est un capteur
            if sensor_type:
                model = glGetDoublev(GL_MODELVIEW_MATRIX)
                proj = glGetDoublev(GL_PROJECTION_MATRIX)
                view = glGetIntegerv(GL_VIEWPORT)
                win_x, win_y, win_z = gluProject(0, 0, 0, model, proj, view)
                if not hasattr(self, 'labels'):
                    self.labels = []
                self.labels.append((win_x, self.height() - win_y, f"{sensor_type}", sensor_type))
            
            glPopMatrix()
    
    def draw_limbs(self):
        self.safely_update_display_list()
        self.update()
    
    def update_fps(self):
        elapsed = self.fps_timer.elapsed()
        if elapsed > 0:
            self.fps = int((self.frame_count * 1000) / elapsed)
            self.frame_count = 0
            self.fps_timer.restart()
    
    def mousePressEvent(self, event):
        self.last_pos = event.pos()
        
    def mouseMoveEvent(self, event):
        if not self.last_pos:
            return
            
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()
        
        if event.buttons() & Qt.LeftButton:
            self.rotation_x += dy
            self.rotation_y += dx
            self.update()
            
        self.last_pos = event.pos()
    
    def apply_imu_data(self, imu_id, quaternion_data):
        """Applique les données IMU (quaternion) à une partie du corps."""
        if not self.isValid() or not self.context().isValid():
            print("Warning: OpenGL context not valid in apply_imu_data")
            return False
        
        try:
            # Déterminer quelle partie du corps est associée à cet IMU
            body_part_name = self.get_body_part_for_sensor('IMU', imu_id)
            
            if not body_part_name or body_part_name not in self.body_parts:
                print(f"Warning: IMU ID {imu_id} not mapped or body part '{body_part_name}' unknown.")
                return False
            
            # Vérifications de validité des données
            if not isinstance(quaternion_data, (list, np.ndarray)):
                print(f"Warning: Quaternion data for IMU {imu_id} is not a list or numpy array.")
                return False
            if len(quaternion_data) != 4:
                print(f"Warning: Quaternion data for IMU {imu_id} does not have 4 components.")
                return False

            # Normaliser le quaternion pour assurer une rotation correcte
            norm_quat = normalize_quaternion(np.array(quaternion_data))
            
            # Appliquer le quaternion normalisé à la partie du corps
            self.body_parts[body_part_name]['rot'] = norm_quat
            
            # Si l'animation n'est pas active, reconstruire la display list
            if not self.walking:
                self.safely_update_display_list()
            
            # Appliquer la prédiction de mouvement après avoir traité les données IMU
            if self.use_motion_prediction and not self.walking:
                # Identifier les parties du corps surveillées par des IMUs
                monitored_parts = set()
                for imu_id, body_part in self.imu_mapping.items():
                    monitored_parts.add(body_part)
                
                # Prédire et appliquer les mouvements des parties non surveillées
                updated_body_parts = self.motion_predictor.predict_joint_movement(
                    self.body_parts, monitored_parts, self.walking)
                
                # Appliquer les prédictions
                for part_name, data in updated_body_parts.items():
                    if part_name not in monitored_parts:
                        self.body_parts[part_name]['rot'] = data['rot']
                
                # Si l'animation n'est pas active, reconstruire la display list
                if not self.walking:
                    self.safely_update_display_list()
            
            # Demander une mise à jour du rendu
            self.update()
            return True
        except Exception as e:
            print(f"Error in apply_imu_data for IMU {imu_id}: {e}")
            return False
    
    def map_imu_to_body_part(self, imu_id, body_part):
        """Map an IMU sensor to a body part."""
        if body_part not in self.body_parts and body_part not in self.legacy_mappings:
            print(f"Warning: Body part '{body_part}' not found in model")
            return False
        
        if body_part in self.legacy_mappings:
            body_part = self.legacy_mappings[body_part]
        
        # Stocker le mapping
        self.imu_mapping[imu_id] = body_part
        return True
    
    def get_body_part_for_sensor(self, sensor_type, sensor_id):
        """Retourne la partie du corps associée à un capteur spécifique.
        
        Args:
            sensor_type (str): Type de capteur ('IMU', 'EMG', 'pMMG')
            sensor_id (int): ID du capteur
            
        Returns:
            str: Nom de la partie du corps associée, ou None si aucun mapping
        """
        if sensor_type == 'IMU':
            if sensor_id in self.imu_mapping:
                return self.imu_mapping[sensor_id]
        elif sensor_type == 'EMG':
            if hasattr(self, 'emg_mapping') and sensor_id in self.emg_mapping:
                return self.emg_mapping[sensor_id]
        elif sensor_type == 'pMMG':
            if hasattr(self, 'pmmg_mapping') and sensor_id in self.pmmg_mapping:
                return self.pmmg_mapping[sensor_id]
        
        print(f"Warning: No mapping found for {sensor_type} {sensor_id}")
        return None

    def get_available_body_parts(self):
        return list(self.body_parts.keys())
        
    def get_current_mappings(self):
        return self.imu_mapping.copy()
        
    def load_external_model(self, file_path):
        if not os.path.exists(file_path):
            return False
            
        try:
            import trimesh
            mesh = trimesh.load(file_path)
            
            self.external_mesh = mesh
            
            self._map_body_parts_to_model()
            
            self.update()
            
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
        
    def _map_body_parts_to_model(self):
        if hasattr(self, 'external_mesh'):
            vertices = np.array(self.external_mesh.vertices)
            
            min_y = np.min(vertices[:, 1])
            max_y = np.max(vertices[:, 1])
            height = max_y - min_y
            
            self.body_parts['head']['pos'] = [0, min_y + height * 0.9, 0]
            self.body_parts['neck']['pos'] = [0, min_y + height * 0.85, 0]
            self.body_parts['torso']['pos'] = [0, min_y + height * 0.7, 0]
        
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

    def set_emg_mapping(self, emg_mapping):
        self.emg_mapping = emg_mapping
        self.update()

    def set_pmmg_mapping(self, pmmg_mapping):
        self.pmmg_mapping = pmmg_mapping
        self.update()

    def _draw_legend(self):
        self.renderText(10, 20, "Legend:", QFont("Arial", 10, QFont.Bold))
        self.renderText(60, 45, "IMU Sensors", QFont("Arial", 9))
        self.renderText(60, 65, "EMG Sensors", QFont("Arial", 9))
        self.renderText(60, 85, "pMMG Sensors", QFont("Arial", 9))
        
        if self.show_fps:
            fps_text = f"FPS: {self.fps:.1f}"
            text_width = 80
            self.renderText(self.width() - text_width - 10, 20, fps_text, QFont("Arial", 10, QFont.Bold))
        
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width(), 0, self.height(), -1, 1)
        
        glBegin(GL_QUADS)
        glColor3f(0.0, 0.8, 0.2)
        glVertex2f(30, self.height() - 45)
        glVertex2f(50, self.height() - 45)
        glVertex2f(50, self.height() - 35)
        glVertex2f(30, self.height() - 35)
        
        glColor3f(0.8, 0.2, 0.0)
        glVertex2f(30, self.height() - 65)
        glVertex2f(50, self.height() - 65)
        glVertex2f(50, self.height() - 55)
        glVertex2f(30, self.height() - 55)
        
        glColor3f(0.0, 0.2, 0.8)
        glVertex2f(30, self.height() - 85)
        glVertex2f(50, self.height() - 85)
        glVertex2f(50, self.height() - 75)
        glVertex2f(30, self.height() - 75)
        glEnd()
        
        glColor3f(0.7, 0.7, 0.7)
        glBegin(GL_LINE_LOOP)
        glVertex2f(5, self.height() - 95)
        glVertex2f(180, self.height() - 95)
        glVertex2f(180, self.height() - 5)
        glVertex2f(5, self.height() - 5)
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def check_context(self):
        if not self.isValid():
            print("Warning: OpenGL widget not valid")
            return False
        
        if not self.context().isValid():
            print("Warning: OpenGL context not valid")
            return False
    
        try:
            self.makeCurrent()
            return True
        except Exception as e:
            print(f"Error activating OpenGL context: {e}")
            return False

    def toggle_motion_prediction(self):
        """Active ou désactive la prédiction de mouvement."""
        self.use_motion_prediction = not self.use_motion_prediction
        return self.use_motion_prediction

    def __del__(self):
        try:
            if self.isValid() and self.context().isValid():
                self.makeCurrent()
                if hasattr(self, 'display_list') and self.display_list:
                    glDeleteLists(self.display_list, 1)
                self.doneCurrent()
        except Exception as e:
            pass

class Model3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.model_viewer = Model3DViewer()
        layout.addWidget(self.model_viewer)
        self.setLayout(layout)
        
    def update_rotation(self, x, y, z):
        self.model_viewer.rotation_x = x
        self.model_viewer.rotation_y = y
        self.model_viewer.rotation_z = z
        self.model_viewer.update()
    
    def toggle_animation(self):
        return self.model_viewer.toggle_walking()
        
    def apply_imu_data(self, imu_id, quaternion):
        return self.model_viewer.apply_imu_data(imu_id, quaternion)
        
    def map_imu_to_body_part(self, imu_id, body_part):
        return self.model_viewer.map_imu_to_body_part(imu_id, body_part)
        
    def get_available_body_parts(self):
        return self.model_viewer.get_available_body_parts()
        
    def get_current_mappings(self):
        return self.model_viewer.get_current_mappings()
        
    def get_emg_mappings(self):
        return getattr(self.model_viewer, 'emg_mapping', {}).copy()
    
    def get_pmmg_mappings(self):
        return getattr(self.model_viewer, 'pmmg_mapping', {}).copy()
        
    def reset_view(self):
        self.model_viewer.reset_view()
    
    def load_external_model(self, file_path):
        return self.model_viewer.load_external_model(file_path)
    
    def update_sensor_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        self.emg_mappings = emg_mappings
        self.imu_mappings = imu_mappings
        self.pmmg_mappings = pmmg_mappings
        
        self.model_viewer.set_emg_mapping(emg_mappings)
        self.model_viewer.set_pmmg_mapping(pmmg_mappings)
        self.model_viewer.imu_mapping = imu_mappings.copy()
        
        QTimer.singleShot(500, self.model_viewer.safely_update_display_list)

    def toggle_motion_prediction(self):
        """Active ou désactive la prédiction de mouvement."""
        return self.model_viewer.toggle_motion_prediction()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Model3DWidget()
    window.show()
    sys.exit(app.exec_())
