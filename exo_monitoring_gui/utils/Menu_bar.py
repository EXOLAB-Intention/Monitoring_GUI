import shutil
from PyQt5.QtWidgets import (QMainWindow, QPushButton, QLabel, QAction, QFileDialog,
                             QMessageBox, QVBoxLayout, QWidget, QProgressBar, QDialog, QTextEdit, QHBoxLayout, QApplication)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
import h5py
import os
import re
from datetime import datetime
from UI.informations import InformationWindow
from utils.hdf5_utils import load_metadata, save_metadata, copy_all_data_preserve_root_metadata
from UI.back.main_window_back import MainAppBack
from utils.file_receiver import request_files, SERVER_IP, PORT, OUT_DIR
class MainBar:
    def __init__(self, main_app):
        self.main_app = main_app
        self.main_app_back = MainAppBack(self.main_app)

    def create_new_subject(self):
        """Creates a new subject file and opens information window"""
        if self.main_app.modified:
            reply = QMessageBox.question(
                self.main_app,
                'Unsaved Changes',
                'There are unsaved changes. Save before creating new subject?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self.save_subject_notsave()
            elif reply == QMessageBox.Cancel:
                return

        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.main_app,
            "Create New Subject File",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            if not filename.endswith(".h5") and not filename.endswith(".hdf5"):
                filename += ".h5"

            try:
                # Initialize basic file structure
                with h5py.File(filename, 'w') as f:
                    f.attrs['subject_created'] = True
                    f.attrs['creation_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.create_group('metadata')
                    f.create_group('trials')

                self.main_app.current_subject_file = filename
                self.main_app.modified = False
                self.save_subject_action.setEnabled(True)
                self.save_subject_as_action.setEnabled(True)
                self.show_metadata_action.setEnabled(True)

                self.main_app.statusBar().showMessage(f"New subject file created: {os.path.basename(filename)}")

                # Display information window to collect metadata
                self.main_app.info_window = InformationWindow(self.main_app, self.main_app.current_subject_file)
                self.main_app.info_window.info_submitted.connect(self.main_app_back.update_subject_metadata)
                self.create_subject_action.setEnabled(False)
                self.load_subject_action.setEnabled(False)
                self.load_existing_trial.setEnabled(False)

                def closeEvent(event):
                    self.create_subject_action.setEnabled(True)
                    self.load_subject_action.setEnabled(True)
                    self.load_existing_trial.setEnabled(True)
                    self.save_subject_action.setEnabled(False)
                    self.save_subject_as_action.setEnabled(False)
                    self.show_metadata_action.setEnabled(False)
                    event.accept()

                self.main_app.info_window.closeEvent = closeEvent
                self.main_app.info_window.show()

            except Exception as e:
                self.main_app_back._show_error(f"Error creating subject file: {str(e)}")

    # Add other methods of MainBar here

    def load_existing_subject(self, review=False):
        """Load an existing subject file"""
        if self.main_app.modified:
            reply = QMessageBox.question(self.main_app, 'Unsaved Changes',
                                        'There are unsaved changes. Save before loading a new subject?',
                                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self.save_subject_notsave()
            elif reply == QMessageBox.Cancel:
                return


        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(
            self.main_app,
            "Open Subject File",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            try:
                with h5py.File(filename, 'r') as f:
                    if 'subject_created' in f.attrs:
                        # Load metadata
                        data, image_path = load_metadata(filename)

                        # Update the current file and UI
                        self.main_app.current_subject_file = filename
                        self.main_app.modified = False
                        self.save_subject_action.setEnabled(True)
                        self.save_subject_as_action.setEnabled(True)
                        self.show_metadata_action.setEnabled(True)

                        # Update the status bar
                        self.main_app.statusBar().showMessage(f"Loaded subject file: {os.path.basename(filename)}")

                        if 'trials' in f:
                            pass

                        self.main_app.info_window = InformationWindow(self.main_app, self.main_app.current_subject_file, review)
                        self.main_app.info_window.info_submitted.connect(self.main_app_back.update_subject_metadata)
                        self.create_subject_action.setEnabled(False)
                        self.load_subject_action.setEnabled(False)
                        self.load_existing_trial.setEnabled(False)

                        def closeEvent(event):
                            self.create_subject_action.setEnabled(True)
                            self.load_subject_action.setEnabled(True)
                            self.load_existing_trial.setEnabled(True)
                            self.save_subject_action.setEnabled(False)
                            self.save_subject_as_action.setEnabled(False)
                            self.show_metadata_action.setEnabled(False)
                            event.accept()

                        self.main_app.info_window.closeEvent = closeEvent
                        self.main_app.info_window.show()

                    else:
                        self.main_app_back._show_error("Not a valid subject file. Missing required attributes.")
                        return

            except Exception as e:
                self.main_app_back._show_error(f"Error loading subject file: {str(e)}")
                return
    



    def save_subject(self):
        """Save the current subject file"""
        if not self.main_app.current_subject_file:
            return self.save_subject_as()
        else:
            self.main_app.info_window._collect_data()
        try:
            # Logic to save data to current file
            # This is a placeholder - your actual save logic might be more complex
            self.main_app.modified = False
            self.main_app.statusBar().showMessage(f"Saved to {os.path.basename(self.main_app.current_subject_file)}")
            return True
        except Exception as e:
            self.main_app_back._show_error(self.main_app,f"Error saving subject: {str(e)}")
            return False

    def save_subject_notsave(self):
        """Save the current subject file"""
        if not self.main_app.current_subject_file:
            return self.save_subject_as()
        else:
            print("Saving subject without saving data")
            self.main_app.info_window._collect_data_notsave()
        try:
            self.main_app.modified = False
            self.main_app.statusBar().showMessage(f"Saved to {os.path.basename(self.main_app.current_subject_file)}")
            return True
        except Exception as e:
            self.main_app_back._show_error(self.main_app,f"Error saving subject: {str(e)}")
            return False

    def save_subject_as(self):
        """Save the subject file with a new name"""
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.main_app,
            "Save Subject As",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            if not filename.endswith(".h5") and not filename.endswith(".hdf5"):
                filename += ".h5"

            self.main_app.current_subject_file = filename
            return self.save_subject()
        return False

    def save_subject_as_notsave(self):
        """Save the subject file with a new name"""
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.main_app,
            "Save Subject As",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            if not filename.endswith(".h5") and not filename.endswith(".hdf5"):
                filename += ".h5"
            print("Saving subject without saving data")
            self.main_app.current_subject_file = filename
            return self.save_subject_notsave()
        return False
    

    def save_experiment_protocol_as(self, parent):
        if not parent.file_path:
            print("Aucun fichier source ouvert.")
            return

        text = parent.experiment_protocol_text.toPlainText()
        if not text:
            return

        # Boîte de dialogue pour choisir un nouveau fichier .h5
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Enregistrer le protocole expérimental sous...",
            "",
            "Fichiers HDF5 (*.h5);;Tous les fichiers (*)"
        )

        if not file_path:
            return  # L'utilisateur a annulé

        try:
            # Étape 1 : Copier tout le fichier original dans le nouveau
            shutil.copy(parent.file_path, file_path)

            # Étape 2 : Modifier ou ajouter la métadonnée 'experiment_protocol'
            with h5py.File(file_path, 'a') as f:
                f.attrs.modify('experiment_protocol', text)

            print(f"✅ Fichier sauvegardé avec succès dans {file_path}")

        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde : {e}")


    def save_experiment_protocol(self, parent):
        if not parent.file_path:
            return
        text = parent.experiment_protocol_text.toPlainText()
        if not text:
            return
        try:
            with h5py.File(parent.file_path, 'a') as f:
                # Ajoute ou met à jour la métadonnée à la racine
                f.attrs.modify('experiment_protocol', text)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du protocole expérimental : {e}")

    def load_experiment_protocol(self, parent):
        """Charge le protocole expérimental depuis les métadonnées si présent."""
        if not parent.file_path:
            return
        try:
            with h5py.File(parent.file_path, 'r') as f:
                if 'experiment_protocol' in f.attrs:
                    text = f.attrs['experiment_protocol']
                    if isinstance(text, bytes):
                        text = text.decode('utf-8')
                    parent.experiment_protocol_text.setPlainText(text)
        except Exception as e:
            print(f"Erreur lors du chargement du protocole expérimental : {e}")

    def show_metadata(self):
        """Display metadata of the current subject"""
        if hasattr(self.main_app, 'current_subject_file'):
            file_path = self.main_app.current_subject_file
        elif hasattr(self.main_app, 'file_path'):
            file_path = self.main_app.file_path
        else:
            QMessageBox.information(self.main_app, "No Subject", "Please open or create a subject first.")
            return

        try:
            data, image_path = load_metadata(file_path)     

            if not data:
                QMessageBox.information(self.main_app, "No Metadata", "No metadata available for this subject.")
                return

            # Create a formatted text to display metadata
            metadata_text = "<h2>Subject Metadata</h2>"
            metadata_text += "<table style='border-collapse: collapse; width: 100%;'>"

            # Personal information section
            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Personal Information</th></tr>"

            # Add personal info fields if they exist
            for field in ["participant_name", "participant_last_name", "participant_age", "participant_weight_kg", "participant_height_cm"]:
                if field in data:
                    metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>{field}</b></td>"
                    metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data[field]}</td></tr>"

            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Anthropometric Measurements</th></tr>"

            for field in ["participant_thigh_length_cm", "participant_shank_length_cm", "participant_upperarm_length_cm", "participant_forearm_length_cm"]:
                if field in data:
                    metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>{field}</b></td>"
                    metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data[field]}</td></tr>"

            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Collection Information</th></tr>"

            if "participant_collection_date" in data:
                metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>Collection Date</b></td>"
                metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data['participant_collection_date']}</td></tr>"

            # Add experimenter name if it exists
            if "last_modified" in data:
                metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>Last modification</b></td>"
                metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data['last_modified']}</td></tr>"

            metadata_text += "</table>"

            # Description if it exists
            if "participant_description" in data and data["participant_description"]:
                metadata_text += f"<h3>Description</h3><p>{data['participant_description']}</p>"

            # Display image if it exists
            if image_path and os.path.exists(image_path):
                # Create a dialog to display the metadata
                dialog = QDialog(self.main_app)
                dialog.setWindowTitle("Subject Metadata")
                dialog.setMinimumWidth(600)

                layout = QVBoxLayout(dialog)

                # Image at the top
                image_label = QLabel()
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    layout.addWidget(image_label)

                # Metadata below
                metadata_browser = QTextEdit()
                metadata_browser.setReadOnly(True)
                metadata_browser.setHtml(metadata_text)
                layout.addWidget(metadata_browser)

                # Button at the bottom
                button_box = QWidget()
                button_layout = QHBoxLayout(button_box)
                close_button = QPushButton("Close")
                close_button.clicked.connect(dialog.accept)
                button_layout.addStretch()
                button_layout.addWidget(close_button)

                layout.addWidget(button_box)

                dialog.exec_()
            else:
                # Just show the metadata without an image
                metadata_dialog = QMessageBox()
                metadata_dialog.setWindowTitle("Subject Metadata")
                metadata_dialog.setTextFormat(Qt.RichText)
                metadata_dialog.setText(metadata_text)
                metadata_dialog.setStandardButtons(QMessageBox.Ok)
                metadata_dialog.exec_()

        except Exception as e:
            self.main_app_back._show_error(self.main_app,f"Error displaying metadata: {str(e)}")


    def show_about_dialog(self):
        """Show information about the software"""
        about_text = """
        <h1>Data Monitoring Software</h1>
        <p>Version 2.5.0</p>
        <p>An advanced monitoring tool for exoskeleton data.</p>
        <p>© 2025 Advanced Exoskeleton Research Laboratory</p>
        <p>For help and documentation, please visit our website or contact support.</p>
        """

        QMessageBox.about(self.main_app, "About Data Monitoring Software", about_text)

    def _create_action(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False):
        """Create a QAction with the given properties"""
        action = QAction(text, self.main_app)
        if icon:
            action.setIcon(icon)
        if shortcut:
            action.setShortcut(shortcut)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot:
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action

    def _create_menubar(self):
        """Create the application menu bar"""
        menubar = self.main_app.menuBar()

        # File menu
        file_menu = menubar.addMenu('&File')

        # File menu actions
        self.create_subject_action = self._create_action(
            "&Create new subject",
            lambda: self.create_new_subject(),
            "Ctrl+N"
        )

        self.load_subject_action = self._create_action(
            "&Load existing subject",
            lambda: self.load_existing_subject(),
            "Ctrl+O",
            tip="Load an existing subject file"
        )

        self.save_subject_action = self._create_action(
            "&Save subject",
            lambda: self.save_subject_notsave(),
            "Ctrl+S",
            tip="Save the current subject"
        )

        self.save_subject_as_action = self._create_action(
            "Save subject &as...",
            lambda: self.save_subject_as_notsave(),
            "Ctrl+Shift+S",
            tip="Save the subject with a new name"
        )

        self.show_metadata_action = self._create_action(
            "&Show metadata",
            lambda: self.show_metadata(),
            "Ctrl+M",
            tip="Display subject metadata"
        )

        self.load_existing_trial = self._create_action(
            "Load existing trial",
            lambda: self.load_existing_subject(True),
            "Ctrl+F",
            tip="Load an existing trial"
        )

        self.Save_current_trial = self._create_action(
            "&Save current trial",
            lambda: self.save_experiment_protocol(),
            "Ctrl+M",
            tip="Save a current trial"
        )

        self.Save_current_trial_as = self._create_action(
            "&Save current trial as...",
            lambda: self.save_experiment_protocol_as(),
            "Ctrl+M",
            tip="Save current trial in a new file"
        )

        self.Save_current_plotas_image = self._create_action(
            "&Save current plotas image",
            lambda: self.show_metadata(),
            "Ctrl+M",
            tip="Save current plotas image"
        )

        self.exit_action = self._create_action(
            "E&xit",
            lambda: self.main_app.close,
            "Alt+F4",
            tip="Exit the application"
        )

        # Add actions to file menu
        file_menu.addAction(self.create_subject_action)
        file_menu.addAction(self.load_subject_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_subject_action)
        file_menu.addAction(self.save_subject_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.load_existing_trial)
        file_menu.addAction(self.Save_current_trial)
        file_menu.addAction(self.Save_current_trial_as)
        file_menu.addAction(self.Save_current_plotas_image)
        file_menu.addSeparator()
        file_menu.addAction(self.show_metadata_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Help menu
        help_menu = menubar.addMenu('&Help')

        # Help menu actions
        about_action = self._create_action(
            "&About",
            lambda: self.show_about_dialog(),
            tip="About the application"
        )

        # Add actions to help menu
        help_menu.addAction(about_action)

        # Initially disable actions that require an open file
        self.Save_current_trial.setEnabled(False)
        self.Save_current_trial_as.setEnabled(False)
        self.Save_current_plotas_image.setEnabled(False)

        self.save_subject_action.setEnabled(False)
        self.save_subject_as_action.setEnabled(False)
        self.show_metadata_action.setEnabled(False)

    def _all_false_or_true(self, boold):
        for attr_name in [
            "create_subject_action",
            "load_subject_action",
            "save_subject_action",
            "save_subject_as_action",
            "load_existing_trial",
            "Save_current_trial",
            "Save_current_trial_as",
            "Save_current_plotas_image",
            "show_metadata_action",
            "exit_action"
        ]:
            action = getattr(self, attr_name, None)
            if action is not None:
                action.setEnabled(boold)


    def _save_and_saveas_closed(self):
        self.save_subject_action.setEnabled(False)
        self.save_subject_as_action.setEnabled(False)

    def clear_plot(self):
        """Clear all plots while maintaining settings."""
        if hasattr(self.main_app, 'clear_plots_from_menu'):
            self.main_app.clear_plots_from_menu()
        elif hasattr(self.main_app, 'clear_all_plots'):
            self.main_app.clear_all_plots()
        else:
            print("[WARNING] clear plots method not found in main_app")

    def refresh_the_connected_system(self):
        """Refresh the connected system and allow modification of sensor mappings."""
        from PyQt5.QtWidgets import QMessageBox
        
        # Vérifier si on a accès à l'interface principale pour ouvrir le dialogue de mapping
        if hasattr(self.main_app, 'backend') and hasattr(self.main_app.backend, 'sensor_config') and self.main_app.backend.sensor_config:
            try:
                print("[DEBUG] Opening sensor mapping dialog...")
                
                # Vérifier que le backend a les méthodes nécessaires
                if not hasattr(self.main_app.backend, 'get_current_mappings_for_dialog'):
                    QMessageBox.warning(
                        self.main_app,
                        "Configuration Unavailable",
                        "The sensor configuration method is not available in the backend."
                    )
                    return
                
                # Obtenir les mappings actuels
                curr_maps = self.main_app.backend.get_current_mappings_for_dialog()
                print(f"[DEBUG] Current mappings: {curr_maps}")
                
                # Importer et créer le dialogue directement
                from plots.sensor_dialogue import SensorMappingDialog
                
                # Créer le dialogue avec des paramètres explicites
                dialog = SensorMappingDialog(self.main_app, curr_maps, None)
                
                # Connecter le signal
                if hasattr(self.main_app.backend, 'update_sensor_mappings'):
                    dialog.mappings_updated.connect(self.main_app.backend.update_sensor_mappings)
                
                # ✅ SOLUTION : Utiliser exec_() pour afficher le dialogue de manière modale
                print("[DEBUG] Showing dialog...")
                result = dialog.exec_()
                
                if result == dialog.Accepted:
                    print("[DEBUG] Dialog accepted")
                else:
                    print("[DEBUG] Dialog cancelled")
                    
            except ImportError as e:
                QMessageBox.critical(
                    self.main_app,
                    "Import Error",
                    f"Unable to import configuration dialog:\n{str(e)}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self.main_app,
                    "Configuration Error",
                    f"Error opening configuration dialog:\n{str(e)}\n\nPlease verify that sensors are properly connected."
                )
                print(f"[ERROR] Exception in refresh_the_connected_system: {e}")
                import traceback
                traceback.print_exc()
        else:
            QMessageBox.information(
                self.main_app, 
                "Refresh Connected System", 
                "No sensors are currently connected.\n\n"
                "Please connect sensors first using the 'Connect' button, then use this function to modify hardware settings and sensor-to-segment mappings."
            )

    def request_h5_file(self):
        from UI.review import Review
        # Get current file or ask user to select one
        f = self.main_app.subject_file
        print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        print(f)
        if not f:
            options = QFileDialog.Options()
            f, _ = QFileDialog.getOpenFileName(
                self.main_app,
                "Open HDF5 File",
                "",
                "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
                options=options
            )
            if not f:  # User cancelled file selection
                return
        
        request_files()

        received_files = [os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)]
        received_files = [f for f in received_files if os.path.isfile(f)]

        if received_files:
            latest_file = max(received_files, key=os.path.getmtime)

            copy_all_data_preserve_root_metadata(latest_file, self.main_app.subject_file)

            self.review = Review(file_path=self.main_app.subject_file)

            for widget in QApplication.topLevelWidgets():
                widget.close()

            self.review.show()
        else:
            print("[WARN] Aucun fichier reçu.")

    def request_h5_file_review(self, file_path, file_dictionary):
        from UI.review import Review
        f = self.main_app.subject_file
        print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        print(f)
        if not f:
            options = QFileDialog.Options()
            f, _ = QFileDialog.getOpenFileName(
                self.main_app,
                "Open HDF5 File",
                "",
                "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
                options=options
            )
            if not f:  # User cancelled file selection
                return
        
        request_files()

        received_files = [os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)]
        received_files = [f for f in received_files if os.path.isfile(f)]

        if received_files:
            latest_file = max(received_files, key=os.path.getmtime)

            copy_all_data_preserve_root_metadata(latest_file, self.main_app.subject_file)
            file_dictionary.append(latest_file)
            self.review = Review(parent=None, file_path=file_path, existing_load=False, trials=file_dictionary)

            for widget in QApplication.topLevelWidgets():
                widget.close()

            self.review.show()
        else:
            print("[WARN] Aucun fichier reçu.")

    def edit_creation_date(self):
        # Edit menu
        menubar = self.main_app.menuBar()

        edit_menu = menubar.addMenu('&Edit')

        # Edit menu actions
        self.clear_plot_action = self._create_action(
            "&Clear plots",
            lambda: self.clear_plot(),
            "Ctrl+P",
            tip="Clear all plots while maintaining settings"
        )

        self.refresh_connected_system_action = self._create_action(
            "&Refresh Connected System",
            lambda: self.refresh_the_connected_system(),
            "Ctrl+R",
            tip="Refresh the connected system and modify sensor mappings"
        )

        self.request_h5_file_action = self._create_action(
            "&Request H5 File",
            lambda: self.request_h5_file(),
            "Ctrl+H",
            tip="Request an H5 file"
        )

        # Add actions to edit menu
        edit_menu.addAction(self.clear_plot_action)
        edit_menu.addAction(self.refresh_connected_system_action)
        edit_menu.addAction(self.request_h5_file_action)

    def edit_Boleen(self, boleen):
        """Active ou désactive les actions du menu Edit (Clear Plot et Request H5 File seulement)."""
        # Seules les actions qui doivent être activées après l'arrêt de l'enregistrement
        actions_to_toggle = [
            ('clear_plot_action', 'clear_plot_action'),  
            ('request_h5_file_action', 'request_h5_file_action')
        ]
        
        for attr_name, action_name in actions_to_toggle:
            if hasattr(self, attr_name):
                action = getattr(self, attr_name)
                if action is not None:
                    action.setEnabled(boleen)
                else:
                    print(f"[WARNING] {action_name} is None")
            else:
                print(f"[WARNING] {attr_name} attribute not found")

    def set_refresh_connected_system_enabled(self, enabled):
        """Active ou désactive spécifiquement l'action Refresh Connected System."""
        if hasattr(self, 'refresh_connected_system_action'):
            action = getattr(self, 'refresh_connected_system_action')
            if action is not None:
                action.setEnabled(enabled)
            else:
                print(f"[WARNING] refresh_connected_system_action is None")
        else:
            print(f"[WARNING] refresh_connected_system_action attribute not found")
    
    def review(self):
        self.Save_current_trial.setEnabled(True)
        self.Save_current_trial_as.setEnabled(True)
        self.show_metadata_action.setEnabled(True)



    def review_start_recording(self, parent, file_dictionary):
        if not parent.file_path:
            print("⚠️ Aucun fichier source (parent.file_path) défini.")
            return
        if file_dictionary is None:
            file_dictionary = []

        # Obtenir dossier et nom de base sans extension
        base_dir = os.path.dirname(parent.file_path)
        base_name = os.path.splitext(os.path.basename(parent.file_path))[0]

        # Déterminer le numéro de trial
        trial_number = len(file_dictionary) + 1

        # Rechercher si _trial_{nombre} est déjà présent
        match = re.match(r"^(.*)_trial_\d+$", base_name)
        if match:
            base_name_clean = match.group(1)
        else:
            base_name_clean = base_name

        new_file_name = f"{base_name_clean}_trial_{trial_number}.h5"
        new_file_path = os.path.join(base_dir, new_file_name)

        try:
            # Lire les métadonnées du fichier source
            with h5py.File(parent.file_path, 'r') as source_file:
                attrs = dict(source_file.attrs)

            # Créer un nouveau fichier avec uniquement les mêmes métadonnées
            with h5py.File(new_file_path, 'w') as new_file:
                for key, value in attrs.items():
                    new_file.attrs[key] = value

            print(f"✅ Fichier créé avec les métadonnées : {new_file_path}")

        except Exception as e:
            print(f"❌ Erreur lors de la création du fichier : {e}")

        from plots.dashboard_app import DashboardApp
        parent.dashboard_instance = DashboardApp(new_file_path, parent, file_dictionary)
        parent.dashboard_instance.showMaximized()

