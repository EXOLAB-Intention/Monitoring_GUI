from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QMessageBox, QLabel, QVBoxLayout,QTextEdit, QFileDialog
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import pandas as pd

def createInformationWindow():
    info_window = QWidget()
    info_window.setWindowTitle("Information")
    info_window.setGeometry(250, 250, 1440, 685)

    input_fields = {}

    labeling = [
        ("Name", 125, 75),
        ("Last Name", 85,130),
        ("Age", 140,185),
        ("Weight", 115,240),
        ("Size", 140,295),
        ("Thigh length (cm)", 687, 75),
        ("Shank length (cm)", 685, 130),
        ("Upperarm length (cm)", 655, 185),
        ("Forearm length (cm)", 668, 240),
    ]
    for label, x, y in labeling:
        labels = QLabel(label, info_window)
        labels.setGeometry(x, y, 450, 100)
        labels.setStyleSheet("font-size: 18px; color: black; padding: 10px;")

    # Champs de saisie
    fields = [
        ("Name", 200,100),
        ("Last Name", 200,155),
        ("Age", 200,210),
        ("Weight", 200,265),
        ("Size", 200,320),
        ("Thigh length (cm)", 850, 100),
        ("Shank length (cm)", 850, 155),
        ("Upperarm length (cm)", 850, 210),
        ("Forearm length (cm)", 850, 265),


    ]

    for placeholder,x ,y in fields:
        line_edit = QLineEdit(info_window)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setGeometry(x, y, 400, 50)
        line_edit.setStyleSheet("font-size: 16px; padding: 10px;")
        input_fields[placeholder] = line_edit

    description = QLineEdit(info_window)
    description.setPlaceholderText("Description")
    description.setGeometry(200, 425, 400, 150)
    description.setStyleSheet("font-size: 16px; padding: 10px;")
    input_fields["Description"] = description

    image_area = ImageDropArea(info_window)
    image_area.setGeometry(700, 335, 640, 240)
    input_fields["Images"] = image_area


    def collectData():
        data = {key: field.text() for key, field in input_fields.items()}
        print("Collected Data:", data)

        df = pd.DataFrame([data])
        df.to_hdf("participants.h5", key="participants", mode="w")

        df = pd.read_hdf("participants.h5", key="participants")
        print(df)

        msg = QMessageBox(info_window)
        msg.setWindowTitle("Infos collectées")
        msg.setText("\n".join(f"{k}: {v}" for k, v in data.items()))
        msg.exec_()

    # Bouton positionné manuellement
    submit_button = QPushButton("Collect Data", info_window)
    submit_button.setGeometry(250, 200, 200, 50)
    submit_button.clicked.connect(collectData)

    return info_window






class ImageDropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Cliquez ou glissez une image ici")
        self.setStyleSheet("""
            border: 2px dashed #aaa;
            font-size: 16px;
            color: #555;
            background-color: #f9f9f9;
            padding: 20px;
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasImage() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_url = event.mimeData().urls()[0].toLocalFile()
            self.setPixmap(QPixmap(file_url).scaledToWidth(300, Qt.SmoothTransformation))

    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.setPixmap(QPixmap(file_path).scaledToWidth(300, Qt.SmoothTransformation))