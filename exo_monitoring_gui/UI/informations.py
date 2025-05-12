from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QPixmap, QIntValidator, QDoubleValidator
from PyQt5.QtCore import Qt, pyqtSignal
from datetime import datetime
from ui.widgets.image_drop_area import ImageDropArea
from utils.hdf5_utils import load_metadata, save_metadata
import os
from plots.dashboard_app import DashboardApp
from ui.experimenter_dialogue import ExperimenterDialog


def createInformationWindow():
    info_window = QWidget()
    info_window.setWindowTitle("Information")
    info_window.setGeometry(100, 100, 800, 500)

    input_fields = {}

    fields = [
        ("Name", 50),
        ("Last Name", 120),
        ("Age", 190),
        ("Weight", 260),
        ("Size", 330),
        ("Experiment Protocol", 400)
    ]

    for placeholder, y in fields:
        line_edit = QLineEdit(info_window)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setGeometry(50, y, 200, 50)
        line_edit.setStyleSheet("font-size: 16px; padding: 10px;")
        input_fields[placeholder] = line_edit

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

    submit_button = QPushButton("Collect Data", info_window)
    submit_button.setGeometry(400, 400, 200, 50)
    submit_button.clicked.connect(collectData)

    return info_window

