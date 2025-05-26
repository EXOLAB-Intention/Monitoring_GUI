from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QFileDialog, QApplication, QWidget
)
from datetime import datetime
from UI.review import Review
from utils.hdf5_utils import load_metadata, save_metadata
import os
from plots.dashboard_app import DashboardApp
from UI.experimenter_dialogue import ExperimenterDialog



class InformationBack(QWidget):
    def __init__(self, parent=None, subject_file=None, review_mode=False):
        super().__init__(parent)
        self.parent = parent
        self.subject_file = subject_file
        self.review_mode = review_mode

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
        all_filled = all(self.parent.input_fields[name].text().strip()
                         for name in self.parent.required_fields)
        self.parent.submit_button.setEnabled(all_filled)

    def _load_existing_data(self):
        try:
            data_from_file, image_file_path = load_metadata(self.parent.subject_file)

            if not data_from_file:
                print(f"Avertissement : Aucune métadonnée de participant n'a été chargée depuis {self.parent.subject_file}")

            for field_display_key, widget in self.parent.input_fields.items():
                normalized_participant_key = f"participant_{field_display_key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

                if normalized_participant_key in data_from_file:
                    value_to_set = data_from_file[normalized_participant_key]
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(value_to_set))
                    elif isinstance(widget, QTextEdit):
                        widget.setPlainText(str(value_to_set))

            if image_file_path and os.path.exists(image_file_path):
                self.parent.image_area.load_image(image_file_path)

            self._check_required_fields()
        except Exception as e:
            import traceback
            error_message = f"Erreur lors du chargement des données dans le formulaire : {str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(self.parent, "Erreur de chargement", error_message)
            print(error_message)

    def _get_form_data(self):
        print("Collecting form data...")
        for name in self.parent.required_fields:
            if not self.parent.input_fields[name].text().strip():
                QMessageBox.warning(self.parent, "Missing Field", f"Please fill in '{name}'")
                return None, False

        data = {}
        for key, widget in self.parent.input_fields.items():
            data[key] = widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()

        image_path = self.parent.image_area.get_image_path()
        if image_path:
            data["image_path"] = image_path

        data["collection_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("C'est bon !")
        print(data)
        return data, True

    def _collect_data(self):
        data, is_valid = self._get_form_data()
        if not is_valid:
            return

        success = True
        if self.parent.subject_file:
            success = save_metadata(self.parent.subject_file, data)

        if success:
            QMessageBox.information(self.parent, "Saved", "Information saved successfully.")
            self.parent.info_submitted.emit(data)
            if self.parent.review_mode:
                for widget in QApplication.topLevelWidgets():
                    if widget is not self.parent:
                        widget.close()
                self.parent.close()

                review = Review(self.parent, self.parent.subject_file)
                review.show()
                return
            else:
                self.parent.hide()
                self.parent.exp_dialog = ExperimenterDialog(self.parent)
                self.parent.exp_dialog.experimenter_name_submitted.connect(self._launch_dashboard_after_experimenter_input)
                self.parent.exp_dialog.closeEvent = self.parent.parent().main_bar._save_and_saveas_closed()
                self.parent.modified = False

                if self.parent.exp_dialog.exec_() == QDialog.Accepted:
                    pass
                else:
                    self.parent.close()
        else:
            QMessageBox.critical(self.parent, "Error", "Failed to save the information.")

    def _launch_dashboard_after_experimenter_input(self, experimenter_name):
        self.parent.dashboard_instance = DashboardApp()
        self.parent.dashboard_instance.showMaximized()

        top_level_widgets = QApplication.topLevelWidgets()
        for widget in top_level_widgets:
            if widget != self.parent.dashboard_instance:
                widget.close()

        self.parent.dashboard_instance.activateWindow()
