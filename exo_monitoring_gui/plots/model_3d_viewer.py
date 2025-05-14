import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtOpenGL import QGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *

class Model3DViewer(QGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0
        self.last_pos = None
        self.vertices = []
        self.faces = []
        self.load_obj('path/to/your/human_model.obj')

    def load_obj(self, file_path):
        """Charge un modèle 3D au format .obj."""
        self.vertices = []
        self.faces = []

        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if line.startswith('v '):  # Ligne définissant un sommet
                        parts = line.strip().split()
                        vertex = list(map(float, parts[1:4]))
                        self.vertices.append(vertex)
                    elif line.startswith('f '):  # Ligne définissant une face
                        parts = line.strip().split()
                        face = [int(idx.split('/')[0]) - 1 for idx in parts[1:]]
                        self.faces.append(face)
        except Exception as e:
            print(f"Erreur lors du chargement du fichier .obj : {e}")

    def calculate_model_center(self):
        """Calcule le centre géométrique du modèle."""
        if not self.vertices:
            return [0, 0, 0]

        x_coords = [v[0] for v in self.vertices]
        y_coords = [v[1] for v in self.vertices]
        z_coords = [v[2] for v in self.vertices]

        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        center_z = sum(z_coords) / len(z_coords)

        return [center_x, center_y, center_z]

    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()

        self.rotation_x += dy
        self.rotation_y += dx

        self.last_pos = event.pos()
        self.updateGL()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        gluLookAt(0, 0, 10, 0, 0, 0, 0, 1, 0)

        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        glRotatef(self.rotation_z, 0, 0, 1)

        # Recentre le modèle
        center = self.calculate_model_center()
        glTranslatef(-center[0], -center[1], -center[2])

        if hasattr(self, 'vertices') and hasattr(self, 'faces'):
            self.draw_model()
        else:
            self.draw_cube()  # Fallback si aucun modèle n'est chargé

    def draw_model(self):
        glBegin(GL_TRIANGLES)
        for face in self.faces:
            for vertex_idx in face:
                glVertex3fv(self.vertices[vertex_idx])
        glEnd()

class Model3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.model_viewer = Model3DViewer()
        layout.addWidget(self.model_viewer)
        self.setLayout(layout)

        # Remplacez "human_model.obj" par le chemin de votre fichier .obj
        self.model_viewer.load_obj("path/to/human_model.obj")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Model3DWidget()
    window.show()
    sys.exit(app.exec_())
