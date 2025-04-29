from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QPixmap, QDrag
import sys, os

class DraggableLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet("background-color: lightblue; border: 1px solid black; padding: 5px;")

    def mouseMoveEvent(self, event):
        if event.buttons() != Qt.LeftButton:
            return

        # Création du drag
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

class ImageDropLabel(QLabel):
    def __init__(self):
        super().__init__()
        base_dir = os.path.dirname(__file__)
        image_path = os.path.join(base_dir, "f.jpg")

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.setText("❌ Image non chargée.")
        else:
            self.setPixmap(pixmap.scaled(300, 200, Qt.KeepAspectRatio))

        self.setAcceptDrops(True)
        self.setStyleSheet("border: 2px dashed gray;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text()
        self.setText(text)
        self.setStyleSheet("color: white; font-weight: bold; background-color: rgba(0,0,0,150);")

app = QApplication(sys.argv)
window = QWidget()
layout = QVBoxLayout(window)

# Label que l'utilisateur peut faire glisser
drag_label = DraggableLabel("Glisser ce texte")

# Label image qui accepte les drops
image_label = ImageDropLabel()

layout.addWidget(drag_label)
layout.addWidget(image_label)

window.show()
sys.exit(app.exec_())
