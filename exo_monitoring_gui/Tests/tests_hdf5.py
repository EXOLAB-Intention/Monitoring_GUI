from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import Qt, QMimeData, QRect
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor, QPen
import sys

# Variables pour gérer les incrémentations
head = {"pMMG": 0, "IMU": 0, "EMG": 0}
y = {"pMMG": 0, "IMU": 0, "EMG": 0}
torse = {"pMMG": 0, "IMU": 0, "EMG": 0}
right_arm = {"pMMG": 0, "IMU": 0, "EMG": 0}
left_arm = {"pMMG": 0, "IMU": 0, "EMG": 0}
right_hand = {"pMMG": 0, "IMU": 0, "EMG": 0}
left_hand = {"pMMG": 0, "IMU": 0, "EMG": 0}
right_leg = {"pMMG": 0, "IMU": 0, "EMG": 0}
left_leg = {"pMMG": 0, "IMU": 0, "EMG": 0}
right_foot = {"pMMG": 0, "IMU": 0, "EMG": 0}
left_foot = {"pMMG": 0, "IMU": 0, "EMG": 0}
hip = {"pMMG": 0, "IMU": 0, "EMG": 0}
pMMG = 8
IxMU = 6
ExMG = 6

visualization_mode = False

class DraggableLabel(QLabel):
    def __init__(self, text, drag_id, nombre, parent=None):
        super().__init__(text, parent)
        self.drag_id = drag_id
        self.nombre = nombre
        self.setStyleSheet(f"background: lightblue; padding: 5px; border: 1px solid black;")

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.drag_id)  # Texte principal : drag_id
            mime.setData("application/nombre", str(self.nombre).encode())  # Ajout de nombre en data
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)



# Classe personnalisée pour le label avec visualisation des zones
class BodyZoneLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.visualization_mode = False
        self.zones = []
        self.setup_zones()
        
    def setup_zones(self):
        # Hauteurs
        head_height = 95
        shoulder_height = 100
        torso_height = 180
        hip_height = 195
        leg_height = 384
        
        # Largeurs et position centrale
        center_x = 108
        
        # Définir toutes les zones (nom, rect, couleur)
        self.zones = [
            ("Tête", QRect(center_x-35, 0, 70, head_height), QColor(255, 0, 0, 100)),
            ("Torse", QRect(center_x-20, head_height, 45, torso_height-head_height), QColor(0, 255, 0, 100)),
            ("Bras droit", QRect(0, head_height, center_x-20, shoulder_height+45-head_height), QColor(0, 0, 255, 100)),
            ("Main droite", QRect(0, shoulder_height+45, center_x-60, torso_height-(shoulder_height+30)), QColor(255, 255, 0, 100)),
            ("Bras gauche", QRect(center_x+25, head_height, center_x, shoulder_height+45-head_height), QColor(0, 0, 255, 100)),
            ("Main gauche", QRect(center_x+75, shoulder_height+45, center_x, torso_height-(shoulder_height+30)), QColor(255, 255, 0, 100)),
            ("Bassin", QRect(center_x-30, torso_height, 60, hip_height-torso_height), QColor(255, 0, 255, 100)),
            ("Jambe droite", QRect(center_x-35, hip_height, 33, leg_height-80-hip_height), QColor(0, 255, 255, 100)),
            ("Jambe gauche", QRect(center_x+2, hip_height, 33, leg_height-80-hip_height), QColor(0, 255, 255, 100)),
            ("Pied droit", QRect(center_x-35, leg_height-80, 33, 80), QColor(128, 128, 0, 100)),
            ("Pied gauche", QRect(center_x+2, leg_height-80, 33, 80), QColor(128, 128, 0, 100))
        ]
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.visualization_mode:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            for name, rect, color in self.zones:
                # Dessiner le rectangle
                painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 200), 2))
                painter.setBrush(color)
                painter.drawRect(rect)
                
                # Ajouter le nom de la zone
                painter.setPen(Qt.black)
                text_x = rect.x() + 5
                text_y = rect.y() + 15
                painter.drawText(text_x, text_y, name)
    
    def toggle_visualization(self):
        self.visualization_mode = not self.visualization_mode
        self.update()  # Déclencher un nouveau paintEvent
    
    # Gestion des événements de drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
    
    def dropEvent(self, event):
        global head, y, torse, right_arm, left_arm, right_hand, left_hand, right_leg, left_leg, right_foot, left_foot, hip, pMMG, IxMU, ExMG
        
        pos = event.pos()  # Position du drop par rapport au label
        drag_id = event.mimeData().text() 
        
        hip_height = 195       # Fin du bassin
        leg_height = 384       # Hauteur totale
        
        center_x = 108
        
        # Vérifier la zone touchée en se basant sur les rectangles définis
        hit_zone = None
        for name, rect, color in self.zones:
            if rect.contains(pos):
                hit_zone = name
                break
        
        # Afficher l'ID du drag et la zone touchée
        print(f"Drop de l'élément {drag_id} sur la zone: {hit_zone if hit_zone else 'non définie'}")
        
        # Mise à jour des compteurs selon la zone touchée
        if hit_zone == "Tête":
            head[drag_id] += 1
            print(f"Tête touchée par {drag_id}: {head}")
        
        elif hit_zone == "Torse":
            torse[drag_id] += 1
            print(f"Torse touché par {drag_id}: {torse}")
        
        elif hit_zone == "Bras droit":
            right_arm[drag_id] += 1
            print(f"Bras droit touché par {drag_id}: {right_arm}")
        
        elif hit_zone == "Main droite":
            right_hand[drag_id] += 1
            print(f"Main droite touchée par {drag_id}: {right_hand}")
        
        elif hit_zone == "Bras gauche":
            left_arm[drag_id] += 1
            print(f"Bras gauche touché par {drag_id}: {left_arm}")
        
        elif hit_zone == "Main gauche":
            left_hand[drag_id] += 1
            print(f"Main gauche touchée par {drag_id}: {left_hand}")
        
        elif hit_zone == "Bassin":
            hip[drag_id] += 1
            print(f"Bassin touché par {drag_id}: {hip}")
        
        elif hit_zone == "Jambe droite":
            right_leg[drag_id] += 1
            print(f"Jambe droite touchée par {drag_id}: {right_leg}")
        
        elif hit_zone == "Jambe gauche":
            left_leg[drag_id] += 1
            print(f"Jambe gauche touchée par {drag_id}: {left_leg}")
        
        elif hit_zone == "Pied droit":
            right_foot[drag_id] += 1
            print(f"Pied droit touché par {drag_id}: {right_foot}")
        
        elif hit_zone == "Pied gauche":
            left_foot[drag_id] += 1
            print(f"Pied gauche touchée par {drag_id}: {left_foot}")
        
        else:
            # Zone entre les jambes ou non définie
            if hip_height < pos.y() < leg_height - 80 and center_x-2 < pos.x() < center_x+2:
                hip += 1
                print(f"Entre les jambes touché par {drag_id}")
            else:
                print(f"Zone non définie touchée par {drag_id} à la position {pos.x()}, {pos.y()}")
        


# Application principale
app = QApplication([])

# Fenêtre principale avec un peu plus d'espace
win = QWidget()
win.setWindowTitle("Drag & Drop sur image avec multiples éléments")
win.setGeometry(100, 100, 800, 900)

# Layout principal
main_layout = QVBoxLayout()

# Layout pour les éléments draggables
drag_layout = QHBoxLayout()

# Créer plusieurs éléments draggables
drag_items = [
    DraggableLabel("pMMG", 'pMMG',8, win),
    DraggableLabel("IMU", "IMU",6, win),
    DraggableLabel("EMG", "EMG",6, win)
]

# Ajouter les éléments draggables au layout
for item in drag_items:
    drag_layout.addWidget(item)

# Layout pour l'image et le bouton
image_layout = QVBoxLayout()

# Label personnalisé pour l'image avec zones
label_drop = BodyZoneLabel(win)
pixmap = QPixmap("C:/Users/samio/Documents/BUT/BUT2/stage/travail/Monitoring-GUI/Tests/personne.png")
label_drop.setPixmap(pixmap.scaled(216, 384, Qt.KeepAspectRatio))
label_drop.setStyleSheet("background: lightgray; padding: 5px;")

# Bouton pour activer/désactiver la visualisation des zones
toggle_button = QPushButton("Afficher/Masquer les zones", win)
toggle_button.clicked.connect(label_drop.toggle_visualization)

# Ajouter image et bouton au layout
image_layout.addWidget(label_drop)
image_layout.addWidget(toggle_button)
image_layout.addStretch()

# Assembler les layouts
main_layout.addLayout(drag_layout)
main_layout.addLayout(image_layout)

# Appliquer le layout principal
win.setLayout(main_layout)

win.show()
sys.exit(app.exec())