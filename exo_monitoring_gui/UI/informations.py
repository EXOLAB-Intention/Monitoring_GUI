from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox)
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtCore import pyqtSignal
from UI.widgets.image_drop_area import ImageDropArea
from UI.back.information_back import InformationBack

class InformationWindow(QDialog):
    info_submitted = pyqtSignal(dict)

    def __init__(self, parent=None, subject_file=None, review_mode=False):
        super().__init__(parent)
        self.subject_file = subject_file
        self.setWindowTitle("Subject Information")
        self.setMinimumSize(1440, 685)

        self.input_fields = {}
        self.required_fields = ["Name", "Last Name", "Age", "Weight (kg)", "Height (cm)"]
        self.review_mode = review_mode
        # Initialize InformationBack
        self.information_back = InformationBack(self, subject_file, review_mode)
        self._setup_ui()

        if self.subject_file:
            self.information_back._load_existing_data()

    def _setup_ui(self):
        left_fields = [
            ("Name", 200, 100),
            ("Last Name", 200, 155),
            ("Age", 200, 210),
            ("Weight (kg)", 200, 265),
            ("Height (cm)", 200, 320),
        ]

        right_fields = [
            ("Thigh length (cm)", 900, 100),
            ("Shank length (cm)", 900, 155),
            ("Upperarm length (cm)", 900, 210),
            ("Forearm length (cm)", 900, 265),
        ]

        for placeholder, x, y in left_fields + right_fields:
            label = QLabel(f"{placeholder}{'*' if placeholder in self.required_fields else ''}", self)
            label.setStyleSheet("font-size: 16px;")

            if x == 200:
                label.setGeometry(x - 115, y, 150, 30)
            else:
                label_width = 175
                label_x_pos = x - label_width - 2
                label.setGeometry(label_x_pos, y, label_width, 30)

            field = QLineEdit(self)
            field.setPlaceholderText(placeholder)
            field.setGeometry(x, y, 400, 40)
            field.setStyleSheet("font-size: 16px; padding: 8px;")
            self.input_fields[placeholder] = field

            if placeholder in self.required_fields:
                field.textChanged.connect(self.information_back._check_required_fields)

            if placeholder == "Age":
                field.setValidator(QIntValidator(0, 150, self))
            elif placeholder in ["Weight (kg)", "Height (cm)", "Thigh length (cm)", "Shank length (cm)",
                                 "Upperarm length (cm)", "Forearm length (cm)"]:
                validator = QDoubleValidator(0.0, 500.0, 2, self)
                validator.setNotation(QDoubleValidator.StandardNotation)
                field.setValidator(validator)

        desc_label = QLabel("Description", self)
        desc_label.setGeometry(200, 390, 150, 30)
        self.input_fields["Description"] = QTextEdit(self)
        self.input_fields["Description"].setGeometry(200, 425, 400, 150)

        self.image_area = ImageDropArea(self)
        self.image_area.setGeometry(700, 335, 640, 240)

        req_note = QLabel("* Required fields", self)
        req_note.setGeometry(200, 580, 200, 20)
        req_note.setStyleSheet("font-size: 14px; color: #f44336;")

        self.submit_button = QPushButton("Collect Data", self)
        self.submit_button.setGeometry(550, 600, 200, 50)
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self.information_back._collect_data)
        self.information_back._set_button_style(self.submit_button, "#4CAF50", "#45a049", "#3d8b40", "#cccccc")

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setGeometry(780, 600, 200, 50)
        self.cancel_button.clicked.connect(self.close)
        self.information_back._set_button_style(self.cancel_button, "#f44336", "#d32f2f", "#b71c1c", "#aaaaaa")

    def _collect_data_notsave(self):
        data, is_valid = self.information_back._get_form_data()
        if not is_valid:
            return

        if self.subject_file:
            # Here you can add any logic that needs to be executed when collecting data without saving
            pass

        QMessageBox.information(self, "Data Collected", "Data collected successfully without saving.")
        self.info_submitted.emit(data)
