import sys
import os
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtOpenGL import QGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *
import math

class Model3DViewer(QGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        
        # Animation parameters
        self.animation_phase = 0
        self.walking = False
        
        # Body part positions (will be updated during drawing)
        self.head_pos = [0, 1.7, 0]
        self.neck_pos = [0, 1.5, 0]
        self.torso_pos = [0, 0.9, 0]
        self.left_shoulder_pos = [-0.2, 1.5, 0]
        self.right_shoulder_pos = [0.2, 1.5, 0]
        self.left_elbow_pos = [-0.4, 1.2, 0]
        self.right_elbow_pos = [0.4, 1.2, 0]
        self.left_hand_pos = [-0.5, 0.8, 0]
        self.right_hand_pos = [0.5, 0.8, 0]
        self.hip_pos = [0, 0.9, 0]
        self.left_knee_pos = [-0.2, 0.5, 0]
        self.right_knee_pos = [0.2, 0.5, 0]
        self.left_foot_pos = [-0.2, 0.0, 0]
        self.right_foot_pos = [0.2, 0.0, 0]
        
        # IMU mapping
        self.imu_mapping = {
            1: 'torso',
            2: 'left_elbow',
            3: 'right_elbow',
            4: 'left_knee',
            5: 'right_knee',
            6: 'head'
        }
        
    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        
    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = width / float(height)
        gluPerspective(45.0, aspect, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
    
    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Position camera
        gluLookAt(0, 1.0, 5.0,  # Camera position
                 0, 1.0, 0.0,   # Look at point
                 0, 1.0, 0.0)   # Up vector
        
        # Apply rotations
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        glRotatef(self.rotation_z, 0, 0, 1)
        
        # Update animation phase if walking
        if self.walking:
            self.animation_phase += 0.05
            if self.animation_phase > 2*math.pi:
                self.animation_phase -= 2*math.pi
            self.updateGL()  # Keep updating when animation is active
        
        # Update limb positions based on animation phase
        if self.walking:
            arm_swing = 0.2 * math.sin(self.animation_phase)
            leg_swing = 0.2 * math.sin(self.animation_phase)
            
            self.left_elbow_pos[2] = arm_swing
            self.right_elbow_pos[2] = -arm_swing
            self.left_hand_pos[2] = arm_swing * 2
            self.right_hand_pos[2] = -arm_swing * 2
            self.left_knee_pos[2] = -leg_swing
            self.right_knee_pos[2] = leg_swing
            self.left_foot_pos[2] = -leg_swing * 1.5
            self.right_foot_pos[2] = leg_swing * 1.5
        
        # Draw stickman
        self.draw_stickman()
    
    def draw_stickman(self):
        """Draw a 3D stickman figure"""
        glLineWidth(3.0)
        
        # Draw head (sphere)
        glPushMatrix()
        glTranslatef(0, 1.7, 0)
        glColor3f(1.0, 0.8, 0.6)  # Skin tone
        self.draw_sphere(0.15, 12, 12)
        glPopMatrix()
        
        # Draw body lines
        glBegin(GL_LINES)
        
        # Neck
        glColor3f(1.0, 0.8, 0.6)
        self.draw_line(self.head_pos, self.neck_pos)
        
        # Torso
        glColor3f(0.2, 0.4, 0.8)  # Blue torso
        self.draw_line(self.neck_pos, self.torso_pos)
        
        # Left arm
        glColor3f(0.2, 0.4, 0.8)
        self.draw_line(self.neck_pos, self.left_shoulder_pos)
        self.draw_line(self.left_shoulder_pos, self.left_elbow_pos)
        self.draw_line(self.left_elbow_pos, self.left_hand_pos)
        
        # Right arm
        self.draw_line(self.neck_pos, self.right_shoulder_pos)
        self.draw_line(self.right_shoulder_pos, self.right_elbow_pos)
        self.draw_line(self.right_elbow_pos, self.right_hand_pos)
        
        # Left leg
        glColor3f(0.1, 0.1, 0.5)  # Darker blue legs
        self.draw_line(self.hip_pos, self.left_knee_pos)
        self.draw_line(self.left_knee_pos, self.left_foot_pos)
        
        # Right leg
        self.draw_line(self.hip_pos, self.right_knee_pos)
        self.draw_line(self.right_knee_pos, self.right_foot_pos)
        
        glEnd()
        
        # Draw joints as small spheres
        self.draw_joints()
    
    def draw_line(self, start, end):
        glVertex3f(start[0], start[1], start[2])
        glVertex3f(end[0], end[1], end[2])
    
    def draw_joints(self):
        """Draw small spheres at joint positions"""
        joint_positions = [
            self.neck_pos,
            self.left_shoulder_pos, self.left_elbow_pos, self.left_hand_pos,
            self.right_shoulder_pos, self.right_elbow_pos, self.right_hand_pos,
            self.hip_pos,
            self.left_knee_pos, self.left_foot_pos,
            self.right_knee_pos, self.right_foot_pos
        ]
        
        glColor3f(0.9, 0.9, 0.9)  # Light gray joints
        for pos in joint_positions:
            glPushMatrix()
            glTranslatef(pos[0], pos[1], pos[2])
            self.draw_sphere(0.05, 8, 8)
            glPopMatrix()
    
    def draw_sphere(self, radius, slices, stacks):
        """Draw a sphere with the given parameters"""
        quadric = gluNewQuadric()
        gluQuadricDrawStyle(quadric, GLU_FILL)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        gluSphere(quadric, radius, slices, stacks)
        gluDeleteQuadric(quadric)
    
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
            self.updateGL()
            
        self.last_pos = event.pos()
    
    def toggle_walking(self):
        """Toggle walking animation on/off"""
        self.walking = not self.walking
        if not self.walking:
            # Reset positions when stopping animation
            self.left_elbow_pos[2] = 0
            self.right_elbow_pos[2] = 0
            self.left_hand_pos[2] = 0
            self.right_hand_pos[2] = 0
            self.left_knee_pos[2] = 0
            self.right_knee_pos[2] = 0
            self.left_foot_pos[2] = 0
            self.right_foot_pos[2] = 0
            self.updateGL()
        return self.walking
    
    def map_imu_to_body_part(self, imu_id, body_part):
        """Map an IMU sensor to a specific body part"""
        self.imu_mapping[imu_id] = body_part
        return True
    
    def get_current_mappings(self):
        """Get current IMU to body part mappings"""
        return self.imu_mapping.copy()
    
    def get_available_body_parts(self):
        """Get list of available body parts for mapping"""
        return ['head', 'neck', 'torso', 'left_shoulder', 'right_shoulder', 
                'left_elbow', 'right_elbow', 'left_hand', 'right_hand', 
                'hip', 'left_knee', 'right_knee', 'left_foot', 'right_foot']
    
    def apply_imu_data(self, imu_id, quaternion):
        """Apply IMU quaternion data - simplified version"""
        # In this simplified version, we just update the global rotation
        if imu_id == 1:  # Use only the first IMU for global rotation
            x_rot = quaternion[1] * 180
            y_rot = quaternion[2] * 180
            z_rot = quaternion[3] * 180
            self.rotation_x = x_rot
            self.rotation_y = y_rot
            self.rotation_z = z_rot
            self.updateGL()
        return True

class Model3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.model_viewer = Model3DViewer()
        layout.addWidget(self.model_viewer)
        self.setLayout(layout)
        
    def update_rotation(self, x, y, z):
        """Update the rotation of the model"""
        self.model_viewer.rotation_x = x
        self.model_viewer.rotation_y = y
        self.model_viewer.rotation_z = z
        self.model_viewer.updateGL()
    
    def toggle_animation(self):
        """Toggle walking animation on/off"""
        return self.model_viewer.toggle_walking()
    
    def apply_imu_data(self, imu_id, quaternion):
        """Apply IMU data to the model"""
        return self.model_viewer.apply_imu_data(imu_id, quaternion)
    
    def map_imu_to_body_part(self, imu_id, body_part):
        """Map an IMU to a body part"""
        return self.model_viewer.map_imu_to_body_part(imu_id, body_part)
    
    def get_available_body_parts(self):
        """Get list of available body parts for mapping"""
        return self.model_viewer.get_available_body_parts()
    
    def get_current_mappings(self):
        """Get current IMU to body part mappings"""
        return self.model_viewer.get_current_mappings()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Model3DWidget()
    window.show()
    sys.exit(app.exec_())
