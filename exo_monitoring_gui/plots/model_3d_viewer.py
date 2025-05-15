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
            'head': {'pos': [0, 1.7, 0], 'rot': [0, 0, 0]},
            'neck': {'pos': [0, 1.5, 0], 'rot': [0, 0, 0]},
            'torso': {'pos': [0, 0.9, 0], 'rot': [0, 0, 0]},
            'left_shoulder': {'pos': [-0.2, 1.5, 0], 'rot': [0, 0, 0]},
            'right_shoulder': {'pos': [0.2, 1.5, 0], 'rot': [0, 0, 0]},
            'left_elbow': {'pos': [-0.4, 1.2, 0], 'rot': [0, 0, 0]},
            'right_elbow': {'pos': [0.4, 1.2, 0], 'rot': [0, 0, 0]},
            'left_hand': {'pos': [-0.5, 0.8, 0], 'rot': [0, 0, 0]},
            'right_hand': {'pos': [0.5, 0.8, 0], 'rot': [0, 0, 0]},
            'hip': {'pos': [0, 0.9, 0], 'rot': [0, 0, 0]},
            'left_knee': {'pos': [-0.2, 0.5, 0], 'rot': [0, 0, 0]},
            'right_knee': {'pos': [0.2, 0.5, 0], 'rot': [0, 0, 0]},
            'left_foot': {'pos': [-0.2, 0.0, 0], 'rot': [0, 0, 0]},
            'right_foot': {'pos': [0.2, 0.0, 0], 'rot': [0, 0, 0]}
        }
        
        # IMU mapping dict - maps IMU ID to body part
        self.imu_mapping = {
            1: 'torso',
            2: 'left_elbow',
            3: 'right_elbow',
            4: 'left_knee',
            5: 'right_knee',
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
        """Précalculer les positions d'animation pour une performance optimale"""
        positions = []
        for i in range(num_frames):
            phase = (i / float(num_frames)) * 2 * math.pi
            arm_swing = 0.2 * math.sin(phase)
            leg_swing = 0.2 * math.sin(phase)
            
            frame_offsets = {
                'left_elbow_z': arm_swing,
                'right_elbow_z': -arm_swing,
                'left_hand_z': arm_swing * 1.5,
                'right_hand_z': -arm_swing * 1.5,
                'left_knee_z': -leg_swing,
                'right_knee_z': leg_swing,
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
        """Dessiner les membres du corps en utilisant le mode immédiat OpenGL."""
        glLineWidth(3.0)
        glBegin(GL_LINES)
        
        glColor3f(1.0, 0.8, 0.6)
        self.draw_line_from_parts('head', 'neck')
        
        glColor3f(0.2, 0.4, 0.8)
        self.draw_line_from_parts('neck', 'torso')
        
        self.draw_line_from_parts('neck', 'left_shoulder')
        self.draw_line_from_parts('left_shoulder', 'left_elbow')
        self.draw_line_from_parts('left_elbow', 'left_hand')
        
        self.draw_line_from_parts('neck', 'right_shoulder')
        self.draw_line_from_parts('right_shoulder', 'right_elbow')
        self.draw_line_from_parts('right_elbow', 'right_hand')
        
        glColor3f(0.1, 0.1, 0.5)
        self.draw_line_from_parts('hip', 'left_knee') 
        self.draw_line_from_parts('left_knee', 'left_foot')
        
        self.draw_line_from_parts('hip', 'right_knee')
        self.draw_line_from_parts('right_knee', 'right_foot')
        
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
        """Mettre à jour l'animation de marche à chaque tick du QTimer."""
        if not self.walking:
            return
        
        self.precalc_frame = (self.precalc_frame + 1) % self.num_precalc_frames
        frame_offsets = self.precalculated_positions[self.precalc_frame]
        
        self.body_parts['left_elbow']['pos'][2] = frame_offsets['left_elbow_z']
        self.body_parts['right_elbow']['pos'][2] = frame_offsets['right_elbow_z']
        self.body_parts['left_hand']['pos'][2] = frame_offsets['left_hand_z']
        self.body_parts['right_hand']['pos'][2] = frame_offsets['right_hand_z']
        self.body_parts['left_knee']['pos'][2] = frame_offsets['left_knee_z']
        self.body_parts['right_knee']['pos'][2] = frame_offsets['right_knee_z']
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
            for part_key in ['left_elbow', 'right_elbow', 'left_hand', 'right_hand', 
                             'left_knee', 'right_knee', 'left_foot', 'right_foot']:
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
        """Ajuster la position des membres en fonction des rotations"""
        if part_name in ['left_elbow', 'right_elbow']:
            rot_factor = rotation[0] / 90.0
            direction = -1 if part_name == 'left_elbow' else 1
            
            self.body_parts[part_name]['pos'][2] = direction * rot_factor * 0.3
            
            hand = 'left_hand' if part_name == 'left_elbow' else 'right_hand'
            self.body_parts[hand]['pos'][2] = direction * rot_factor * 0.5
            
        elif part_name in ['left_knee', 'right_knee']:
            rot_factor = rotation[0] / 90.0
            direction = -1 if part_name == 'left_knee' else 1
            
            self.body_parts[part_name]['pos'][2] = direction * rot_factor * 0.3
            
            foot = 'left_foot' if part_name == 'left_knee' else 'right_foot'
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
