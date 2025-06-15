from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QWidget, QMessageBox
from PyQt5.QtCore import pyqtSignal
import h5py


class ExperimenterDialog(QDialog):
    """
    Dialog box to request the experimenter's name.
    """
    experimenter_name_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experimenter Information")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.subject_file = parent.subject_file if parent else None
        self.hasName = False
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        self.title_label = QLabel("Name of the experimenter")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(self.title_label)

        # Instruction
        self.instruction_label = QLabel("Please write your full name.")
        self.instruction_label.setStyleSheet("font-size: 12px;")
        main_layout.addWidget(self.instruction_label)

        # Name input field
        with h5py.File(self.subject_file, 'r+') as f:
            root_attrs = dict(f.attrs)
            if "experimenter_name" in root_attrs:
                d = f.attrs["experimenter_name"]
                self.name_input = QLineEdit()
                self.name_input.setText(d)
                self.hasName = True
            else:
                self.name_input = QLineEdit()
                self.name_input.setPlaceholderText("Full name")
        self.name_input.setStyleSheet("font-size: 14px; padding: 5px;")
        main_layout.addWidget(self.name_input)
        
        # Spacer
        spacer = QWidget()
        spacer.setMinimumHeight(10)
        main_layout.addWidget(spacer)

        # Continue button
        self.continue_button = QPushButton("CONTINUE")
        self.continue_button.setStyleSheet("""
            QPushButton {
                font-size: 14px; 
                padding: 10px; 
                background-color: #5cb85c; 
                color: white; 
                border: none; 
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
            QPushButton:pressed {
                background-color: #398439;
            }
            QPushButton:disabled {
                background-color: #d3d3d3;
                color: #a0a0a0;
            }
        """)
        if self.hasName:
            self.continue_button.setEnabled(True)  # Initially disabled
        else:
            self.continue_button.setEnabled(False)
        main_layout.addWidget(self.continue_button)
        
        # Connect signals
        self.name_input.textChanged.connect(self._check_input)
        self.continue_button.clicked.connect(self._submit_name)

    def _check_input(self):
        """Enable button if input is not empty"""
        self.continue_button.setEnabled(bool(self.name_input.text().strip()))
    
    def _submit_name(self):
        """Submit the experimenter's name and redirect to dashboard"""
        name = self.name_input.text().strip()
        print(f"Experimenter's name submitted: {name}")
        if name:
            # Ouvrir le fichier HDF5 en mode lecture/écriture
            with h5py.File(self.subject_file, 'r+') as f:
                root_attrs = dict(f.attrs)

                # Afficher les métadonnées existantes
                if root_attrs:
                    print(f"Métadonnées à la racine de '{self.subject_file}':")
                    for key, value in root_attrs.items():
                        print(f"  {key}: {value}")

                # Remplacer ou créer l'attribut 'experimenter_name'
                f.attrs["experimenter_name"] = name
                print(f"L'attribut 'experimenter_name' a été mis à jour avec : {name}")
            self.experimenter_name_submitted.emit(name)
            self.accept()
        else:
            QMessageBox.warning(self, "Missing Information", "Please enter your name.")


def createExperimenterDialog(parent=None):
    """Function to create and return an experimenter dialog"""
    return ExperimenterDialog(parent)