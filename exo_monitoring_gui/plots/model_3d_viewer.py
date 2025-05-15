import sys
import os
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtOpenGL import QGLWidget, QGLFormat
from OpenGL.GL import *
from OpenGL.GLU import *
import math

class Model3DViewer(QGLWidget):
    def __init__(self, parent=None):
        # Format OpenGL optimisé
        fmt = QGLFormat()
        fmt.setDoubleBuffer(True)
        fmt.setSampleBuffers(True)
        fmt.setSwapInterval(1)  # Activer V-sync pour une animation plus fluide
        super().__init__(fmt, parent)
        
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        
        # Animation parameters
        self.animation_phase = 0
        self.walking = False
        
        # Compteur de FPS
        self.fps_timer = QElapsedTimer()
        self.fps_timer.start()
        self.frame_count = 0
        self.fps = 0
        
        # Body part positions and rotations
        self.body_parts = {
            # Head/Neck/Torso
            'head': {'pos': [0, 1.7, 0], 'rot': [0, 0, 0]},
            'neck': {'pos': [0, 1.5, 0], 'rot': [0, 0, 0]},
            'torso': {'pos': [0, 0.9, 0], 'rot': [0, 0, 0]},
            
            # Upper body - Left
            'deltoid_l': {'pos': [-0.15, 1.4, 0], 'rot': [0, 0, 0]},
            'biceps_l': {'pos': [-0.3, 1.3, 0], 'rot': [0, 0, 0]},
            'forearm_l': {'pos': [-0.4, 1.1, 0], 'rot': [0, 0, 0]},
            'dorsalis_major_l': {'pos': [-0.1, 1.2, 0], 'rot': [0, 0, 0]},
            'pectorals_l': {'pos': [-0.1, 1.3, 0], 'rot': [0, 0, 0]},
            'left_hand': {'pos': [-0.5, 0.8, 0], 'rot': [0, 0, 0]},
            
            # Upper body - Right
            'deltoid_r': {'pos': [0.15, 1.4, 0], 'rot': [0, 0, 0]},
            'biceps_r': {'pos': [0.3, 1.3, 0], 'rot': [0, 0, 0]},
            'forearm_r': {'pos': [0.4, 1.1, 0], 'rot': [0, 0, 0]},
            'dorsalis_major_r': {'pos': [0.1, 1.2, 0], 'rot': [0, 0, 0]},
            'pectorals_r': {'pos': [0.1, 1.3, 0], 'rot': [0, 0, 0]},
            'right_hand': {'pos': [0.5, 0.8, 0], 'rot': [0, 0, 0]},
            
            # Lower body
            'hip': {'pos': [0, 0.9, 0], 'rot': [0, 0, 0]},
            'quadriceps_l': {'pos': [-0.15, 0.7, 0], 'rot': [0, 0, 0]},
            'quadriceps_r': {'pos': [0.15, 0.7, 0], 'rot': [0, 0, 0]},
            'ishcio_hamstrings_l': {'pos': [-0.15, 0.6, 0], 'rot': [0, 0, 0]},
            'ishcio_hamstrings_r': {'pos': [0.15, 0.6, 0], 'rot': [0, 0, 0]},
            'calves_l': {'pos': [-0.2, 0.3, 0], 'rot': [0, 0, 0]},
            'calves_r': {'pos': [0.2, 0.3, 0], 'rot': [0, 0, 0]},
            'glutes_l': {'pos': [-0.15, 0.8, 0], 'rot': [0, 0, 0]},
            'glutes_r': {'pos': [0.15, 0.8, 0], 'rot': [0, 0, 0]},
            'left_foot': {'pos': [-0.2, 0.0, 0], 'rot': [0, 0, 0]},
            'right_foot': {'pos': [0.2, 0.0, 0], 'rot': [0, 0, 0]}
        }
        
        # IMU mapping dict - maps IMU ID to body part
        self.imu_mapping = {
            1: 'torso',
            2: 'forearm_l',     # Changed from 'left_elbow' to 'forearm_l'
            3: 'forearm_r',     # Changed from 'right_elbow' to 'forearm_r'
            4: 'calves_l',      # Changed from 'left_knee' to 'calves_l'
            5: 'calves_r',      # Changed from 'right_knee' to 'calves_r'
            6: 'head'
        }
        
        # Précalculer les animations pour optimisation
        self.num_precalc_frames = 120
        self.precalculated_positions = self._precalculate_animation(self.num_precalc_frames)
        self.precalc_frame = 0
        
        # Optimisations pour OpenGL
        self.display_list = None
        self.quadric = None
        
        # Remplacer AnimationThread par QTimer
        self.animation_main_timer = QTimer(self)
        self.animation_main_timer.timeout.connect(self.update_animation_frame)
        self.animation_main_timer.setInterval(16)  # Intervalle en ms

        # Timer pour mesure de FPS
        self.fps_update_timer = QTimer(self)
        self.fps_update_timer.timeout.connect(self.update_fps)
        self.fps_update_timer.start(1000)  # Mise à jour FPS chaque seconde
                
    def _precalculate_animation(self, num_frames):
        """Precalculate animation positions for optimal performance"""
        positions = []
        for i in range(num_frames):
            phase = (i / float(num_frames)) * 2 * math.pi
            arm_swing = 0.2 * math.sin(phase)
            leg_swing = 0.2 * math.sin(phase)
            
            frame_offsets = {
                'forearm_l_z': arm_swing,          # Changed from 'left_elbow_z'
                'forearm_r_z': -arm_swing,         # Changed from 'right_elbow_z'
                'left_hand_z': arm_swing * 1.5,
                'right_hand_z': -arm_swing * 1.5,
                'calves_l_z': -leg_swing,          # Changed from 'left_knee_z'
                'calves_r_z': leg_swing,           # Changed from 'right_knee_z'
                'left_foot_z': -leg_swing * 1.5,
                'right_foot_z': leg_swing * 1.5
            }
            positions.append(frame_offsets)
            
        return positions
                
    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        
        glShadeModel(GL_SMOOTH)
        glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_FASTEST)
        glHint(GL_POLYGON_SMOOTH_HINT, GL_FASTEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        
        self.quadric = gluNewQuadric()
        gluQuadricDrawStyle(self.quadric, GLU_FILL)
        gluQuadricNormals(self.quadric, GLU_SMOOTH)
        
        self.create_display_list()
        
    def create_display_list(self):
        """Créer un display list pour accélérer le rendu"""
        if self.display_list:
            glDeleteLists(self.display_list, 1)
            
        self.display_list = glGenLists(1)
        glNewList(self.display_list, GL_COMPILE)
        
        glPushMatrix()
        glTranslatef(*self.body_parts['head']['pos'])
        gluSphere(self.quadric, 0.15, 12, 12)
        glPopMatrix()
        
        glEndList()
        
    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = width / float(height)
        gluPerspective(45.0, aspect, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
    
    def paintGL(self):
        self.frame_count += 1
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        gluLookAt(0, 1.0, 5.0,
                 0, 1.0, 0.0,
                 0, 1.0, 0.0)
        
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        glRotatef(self.rotation_z, 0, 0, 1)
        
        if self.display_list is not None:
            glCallList(self.display_list)
        
        self.draw_limbs()
        self.draw_joints()
        
        self.renderText(10, self.height() - 20, f"FPS: {self.fps}")
    
    def draw_limbs(self):
        """Draw the limbs of the body using immediate mode OpenGL."""
        glLineWidth(3.0)
        glBegin(GL_LINES)
        
        # Head and neck
        glColor3f(1.0, 0.8, 0.6)
        self.draw_line_from_parts('head', 'neck')
        
        # Torso connections
        glColor3f(0.2, 0.4, 0.8)
        self.draw_line_from_parts('neck', 'torso')
        
        # Left arm muscle groups
        glColor3f(0.0, 0.5, 1.0)  # Blue for left side
        self.draw_line_from_parts('neck', 'deltoid_l')
        self.draw_line_from_parts('deltoid_l', 'biceps_l')
        self.draw_line_from_parts('biceps_l', 'forearm_l')
        self.draw_line_from_parts('forearm_l', 'left_hand')
        self.draw_line_from_parts('torso', 'dorsalis_major_l')
        self.draw_line_from_parts('torso', 'pectorals_l')
        self.draw_line_from_parts('pectorals_l', 'deltoid_l')
        
        # Right arm muscle groups
        glColor3f(1.0, 0.5, 0.0)  # Orange for right side
        self.draw_line_from_parts('neck', 'deltoid_r')
        self.draw_line_from_parts('deltoid_r', 'biceps_r')
        self.draw_line_from_parts('biceps_r', 'forearm_r')
        self.draw_line_from_parts('forearm_r', 'right_hand')
        self.draw_line_from_parts('torso', 'dorsalis_major_r')
        self.draw_line_from_parts('torso', 'pectorals_r')
        self.draw_line_from_parts('pectorals_r', 'deltoid_r')
        
        # Lower body - left side
        glColor3f(0.0, 0.7, 0.3)  # Green for left leg
        self.draw_line_from_parts('hip', 'quadriceps_l')
        self.draw_line_from_parts('hip', 'glutes_l')
        self.draw_line_from_parts('hip', 'ishcio_hamstrings_l')
        self.draw_line_from_parts('quadriceps_l', 'calves_l')
        self.draw_line_from_parts('ishcio_hamstrings_l', 'calves_l')
        self.draw_line_from_parts('calves_l', 'left_foot')
        
        # Lower body - right side
        glColor3f(0.7, 0.0, 0.3)  # Red for right leg
        self.draw_line_from_parts('hip', 'quadriceps_r')
        self.draw_line_from_parts('hip', 'glutes_r')
        self.draw_line_from_parts('hip', 'ishcio_hamstrings_r')
        self.draw_line_from_parts('quadriceps_r', 'calves_r')
        self.draw_line_from_parts('ishcio_hamstrings_r', 'calves_r')
        self.draw_line_from_parts('calves_r', 'right_foot')
        
        glEnd()
    
    def draw_line_from_parts(self, part1, part2):
        """Dessiner une ligne entre deux parties du corps"""
        p1 = self.body_parts[part1]['pos']
        p2 = self.body_parts[part2]['pos']
        glVertex3f(p1[0], p1[1], p1[2])
        glVertex3f(p2[0], p2[1], p2[2])
    
    def draw_joints(self):
        """Dessiner les articulations avec une complexité réduite"""
        for part_name, data in self.body_parts.items():
            pos = data['pos']
            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])

            # Vérifie si un capteur est assigné à cette partie
            mapped = any(mapped_part == part_name for mapped_part in self.imu_mapping.values())
            if mapped:
                glColor3f(0.0, 0.8, 0.2)  # Vert si capteur assigné
            else:
                glColor3f(0.9, 0.9, 0.9)  # Gris sinon

            if self.quadric:
                gluSphere(self.quadric, 0.05, 6, 6)
            glPopMatrix()
    
    def update_animation_frame(self):
        """Update walking animation on each QTimer tick."""
        if not self.walking:
            return
        
        self.precalc_frame = (self.precalc_frame + 1) % self.num_precalc_frames
        frame_offsets = self.precalculated_positions[self.precalc_frame]
        
        # Update these references to match the new keys
        self.body_parts['forearm_l']['pos'][2] = frame_offsets['forearm_l_z']
        self.body_parts['forearm_r']['pos'][2] = frame_offsets['forearm_r_z']
        self.body_parts['left_hand']['pos'][2] = frame_offsets['left_hand_z']
        self.body_parts['right_hand']['pos'][2] = frame_offsets['right_hand_z']
        self.body_parts['calves_l']['pos'][2] = frame_offsets['calves_l_z']
        self.body_parts['calves_r']['pos'][2] = frame_offsets['calves_r_z']
        self.body_parts['left_foot']['pos'][2] = frame_offsets['left_foot_z']
        self.body_parts['right_foot']['pos'][2] = frame_offsets['right_foot_z']
        
        self.update()
    
    def update_fps(self):
        """Mise à jour du compteur de FPS"""
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
    
    def toggle_walking(self):
        """Activer/désactiver l'animation de marche"""
        self.walking = not self.walking
        if self.walking:
            self.precalc_frame = 0
            self.animation_main_timer.start()
        else:
            self.animation_main_timer.stop()
            for part_key in ['forearm_l', 'forearm_r', 'left_hand', 'right_hand', 
                             'calves_l', 'calves_r', 'left_foot', 'right_foot']:
                self.body_parts[part_key]['pos'][2] = 0
            self.update()
        return self.walking
    
    def apply_imu_data(self, imu_id, quaternion):
        """Appliquer les données IMU à une partie du corps"""
        if imu_id in self.imu_mapping:
            part_name = self.imu_mapping[imu_id]
            
            x_rot = quaternion[1] * 90
            y_rot = quaternion[2] * 90
            z_rot = quaternion[3] * 90
            
            self.body_parts[part_name]['rot'] = [x_rot, y_rot, z_rot]
            
            self._adjust_limb_position(part_name, [x_rot, y_rot, z_rot])
            
            self.update()
            return True
        return False
    
    def _adjust_limb_position(self, part_name, rotation):
        """Adjust limb positions based on rotations"""
        if part_name in ['forearm_l', 'forearm_r']:  # Updated from left_elbow/right_elbow
            rot_factor = rotation[0] / 90.0
            direction = -1 if part_name == 'forearm_l' else 1
            
            self.body_parts[part_name]['pos'][2] = direction * rot_factor * 0.3
            
            hand = 'left_hand' if part_name == 'forearm_l' else 'right_hand'
            self.body_parts[hand]['pos'][2] = direction * rot_factor * 0.5
            
        elif part_name in ['calves_l', 'calves_r']:  # Updated from left_knee/right_knee
            rot_factor = rotation[0] / 90.0
            direction = -1 if part_name == 'calves_l' else 1
            
            self.body_parts[part_name]['pos'][2] = direction * rot_factor * 0.3
            
            foot = 'left_foot' if part_name == 'calves_l' else 'right_foot'
            self.body_parts[foot]['pos'][2] = direction * rot_factor * 0.5
    
    def map_imu_to_body_part(self, imu_id, body_part):
        """Associer un capteur IMU à une partie du corps"""
        if body_part in self.body_parts:
            self.imu_mapping[imu_id] = body_part
            return True
        return False
        
    def get_available_body_parts(self):
        """Obtenir la liste des parties du corps disponibles"""
        return list(self.body_parts.keys())
        
    def get_current_mappings(self):
        """Obtenir les associations actuelles IMU-parties du corps"""
        return self.imu_mapping.copy()
        
    def __del__(self):
        """Clean up OpenGL resources when object is destroyed."""
        try:
            # Only delete OpenGL resources if the context is valid
            if self.isValid() and self.context().isValid():
                self.makeCurrent()
                if hasattr(self, 'display_list') and self.display_list:
                    glDeleteLists(self.display_list, 1)
                self.doneCurrent()
        except Exception as e:
            # Silently ignore errors during cleanup
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
        """Mettre à jour la rotation globale du modèle"""
        self.model_viewer.rotation_x = x
        self.model_viewer.rotation_y = y
        self.model_viewer.rotation_z = z
        self.model_viewer.update()
    
    def toggle_animation(self):
        """Activer/désactiver l'animation de marche"""
        return self.model_viewer.toggle_walking()
        
    def apply_imu_data(self, imu_id, quaternion):
        """Appliquer les données IMU au modèle"""
        return self.model_viewer.apply_imu_data(imu_id, quaternion)
        
    def map_imu_to_body_part(self, imu_id, body_part):
        """Associer un IMU à une partie du corps"""
        return self.model_viewer.map_imu_to_body_part(imu_id, body_part)
        
    def get_available_body_parts(self):
        """Obtenir la liste des parties du corps disponibles"""
        return self.model_viewer.get_available_body_parts()
        
    def get_current_mappings(self):
        """Obtenir les associations actuelles IMU-parties du corps"""
        return self.model_viewer.get_current_mappings()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Model3DWidget()
    window.show()
    sensor_id = 1
    selected_body_part = 'torso'
    window.model_viewer.map_imu_to_body_part(sensor_id, selected_body_part)
    window.model_viewer.assign_button.clicked.connect(window.model_viewer.assign_sensor)

    sys.exit(app.exec_())
