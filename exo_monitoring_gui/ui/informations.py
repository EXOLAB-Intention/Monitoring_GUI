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


class InformationWindow(QDialog):
    info_submitted = pyqtSignal(dict)

    def __init__(self, parent=None, subject_file=None):
        super().__init__(parent)
        self.subject_file = subject_file
        self.setWindowTitle("Subject Information")
        self.setMinimumSize(1440, 685)

        self.input_fields = {}
        self.required_fields = ["Name", "Last Name", "Age", "Weight (kg)", "Size (cm)"]

        self._setup_ui()

        if self.subject_file:
            self._load_existing_data()

    def closeEvent(self, event):
            # Appeler la méthode closeEvent du parent si elle existe
            if hasattr(self.parent(), 'closeEvent'):
                self.parent().closeEvent(event)
            else:
                event.accept()
                
    def _setup_ui(self):
        left_fields = [
            ("Name", 200, 100),
            ("Last Name", 200, 155),
            ("Age", 200, 210),
            ("Weight (kg)", 200, 265),
            ("Size (cm)", 200, 320),
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

            if x == 200:  # Left column (Name, Last Name, etc.)
                label.setGeometry(x - 115, y, 150, 30)  # Original geometry
            else:  # Right column (Thigh length, etc. where x is 850)
                label_width = 175  # Increased width for the label
                label_x_pos = x - label_width - 2  # Position x of the label
                label.setGeometry(label_x_pos, y, label_width, 30)

            field = QLineEdit(self)
            field.setPlaceholderText(placeholder)
            field.setGeometry(x, y, 400, 40)
            field.setStyleSheet("font-size: 16px; padding: 8px;")
            self.input_fields[placeholder] = field

            # Connect for required check
            if placeholder in self.required_fields:
                field.textChanged.connect(self._check_required_fields)

            # Set appropriate validators
            if placeholder == "Age":
                field.setValidator(QIntValidator(0, 150, self))
            elif placeholder in ["Weight (kg)", "Size (cm)", "Thigh length (cm)", "Shank length (cm)",
                                 "Upperarm length (cm)", "Forearm length (cm)"]:
                validator = QDoubleValidator(0.0, 500.0, 2, self)
                validator.setNotation(QDoubleValidator.StandardNotation)
                field.setValidator(validator)

        # Description
        desc_label = QLabel("Description", self)
        desc_label.setGeometry(200, 390, 150, 30)
        self.input_fields["Description"] = QTextEdit(self)
        self.input_fields["Description"].setGeometry(200, 425, 400, 150)

        # Image area
        self.image_area = ImageDropArea(self)
        self.image_area.setGeometry(700, 335, 640, 240)

        # Required field note
        req_note = QLabel("* Required fields", self)
        req_note.setGeometry(200, 580, 200, 20)
        req_note.setStyleSheet("font-size: 14px; color: #f44336;")

        # Buttons
        self.submit_button = QPushButton("Collect Data", self)
        self.submit_button.setGeometry(550, 600, 200, 50)
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._collect_data)
        self._set_button_style(self.submit_button, "#4CAF50", "#45a049", "#3d8b40", "#cccccc")

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setGeometry(780, 600, 200, 50)
        self.cancel_button.clicked.connect(self.reject)
        self._set_button_style(self.cancel_button, "#f44336", "#d32f2f", "#b71c1c", "#aaaaaa")

    def _set_button_style(self, button, color, hover, pressed, disabled):
        button.setStyleSheet(f"""
            QPushButton {{
                font-size: 16px;
                padding: 10px;
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {pressed}; }}
            QPushButton:disabled {{ background-color: {disabled}; color: #666666; }}
        """)

    def _check_required_fields(self):
        all_filled = all(self.input_fields[name].text().strip()
                         for name in self.required_fields)
        self.submit_button.setEnabled(all_filled)

    def _load_existing_data(self):
        try:
            data, image_path = load_metadata(self.subject_file)
            for key, widget in self.input_fields.items():
                if key in data:
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(data[key]))
                    elif isinstance(widget, QTextEdit):
                        widget.setPlainText(str(data[key]))

            if image_path and os.path.exists(image_path):
                self.image_area.load_image(image_path)

            self._check_required_fields()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")

    def _collect_data(self):
        for name in self.required_fields:
            if not self.input_fields[name].text().strip():
                QMessageBox.warning(self, "Missing Field", f"Please fill in '{name}'")
                return

        data = {}
        for key, widget in self.input_fields.items():
            data[key] = widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()

        image_path = self.image_area.get_image_path()
        if image_path:
            data["image_path"] = image_path

        data["collection_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        success = True
        if self.subject_file:
            success = save_metadata(self.subject_file, data)

        if success:
            QMessageBox.information(self, "Saved", "Information saved successfully.")
            self.info_submitted.emit(data)

            # Hide InformationWindow temporarily
            self.hide()

            # Create and execute ExperimenterDialog
            # Pass self.parent() which could be the main window or None
            self.exp_dialog = ExperimenterDialog(self.parent())
            self.exp_dialog.experimenter_name_submitted.connect(self._launch_dashboard_after_experimenter_input)
            
            # exec_() will show the dialog and block until it's closed
            if self.exp_dialog.exec_() == QDialog.Accepted:
                # If accepted, _launch_dashboard_after_experimenter_input has been called
                # and it will handle closing InformationWindow (self.accept())
                pass
            else:
                # ExperimenterDialog was cancelled or closed without submitting
                self.close() # Close InformationWindow if experimenter input is cancelled
        else:
            QMessageBox.critical(self, "Error", "Failed to save the information.")

    def _collect_data_notsave(self):
        for name in self.required_fields:
            if not self.input_fields[name].text().strip():
                QMessageBox.warning(self, "Missing Field", f"Please fill in '{name}'")
                return

        data = {}
        for key, widget in self.input_fields.items():
            data[key] = widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()

        image_path = self.image_area.get_image_path()
        if image_path:
            data["image_path"] = image_path

        data["collection_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        success = True
        if self.subject_file:
            success = save_metadata(self.subject_file, data)

        if success:
            QMessageBox.information(self, "Saved", "Information saved successfully.")
            self.info_submitted.emit(data)
        else:
            QMessageBox.critical(self, "Error", "Failed to save the information.")

    def _launch_dashboard_after_experimenter_input(self, experimenter_name):
        """Lauches the DashboardApp after experimenter name is submitted."""
        # experimenter_name is available here if needed for the dashboard
        # For now, we just launch the dashboard.
        
        # Store the dashboard instance on self to prevent garbage collection if it's not a top-level window by default
        # QMainWindow instances usually manage their own lifecycle when shown.
        self.dashboard_instance = DashboardApp()
        self.dashboard_instance.show()
        
        self.accept() # Close the InformationWindow now that the flow is complete

def createInformationWindow(parent=None, subject_file=None):
    return InformationWindow(parent, subject_file)
