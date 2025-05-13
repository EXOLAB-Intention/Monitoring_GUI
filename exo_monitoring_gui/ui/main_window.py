from PyQt5.QtWidgets import (QMainWindow, QPushButton, QLabel, QAction, QFileDialog,
                         QMessageBox, QVBoxLayout, QWidget, QProgressBar, QDialog, QTextEdit, QHBoxLayout)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
import h5py
import os
import sys
from datetime import datetime
import traceback

# Ensure relative imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from UI.informations import InformationWindow
from utils.hdf5_utils import load_metadata, save_metadata


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialization of state variables
        self.current_subject_file = None
        self.current_trial_data = None
        self.modified = False
        self.plot_widgets = []  # To store references to plot widgets
        
        # Main window configuration
        self.setWindowTitle("Data Monitoring Software")
        self.setGeometry(50, 50, 1600, 900)  # More reasonable size
        self._setup_ui()
        self._create_menubar()
        self._apply_styles()
        
        # Timer for auto-save (every 5 minutes)
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(300000)  # 5 minutes in milliseconds
        
    def _setup_ui(self):
        """Configure the main user interface"""
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create welcome screen container
        welcome_container = QWidget()
        welcome_layout = QVBoxLayout(welcome_container)
        welcome_layout.setContentsMargins(50, 50, 50, 50)
        welcome_layout.setSpacing(20)
        
        # Add logo (if you have one)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        try:
            logo_pixmap = QPixmap("resources/logo.png").scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            welcome_layout.addWidget(logo_label)
        except:
            # If logo image doesn't exist, use a placeholder
            logo_label.setText("💻")
            logo_label.setStyleSheet("font-size: 120px; color: #1976D2;")
            logo_label.setAlignment(Qt.AlignCenter)
            welcome_layout.addWidget(logo_label)
        
        # Welcome text with large scientific font
        welcome_text = QLabel("START SCREEN")
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 48px;
            font-weight: bold;
            color: #1976D2;
            letter-spacing: 4px;
            margin-top: 20px;
        """)
        welcome_layout.addWidget(welcome_text)
        
        # Subtitle
        subtitle_text = QLabel("Exoskeleton Monitoring System")
        subtitle_text.setAlignment(Qt.AlignCenter)
        subtitle_text.setStyleSheet("""
            font-family: 'Segoe UI Light', Arial, sans-serif;
            font-size: 24px;
            color: #455A64;
            margin-bottom: 30px;
        """)
        welcome_layout.addWidget(subtitle_text)
        
        # Quick action buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(20)
        
        new_subject_btn = QPushButton("New Subject")
        new_subject_btn.clicked.connect(self.create_new_subject)
        
        load_subject_btn = QPushButton("Load Subject")
        load_subject_btn.clicked.connect(self.load_existing_subject)
        
        quick_help_btn = QPushButton("Quick Help")
        quick_help_btn.clicked.connect(self.show_about_dialog)
        
        button_layout.addStretch()
        button_layout.addWidget(new_subject_btn)
        button_layout.addWidget(load_subject_btn)
        button_layout.addWidget(quick_help_btn)
        button_layout.addStretch()
        
        welcome_layout.addWidget(button_container)
        welcome_layout.addStretch()
        
        # Add version and copyright
        version_label = QLabel("DATA Monitoring Software v2.5.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            color: #78909C;
        """)
        welcome_layout.addWidget(version_label)
        
        copyright_label = QLabel("© 2025 Advanced Exoskeleton Research Laboratory")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10px;
            color: #B0BEC5;
        """)
        welcome_layout.addWidget(copyright_label)
        
        # Add welcome container to main layout
        main_layout.addWidget(welcome_container)
        
        # Status bar to display information
        self.statusBar().showMessage("Ready")
        
        # Progress bar for long operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        
    def _create_menubar(self):
        """Create the application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        # File menu actions
        create_subject_action = self._create_action("&Create new subject", self.create_new_subject, "Ctrl+N", 
                                                  tip="Create a new subject file")
        load_subject_action = self._create_action("&Load existing subject", self.load_existing_subject, "Ctrl+O",
                                                tip="Load an existing subject file")
        self.save_subject_action = self._create_action("&Save subject", self.save_subject, "Ctrl+S",
                                                    tip="Save the current subject")
        self.save_subject_as_action = self._create_action("Save subject &as...", self.save_subject_as, "Ctrl+Shift+S",
                                                        tip="Save the subject with a new name")
        self.show_metadata_action = self._create_action("&Show metadata", self.show_metadata, "Ctrl+M",
                                                     tip="Display subject metadata")
        exit_action = self._create_action("E&xit", self.close, "Alt+F4",
                                        tip="Exit the application")
        
        # Add actions to file menu
        file_menu.addAction(create_subject_action)
        file_menu.addAction(load_subject_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_subject_action)
        file_menu.addAction(self.save_subject_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.show_metadata_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        # Help menu actions
        about_action = self._create_action("&About", self.show_about_dialog,
                                         tip="About the application")
        
        # Add actions to help menu
        help_menu.addAction(about_action)
        
        # Initially disable actions that require an open file
        self.save_subject_action.setEnabled(False)
        self.save_subject_as_action.setEnabled(False)
        self.show_metadata_action.setEnabled(False)
    
    def _create_action(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False):
        """Create a QAction with the given properties"""
        action = QAction(text, self)
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
    
    def _apply_styles(self):
        """Apply CSS styles to the application"""
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #f0f0f0;
            }
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #dddddd;
            }
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #dceaff;
                color: black;
            }
            QMenu::separator {
                height: 1px;
                background: #dddddd;
                margin: 5px 15px;
            }
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #dddddd;
                border-radius: 3px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3399ff;
                width: 10px;
            }
        """)

    def create_new_subject(self):
        """Creates a new subject file and opens information window"""
        if self.modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                        'There are unsaved changes. Save before creating new subject?',
                                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self.save_subject()
            elif reply == QMessageBox.Cancel:
                return
        
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self,
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

                self.current_subject_file = filename
                self.modified = False
                self.save_subject_action.setEnabled(True)
                self.save_subject_as_action.setEnabled(True)
                self.show_metadata_action.setEnabled(True)
                
                self.statusBar().showMessage(f"New subject file created: {os.path.basename(filename)}")
                
                # Display information window to collect metadata
                # Correction de la variable
                self.info_window = InformationWindow(self, self.current_subject_file)
                self.info_window.info_submitted.connect(self.update_subject_metadata)


                def closeEvent(event):
                    self.save_subject_action.setEnabled(False)
                    self.save_subject_as_action.setEnabled(False)
                    self.show_metadata_action.setEnabled(False)
                    event.accept()

                self.info_window.closeEvent = closeEvent                          
                self.info_window.show()
                
            except Exception as e:
                self._show_error(f"Error creating subject file: {str(e)}")
    
    def load_existing_subject(self):
        """Load an existing subject file"""
        if self.modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                        'There are unsaved changes. Save before loading a new subject?',
                                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self.save_subject()
            elif reply == QMessageBox.Cancel:
                return

        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Subject File",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            try:
                # Verify it's a valid subject file
                with h5py.File(filename, 'r') as f:
                    if 'subject_created' in f.attrs:
                        # Load metadata
                        data, image_path = load_metadata(filename)
                        
                        # Update the current file and UI
                        self.current_subject_file = filename
                        self.modified = False
                        self.save_subject_action.setEnabled(True)
                        self.save_subject_as_action.setEnabled(True)
                        self.show_metadata_action.setEnabled(True)
                        
                        # Update the status bar
                        self.statusBar().showMessage(f"Loaded subject file: {os.path.basename(filename)}")
                        
                        # If the file contains trial data, load it
                        if 'trials' in f:
                            # Logic to load and display trials would go here
                            pass
                        
                        # Display information window with loaded data
                        self.info_window = InformationWindow(self, self.current_subject_file)
                        self.info_window.info_submitted.connect(self.update_subject_metadata)
                        self.info_window.show()


                            
                    else:
                        self._show_error("Not a valid subject file. Missing required attributes.")
                        return
                        
            except Exception as e:
                self._show_error(f"Error loading subject file: {str(e)}")
                return
    
    def save_subject(self):
        """Save the current subject file"""
        if not self.current_subject_file:
            return self.save_subject_as()
        else:
            self.info_window._collect_data()
        try:
            # Logic to save data to current file
            # This is a placeholder - your actual save logic might be more complex
            self.modified = False
            self.statusBar().showMessage(f"Saved to {os.path.basename(self.current_subject_file)}")
            return True
        except Exception as e:
            self._show_error(f"Error saving subject: {str(e)}")
            return False

    def save_subject_as(self):
        """Save the subject file with a new name"""
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Subject As",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            if not filename.endswith(".h5") and not filename.endswith(".hdf5"):
                filename += ".h5"
                
            self.current_subject_file = filename
            return self.save_subject()
        return False

    def show_metadata(self):
        """Display metadata of the current subject"""
        if not self.current_subject_file:
            QMessageBox.information(self, "No Subject", "Please open or create a subject first.")
            return
        
        try:
            # Load metadata from the current file
            data, image_path = load_metadata(self.current_subject_file)
            
            if not data:
                QMessageBox.information(self, "No Metadata", "No metadata available for this subject.")
                return
                
            # Create a formatted text to display metadata
            metadata_text = "<h2>Subject Metadata</h2>"
            metadata_text += "<table style='border-collapse: collapse; width: 100%;'>"
            
            # Personal information section
            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Personal Information</th></tr>"
            
            # Add personal info fields if they exist
            for field in ["Name", "Last Name", "Age", "Weight", "Size"]:
                if field in data:
                    metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>{field}</b></td>"
                    metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data[field]}</td></tr>"
            
            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Anthropometric Measurements</th></tr>"
            
            for field in ["Thigh length (cm)", "Shank length (cm)", "Upperarm length (cm)", "Forearm length (cm)"]:
                if field in data:
                    metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>{field}</b></td>"
                    metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data[field]}</td></tr>"
            
            metadata_text += "<tr><th colspan='2' style='background-color: #f0f0f0; padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Collection Information</th></tr>"

            if "collection_date" in data:
                metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>Collection Date</b></td>"
                metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data['collection_date']}</td></tr>"
            
            # Add experimenter name if it exists
            if "experimenter_name" in data:
                metadata_text += f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><b>Experimenter</b></td>"
                metadata_text += f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{data['experimenter_name']}</td></tr>"
            
            metadata_text += "</table>"
            
            # Description if it exists
            if "Description" in data and data["Description"]:
                metadata_text += f"<h3>Description</h3><p>{data['Description']}</p>"
            
            # Display image if it exists
            if image_path and os.path.exists(image_path):
                # Create a dialog to display the metadata
                dialog = QDialog(self)
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
            self._show_error(f"Error displaying metadata: {str(e)}")

    def show_about_dialog(self):
        """Show information about the software"""
        about_text = """
        <h1>Data Monitoring Software</h1>
        <p>Version 2.5.0</p>
        <p>An advanced monitoring tool for exoskeleton data.</p>
        <p>© 2025 Advanced Exoskeleton Research Laboratory</p>
        <p>For help and documentation, please visit our website or contact support.</p>
        """
        
        QMessageBox.about(self, "About Data Monitoring Software", about_text)
    
    def _show_error(self, message):
        """Display an error message"""
        QMessageBox.critical(self, "Error", message)
        print(f"ERROR: {message}")
    
    def _autosave(self):
        """Automatically save current work if modified"""
        if self.modified and self.current_subject_file:
            try:
                # Perform actual save operation
                self.save_subject()
                
                # Update status bar with autosave info
                self.statusBar().showMessage(f"Auto-saved to {os.path.basename(self.current_subject_file)}", 3000)
                
                print(f"Auto-saved at {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"Error during auto-save: {str(e)}")
    
    def update_subject_metadata(self, metadata):
        """Update the subject metadata based on information provided"""
        if not self.current_subject_file:
            print("Error: No subject file is currently open")
            return
        
        try:
            # Save metadata to the current file
            save_metadata(self.current_subject_file, metadata)
            
            # Update UI components if needed
            self.modified = True
            
            # Update status bar
            self.statusBar().showMessage(f"Subject metadata updated for: {os.path.basename(self.current_subject_file)}")
            
            # Additional processing if needed
            if 'Name' in metadata and 'Last Name' in metadata:
                subject_name = f"{metadata['Name']} {metadata['Last Name']}"
                print(f"Subject information updated for: {subject_name}")
            
            # The subject has been created, so we can enable relevant actions
            self.save_subject_action.setEnabled(True)
            self.save_subject_as_action.setEnabled(True)
            self.show_metadata_action.setEnabled(True)
        
        except Exception as e:
            self._show_error(f"Error updating subject metadata: {str(e)}")