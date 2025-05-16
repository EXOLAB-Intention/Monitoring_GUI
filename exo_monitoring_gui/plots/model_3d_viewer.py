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
        self.show_fps = True  # Option pour activer/désactiver l'affichage des FPS
        
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
        
        # Legacy mappings for backward compatibility
        self.legacy_mappings = {
            'left_elbow': 'forearm_l',
            'right_elbow': 'forearm_r',
            'left_knee': 'calves_l',
            'right_knee': 'calves_r'
        }
        
        # Précalculer les animations pour optimisation
        self.num_precalc_frames = 120
        self.precalculated_positions = self._precalculate_animation(self.num_precalc_frames)
        self.precalc_frame = 0
        
        # Optimisations pour OpenGL
        self.display_list = 0  # Doit être initialisé à 0, pas à None
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
            
            # Calculs simplifiés pour éviter les bugs
            arm_swing = 0.25 * math.sin(phase)
            
            # Phase opposée pour jambe droite et gauche (décalage de 180 degrés)
            leg_swing_left = 0.3 * math.sin(phase)
            leg_swing_right = 0.3 * math.sin(phase + math.pi)
            
            # Amplitude des mouvements
            torso_sway = 0.05 * math.sin(phase)
            vertical_bounce = 0.03 * math.sin(phase * 2)
            torso_rotation = 3 * math.sin(phase)
            
            # Rotation de la tête (réduite)
            head_rotation_x = 1.0 * math.sin(phase + 0.2)
            head_rotation_y = torso_rotation * 0.2
            head_rotation_z = 0.5 * math.sin(phase)
            
            frame_offsets = {
                # Mouvements du torse et de la tête
                'torso_x': torso_sway,
                'head_x': torso_sway * 1.1,
                'neck_x': torso_sway * 1.05,
                
                # Mouvement vertical
                'torso_y': vertical_bounce,
                'head_y': vertical_bounce * 1.2,
                'neck_y': vertical_bounce * 1.1,
                
                # Rotations
                'torso_rot_y': torso_rotation,
                'head_rot_x': head_rotation_x,
                'head_rot_y': head_rotation_y,
                'head_rot_z': head_rotation_z,
                
                # Hanche
                'hip_x': torso_sway * 0.5,
                'hip_y': vertical_bounce,
                
                # Bras gauche
                'deltoid_l_z': arm_swing * 0.7,
                'biceps_l_z': arm_swing * 0.9,
                'forearm_l_z': arm_swing,
                'left_hand_z': arm_swing * 1.2,
                'dorsalis_major_l_z': arm_swing * 0.5,
                'pectorals_l_z': arm_swing * 0.4,
                
                # Bras droit
                'deltoid_r_z': -arm_swing * 0.7, 
                'biceps_r_z': -arm_swing * 0.9,
                'forearm_r_z': -arm_swing,
                'right_hand_z': -arm_swing * 1.2,
                'dorsalis_major_r_z': -arm_swing * 0.5,
                'pectorals_r_z': -arm_swing * 0.4,
                
                # Jambe gauche - Phase indépendante
                'glutes_l_z': leg_swing_left * 0.5,
                'quadriceps_l_z': leg_swing_left * 0.7,
                'ishcio_hamstrings_l_z': leg_swing_left * 0.7,
                'calves_l_z': leg_swing_left * 0.9,
                'left_foot_z': leg_swing_left * 1.3,
                
                # Jambe droite - Phase indépendante
                'glutes_r_z': leg_swing_right * 0.5,
                'quadriceps_r_z': leg_swing_right * 0.7,
                'ishcio_hamstrings_r_z': leg_swing_right * 0.7,
                'calves_r_z': leg_swing_right * 0.9,
                'right_foot_z': leg_swing_right * 1.3
            }
            positions.append(frame_offsets)
            
        return positions

    def get_default_position(self, part_name):
        """Retourne la position par défaut d'une partie du corps (sans animation)"""
        # Ces positions correspondent aux positions initiales définies dans le dictionnaire body_parts
        default_positions = {
            'head': [0, 1.7, 0],
            'neck': [0, 1.5, 0],
            'torso': [0, 0.9, 0],
            'deltoid_l': [-0.15, 1.4, 0],
            'biceps_l': [-0.3, 1.3, 0],
            'forearm_l': [-0.4, 1.1, 0],
            'dorsalis_major_l': [-0.1, 1.2, 0],
            'pectorals_l': [-0.1, 1.3, 0],
            'left_hand': [-0.5, 0.8, 0],
            'deltoid_r': [0.15, 1.4, 0],
            'biceps_r': [0.3, 1.3, 0],
            'forearm_r': [0.4, 1.1, 0],
            'dorsalis_major_r': [0.1, 1.2, 0],
            'pectorals_r': [0.1, 1.3, 0],
            'right_hand': [0.5, 0.8, 0],
            'hip': [0, 0.9, 0],
            'quadriceps_l': [-0.15, 0.7, 0],
            'quadriceps_r': [0.15, 0.7, 0],
            'ishcio_hamstrings_l': [-0.15, 0.6, 0],
            'ishcio_hamstrings_r': [0.15, 0.6, 0],
            'calves_l': [-0.2, 0.3, 0],
            'calves_r': [0.2, 0.3, 0],
            'glutes_l': [-0.15, 0.8, 0],
            'glutes_r': [0.15, 0.8, 0],
            'left_foot': [-0.2, 0.0, 0],
            'right_foot': [0.2, 0.0, 0]
        }
        return default_positions.get(part_name, [0, 0, 0])

    def update_animation_frame(self):
        """Update walking animation on each QTimer tick with full body movement"""
        if not self.walking:
            return
        
        self.precalc_frame = (self.precalc_frame + 1) % self.num_precalc_frames
        frame_offsets = self.precalculated_positions[self.precalc_frame]
        
        # Liste des parties et leurs clés d'offset correspondantes
        part_offset_pairs = [
            # Tête et torse
            ('torso', 'torso_x'), ('torso', 'torso_y'),
            ('head', 'head_x'), ('head', 'head_y'),
            ('neck', 'neck_x'), ('neck', 'neck_y'),
            ('hip', 'hip_x'), ('hip', 'hip_y'),
            
            # Bras gauche
            ('deltoid_l', 'deltoid_l_z'),
            ('biceps_l', 'biceps_l_z'),
            ('forearm_l', 'forearm_l_z'),
            ('left_hand', 'left_hand_z'),
            ('dorsalis_major_l', 'dorsalis_major_l_z'),
            ('pectorals_l', 'pectorals_l_z'),
            
            # Bras droit
            ('deltoid_r', 'deltoid_r_z'),
            ('biceps_r', 'biceps_r_z'),
            ('forearm_r', 'forearm_r_z'),
            ('right_hand', 'right_hand_z'),
            ('dorsalis_major_r', 'dorsalis_major_r_z'),
            ('pectorals_r', 'pectorals_r_z'),
            
            # Jambe gauche
            ('glutes_l', 'glutes_l_z'),
            ('quadriceps_l', 'quadriceps_l_z'),
            ('ishcio_hamstrings_l', 'ishcio_hamstrings_l_z'),
            ('calves_l', 'calves_l_z'),
            ('left_foot', 'left_foot_z'),
            
            # Jambe droite
            ('glutes_r', 'glutes_r_z'),
            ('quadriceps_r', 'quadriceps_r_z'),
            ('ishcio_hamstrings_r', 'ishcio_hamstrings_r_z'),
            ('calves_r', 'calves_r_z'),
            ('right_foot', 'right_foot_z')
        ]
        
        # Appliquer les offsets seulement si les clés existent
        for part_name, offset_key in part_offset_pairs:
            if offset_key in frame_offsets and part_name in self.body_parts:
                if offset_key.endswith('_x'):
                    self.body_parts[part_name]['pos'][0] = self.get_default_position(part_name)[0] + frame_offsets[offset_key]
                elif offset_key.endswith('_y'):
                    self.body_parts[part_name]['pos'][1] = self.get_default_position(part_name)[1] + frame_offsets[offset_key]
                elif offset_key.endswith('_z'):
                    self.body_parts[part_name]['pos'][2] = self.get_default_position(part_name)[2] + frame_offsets[offset_key]
        
        # Appliquer les rotations avec vérification des clés
        rotation_keys = [
            ('torso', 'torso_rot_y', 1),
            ('head', 'head_rot_x', 0),
            ('head', 'head_rot_y', 1),
            ('head', 'head_rot_z', 2)
        ]
        
        for part_name, rot_key, rot_index in rotation_keys:
            if rot_key in frame_offsets:
                self.body_parts[part_name]['rot'][rot_index] = frame_offsets[rot_key]
        
        # Recréer la display list pour l'animation
        self.create_display_list()
        self.update()

    def toggle_walking(self):
        """Activer/désactiver l'animation de marche"""
        self.walking = not self.walking
        if self.walking:
            self.precalc_frame = 0
            self.animation_main_timer.start()
        else:
            self.animation_main_timer.stop()
            # Réinitialiser les positions de toutes les parties du corps
            for part_name in self.body_parts:
                default_pos = self.get_default_position(part_name)
                self.body_parts[part_name]['pos'] = default_pos.copy()
            self.update()
        return self.walking

    def reset_view(self):
        """Réinitialiser la vue du modèle à la position de face par défaut"""
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.update()

    def initializeGL(self):
        """Initialize OpenGL context and resources."""
        # Vérifie si le contexte est valide avant d'appeler les fonctions OpenGL
        if not self.isValid() or not self.context().isValid():
            print("Warning: OpenGL context not valid during initialization")
            return

        # Configuration OpenGL de base
        try:
            glClearColor(0.1, 0.1, 0.1, 1.0)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glEnable(GL_NORMALIZE)
            
            # Configurer la lumière
            glLightfv(GL_LIGHT0, GL_POSITION, [5.0, 5.0, 5.0, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
            glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0])
            
            # Initialiser le quadric pour les articulations
            self.quadric = gluNewQuadric()
            gluQuadricDrawStyle(self.quadric, GLU_FILL)
            gluQuadricNormals(self.quadric, GLU_SMOOTH)
            
            # Initialiser d'abord la display_list du modèle
            self.display_list = 0  # Initialisation explicite
            self.create_display_list()
            
            # Puis créer le sol
            try:
                # Créer le sol uniquement si la display_list du modèle a été créée avec succès
                if self.display_list != 0:
                    self.floor_display_list = glGenLists(1)
                    if self.floor_display_list != 0:
                        glNewList(self.floor_display_list, GL_COMPILE)
                        self.create_floor()
                        glEndList()
                    else:
                        self.floor_display_list = 0
                        print("Warning: Could not create floor display list")
                else:
                    self.floor_display_list = 0
            except OpenGL.error.GLError as e:
                print(f"OpenGL error creating floor: {e}")
                self.floor_display_list = 0
                
        except OpenGL.error.GLError as e:
            print(f"OpenGL initialization error: {e}")

    def create_floor(self):
        """Créer un sol quadrillé pour visualiser la direction de déplacement"""
        # Couleur du sol
        glColor3f(0.3, 0.3, 0.3)
        
        # Taille du sol
        floor_size = 10.0
        grid_size = 0.5
        
        # Dessiner le sol principal
        glBegin(GL_QUADS)
        glVertex3f(-floor_size, 0, -floor_size)
        glVertex3f(-floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, floor_size)
        glVertex3f(floor_size, 0, -floor_size)
        glEnd()
        
        # Dessiner le quadrillage
        glLineWidth(1.0)
        glBegin(GL_LINES)
        
        # Lignes dans l'axe Z (avant/arrière)
        glColor3f(0.5, 0.5, 0.5)
        for x in np.arange(-floor_size, floor_size + grid_size, grid_size):
            glVertex3f(x, 0.01, -floor_size)
            glVertex3f(x, 0.01, floor_size)
        
        # Lignes dans l'axe X (gauche/droite)
        for z in np.arange(-floor_size, floor_size + grid_size, grid_size):
            glVertex3f(-floor_size, 0.01, z)
            glVertex3f(floor_size, 0.01, z)
        
        glEnd()
        
        # Dessiner des marqueurs de direction (flèches ou repères)
        self.draw_direction_marker(0, 0.02, 0, 1.5)  # Marqueur au centre
        
        # Ajouter des marqueurs aux quatre coins pour l'orientation
        self.draw_direction_marker(-floor_size + 0.5, 0.02, -floor_size + 0.5, 0.5)  # Coin arrière gauche
        self.draw_direction_marker(floor_size - 0.5, 0.02, -floor_size + 0.5, 0.5)   # Coin arrière droit
        self.draw_direction_marker(-floor_size + 0.5, 0.02, floor_size - 0.5, 0.5)   # Coin avant gauche
        self.draw_direction_marker(floor_size - 0.5, 0.02, floor_size - 0.5, 0.5)    # Coin avant droit

    def draw_direction_marker(self, x, y, z, size):
        """Dessiner un marqueur de direction (flèche)"""
        # Flèche pointant vers Z+ (avant)
        glBegin(GL_LINES)
        
        # Ligne principale de la flèche
        glColor3f(0.0, 0.7, 0.0)  # Vert pour l'axe Z (avant)
        glVertex3f(x, y, z)
        glVertex3f(x, y, z + size)
        
        # Pointe de la flèche
        glVertex3f(x, y, z + size)
        glVertex3f(x - size/5, y, z + size - size/5)
        
        glVertex3f(x, y, z + size)
        glVertex3f(x + size/5, y, z + size - size/5)
        
        # Ligne X (rouge)
        glColor3f(0.7, 0.0, 0.0)  # Rouge pour l'axe X (droite)
        glVertex3f(x, y, z)
        glVertex3f(x + size, y, z)
        
        # Pointe de la flèche X
        glVertex3f(x + size, y, z)
        glVertex3f(x + size - size/5, y, z - size/5)
        
        glVertex3f(x + size, y, z)
        glVertex3f(x + size - size/5, y, z + size/5)
        
        glEnd()

    def create_display_list(self):
        """Create an OpenGL display list for the model."""
        # S'assurer que le contexte est valide
        if not self.isValid() or not self.context().isValid():
            print("Warning: OpenGL context not valid when creating display list")
            return
        
        try:
            self.makeCurrent()
            
            # Vérifier si display_list est déjà défini et valide
            if hasattr(self, 'display_list') and self.display_list != 0:
                try:
                    glDeleteLists(self.display_list, 1)
                except OpenGL.error.GLError:
                    pass
            
            # Générer une nouvelle liste
            self.display_list = glGenLists(1)
            if self.display_list == 0:
                print("Error: Failed to generate a valid display list ID")
                return
                
            glNewList(self.display_list, GL_COMPILE)
            
            # Dessiner le modèle
            self.draw_limbs_internal()
            self.draw_joints_internal()
            
            glEndList()
        except OpenGL.error.GLError as e:
            print(f"OpenGL error in create_display_list: {e}")
            self.display_list = 0
        finally:
            self.doneCurrent()

    def resizeGL(self, width, height):
        """Handle window resize events."""
        # Vérifier que le contexte OpenGL est valide
        if not self.isValid() or not self.context().isValid():
            return
        
        try:
            glViewport(0, 0, width, height)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            aspect = width / float(height) if height > 0 else 1.0
            gluPerspective(45.0, aspect, 0.1, 100.0)
            glMatrixMode(GL_MODELVIEW)
        except OpenGL.error.GLError as e:
            print(f"OpenGL resize error: {e}")

    def paintGL(self):
        """Render the OpenGL scene."""
        # Vérifier que le contexte OpenGL est valide
        if not self.isValid() or not self.context().isValid():
            return
        
        try:
            self.frame_count += 1
            
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
            
            gluLookAt(0, 1.0, 5.0, 0, 1.0, 0.0, 0, 1.0, 0.0)
            
            # Rotation globale
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)
            glRotatef(self.rotation_z, 0, 0, 1)
            
            # Dessiner le sol si disponible
            if hasattr(self, 'floor_display_list') and self.floor_display_list != 0:
                glCallList(self.floor_display_list)
            
            # Si en animation, dessiner directement (plus fluide)
            if not hasattr(self, 'walking') or not self.walking:
                if hasattr(self, 'display_list') and self.display_list != 0:
                    glCallList(self.display_list)
                else:
                    self.draw_limbs_internal()
                    self.draw_joints_internal()
            else:
                self.draw_limbs_internal()
                self.draw_joints_internal()
            
            # Draw the sensor legend
            self._draw_legend()
        except OpenGL.error.GLError as e:
            print(f"OpenGL rendering error: {e}")

    def draw_limbs_internal(self):
        """Draw the limbs of the body using immediate mode OpenGL."""
        glLineWidth(3.0)
        glBegin(GL_LINES)
        
        # Head and neck
        glColor3f(1.0, 0.8, 0.6)
        self.draw_line_from_parts('head', 'neck')
        
        # Torso connections - AJOUT DE LA CONNEXION TORSE-HANCHE
        glColor3f(0.2, 0.4, 0.8)
        self.draw_line_from_parts('neck', 'torso')
        self.draw_line_from_parts('torso', 'hip')  # Cette ligne était manquante
        
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
    
    def draw_joints_internal(self):
        """Dessiner les articulations avec rotations individuelles et indication du type de capteur"""
        for part_name, data in self.body_parts.items():
            pos = data['pos']
            rot = data['rot']
            
            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])
            
            # Appliquer la rotation individuelle de chaque partie
            glRotatef(rot[0], 1, 0, 0)
            glRotatef(rot[1], 0, 1, 0)
            glRotatef(rot[2], 0, 0, 1)

            # Déterminer le type de capteur
            sensor_type = self._get_mapped_sensor_type(part_name)
            
            # Couleur selon le type de capteur
            if sensor_type == "IMU":
                glColor3f(0.0, 0.8, 0.2)  # Vert pour IMU
            elif sensor_type == "EMG":
                glColor3f(0.8, 0.2, 0.0)  # Rouge pour EMG
            elif sensor_type == "pMMG":
                glColor3f(0.0, 0.2, 0.8)  # Bleu pour pMMG
            else:
                glColor3f(0.9, 0.9, 0.9)  # Gris si aucun capteur

            # Dessiner la sphère de l'articulation
            if self.quadric:
                if part_name == 'head':
                    gluSphere(self.quadric, 0.15, 12, 12)
                else:
                    gluSphere(self.quadric, 0.05, 6, 6)
            
            # Ajouter une étiquette pour le type de capteur
            if sensor_type:
                # Sauvegarder la position pour l'étiquette
                model = glGetDoublev(GL_MODELVIEW_MATRIX)
                proj = glGetDoublev(GL_PROJECTION_MATRIX)
                view = glGetIntegerv(GL_VIEWPORT)
                
                # Obtenir les coordonnées d'écran
                win_x, win_y, win_z = gluProject(0, 0, 0, model, proj, view)
                
                # Stocker pour affichage ultérieur
                if not hasattr(self, 'labels'):
                    self.labels = []
                self.labels.append((win_x, self.height() - win_y, f"{sensor_type}", sensor_type))
            
            glPopMatrix()
    
    def draw_joints(self):
        """Améliorer le rendu des articulations avec indication visuelle du mapping"""
        for part_name, data in self.body_parts.items():
            pos = data['pos']
            rot = data['rot']
            
            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])
            
            # Appliquer rotation
            glRotatef(rot[0], 1, 0, 0)
            glRotatef(rot[1], 0, 1, 0)
            glRotatef(rot[2], 0, 0, 1)

            # Déterminer le type de capteur associé à cette partie
            mapped_sensor_type = self._get_mapped_sensor_type(part_name)
            
            # Couleur selon le type de capteur
            if mapped_sensor_type == "IMU":
                glColor3f(0.0, 0.8, 0.2)  # Vert pour IMU
            elif mapped_sensor_type == "EMG":
                glColor3f(0.8, 0.2, 0.0)  # Rouge pour EMG
            elif mapped_sensor_type == "pMMG":
                glColor3f(0.0, 0.2, 0.8)  # Bleu pour pMMG
            else:
                glColor3f(0.9, 0.9, 0.9)  # Gris si aucun capteur

            # Dessiner la sphère
            if self.quadric:
                if part_name == 'head':
                    gluSphere(self.quadric, 0.15, 12, 12)
                else:
                    gluSphere(self.quadric, 0.05, 6, 6)
                    
            glPopMatrix()
    
    def draw_limbs(self):
        """Méthode publique pour redessiner les limbs - utilise la version interne"""
        self.create_display_list()
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
    
    def apply_imu_data(self, imu_id, quaternion):
        """Appliquer les données IMU à une partie du corps"""
        if imu_id in self.imu_mapping:
            part_name = self.imu_mapping[imu_id]
            
            x_rot = quaternion[1] * 90
            y_rot = quaternion[2] * 90
            z_rot = quaternion[3] * 90
            
            self.body_parts[part_name]['rot'] = [x_rot, y_rot, z_rot]
            
            self._adjust_limb_position(part_name, [x_rot, y_rot, z_rot])
            
            # Recréer la display list lorsque l'IMU change
            self.create_display_list()
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
        """Associer un capteur IMU à une partie du corps avec validation"""
        if body_part not in self.body_parts and body_part not in self.legacy_mappings:
            print(f"Warning: Body part '{body_part}' not found in model")
            return False
        
        # Si c'est un nom hérité, le convertir au nom actuel
        if body_part in self.legacy_mappings:
            body_part = self.legacy_mappings[body_part]
        
        self.imu_mapping[imu_id] = body_part
        return True
        
    def get_available_body_parts(self):
        """Obtenir la liste des parties du corps disponibles"""
        return list(self.body_parts.keys())
        
    def get_current_mappings(self):
        """Obtenir les associations actuelles IMU-parties du corps"""
        return self.imu_mapping.copy()
        
    def load_external_model(self, file_path):
        """Charger un modèle 3D externe (obj, stl, etc.)"""
        if not os.path.exists(file_path):
            return False
            
        try:
            # Cette implémentation dépend des bibliothèques que vous utilisez
            # Par exemple, avec PyMesh:
            # import pymesh
            # mesh = pymesh.load_mesh(file_path)
            
            # Ou avec trimesh:
            import trimesh
            mesh = trimesh.load(file_path)
            
            # Stocker le mesh et l'utiliser pour le rendu
            self.external_mesh = mesh
            
            # Mettre à jour le mapping des parties du corps sur le nouveau modèle
            self._map_body_parts_to_model()
            
            # Mise à jour de l'affichage
            self.update()
            
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
        
    def _map_body_parts_to_model(self):
        """Mapper les parties du corps sur un modèle externe"""
        # Cette implémentation dépendra de la structure du modèle chargé
        # Vous devrez adapter cette fonction à votre cas spécifique
        
        # Exemple: utiliser les positions extrêmes pour estimer les parties
        if hasattr(self, 'external_mesh'):
            vertices = np.array(self.external_mesh.vertices)
            
            # Trouver la hauteur totale du modèle
            min_y = np.min(vertices[:, 1])
            max_y = np.max(vertices[:, 1])
            height = max_y - min_y
            
            # Mapper les parties du corps en fonction de la hauteur relative
            self.body_parts['head']['pos'] = [0, min_y + height * 0.9, 0]
            self.body_parts['neck']['pos'] = [0, min_y + height * 0.85, 0]
            self.body_parts['torso']['pos'] = [0, min_y + height * 0.7, 0]
            # ... mapper toutes les autres parties
        
    def _get_mapped_sensor_type(self, part_name):
        """Déterminer le type de capteur associé à une partie du corps"""
        # Vérifier les IMU (déjà implémentés)
        for imu_id, mapped_part in self.imu_mapping.items():
            if mapped_part == part_name:
                return "IMU"
        
        # Structure pour stocker les mappings EMG et pMMG (à implémenter)
        # Ces attributs doivent être définis lors de l'initialisation
        if hasattr(self, 'emg_mapping'):
            for emg_id, mapped_part in self.emg_mapping.items():
                if mapped_part == part_name:
                    return "EMG"
                    
        if hasattr(self, 'pmmg_mapping'):
            for pmmg_id, mapped_part in self.pmmg_mapping.items():
                if mapped_part == part_name:
                    return "pMMG"
        
        return None  # Aucun capteur associé

    def set_emg_mapping(self, emg_mapping):
        """Définir les associations EMG-parties du corps"""
        self.emg_mapping = emg_mapping
        self.update()

    def set_pmmg_mapping(self, pmmg_mapping):
        """Définir les associations pMMG-parties du corps"""
        self.pmmg_mapping = pmmg_mapping
        self.update()

    def _draw_legend(self):
        """Dessiner la légende des capteurs et afficher FPS en haut à droite"""
        # Title and labels
        self.renderText(10, 20, "Legend:", QFont("Arial", 10, QFont.Bold))
        self.renderText(60, 45, "IMU Sensors", QFont("Arial", 9))
        self.renderText(60, 65, "EMG Sensors", QFont("Arial", 9))
        self.renderText(60, 85, "pMMG Sensors", QFont("Arial", 9))
        
        # Afficher FPS en haut à droite
        if self.show_fps:
            fps_text = f"FPS: {self.fps:.1f}"
            text_width = 80  # Largeur approximative du texte
            self.renderText(self.width() - text_width - 10, 20, fps_text, QFont("Arial", 10, QFont.Bold))
        
        # Draw color squares
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width(), 0, self.height(), -1, 1)
        
        glBegin(GL_QUADS)
        # IMU (green)
        glColor3f(0.0, 0.8, 0.2)
        glVertex2f(30, self.height() - 45)
        glVertex2f(50, self.height() - 45)
        glVertex2f(50, self.height() - 35)
        glVertex2f(30, self.height() - 35)
        
        # EMG (red)
        glColor3f(0.8, 0.2, 0.0)
        glVertex2f(30, self.height() - 65)
        glVertex2f(50, self.height() - 65)
        glVertex2f(50, self.height() - 55)
        glVertex2f(30, self.height() - 55)
        
        # pMMG (blue)
        glColor3f(0.0, 0.2, 0.8)
        glVertex2f(30, self.height() - 85)
        glVertex2f(50, self.height() - 85)
        glVertex2f(50, self.height() - 75)
        glVertex2f(30, self.height() - 75)
        glEnd()
        
        # Add a border around the legend
        glColor3f(0.7, 0.7, 0.7)
        glBegin(GL_LINE_LOOP)
        glVertex2f(5, self.height() - 100)     # Bas gauche - Plus bas de 5 pixels
        glVertex2f(180, self.height() - 100)   # Bas droite - Plus large de 10 pixels
        glVertex2f(180, self.height() - 10)    # Haut droite - Plus haut de 5 pixels
        glVertex2f(5, self.height() - 10)      # Haut gauche - Plus haut de 5 pixels
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def __del__(self):
        """Clean up OpenGL resources when object is destroyed."""
        try:
            # Only delete OpenGL resources if the context is valid
            if self.isValid() and self.context().isValid():
                self.makeCurrent()
                if hasattr(self, 'display_list') and self.display_list:
                    glDeleteLists(self.display_list, 1)
                if hasattr(self, 'floor_display_list') and self.floor_display_list:
                    glDeleteLists(self.floor_display_list, 1)
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
        
    def reset_view(self):
        """Réinitialiser la vue du modèle 3D à la position de face"""
        self.model_viewer.reset_view()
    
    def load_external_model(self, file_path):
        """Proxy method to load external 3D model"""
        return self.model_viewer.load_external_model(file_path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Model3DWidget()
    window.show()
    sensor_id = 1
    selected_body_part = 'torso'
    window.model_viewer.map_imu_to_body_part(sensor_id, selected_body_part)
    window.model_viewer.assign_button.clicked.connect(window.model_viewer.assign_sensor)

    sys.exit(app.exec_())
