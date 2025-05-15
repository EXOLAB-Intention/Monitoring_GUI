import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QSplitter, QGridLayout, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush
from plots.model_3d_viewer import Model3DWidget
import re

class MappingBadgesWidget(QWidget):
    def __init__(self, mappings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        for part in sorted(set(mappings.values())):
            h = QHBoxLayout()
            part_label = QLabel(f"<b>{part.capitalize()}</b>")
            h.addWidget(part_label)
            for typ in ["IMU", "EMG", "pMMG"]:
                for sid, bpart in mappings.items():
                    if bpart == part and str(sid).startswith(typ[0]):
                        badge = QLabel(f"{typ}{sid}")
                        badge.setStyleSheet(f"background: {self._color(typ)}; color: white; border-radius: 8px; padding: 2px 8px; margin: 2px;")
                        h.addWidget(badge)
            layout.addLayout(h)
        layout.addStretch(1)

    def _color(self, typ):
        return {"IMU": "#2196F3", "EMG": "#4CAF50", "pMMG": "#FF9800"}.get(typ, "#888")

class SensorMappingDialog(QDialog):
    mappings_updated = pyqtSignal(dict, dict, dict)  # EMG, IMU, PMMG mappings

    def __init__(self, parent=None, current_mappings=None):
        super().__init__(parent)
        self.setWindowTitle("Sensor Mapping Configuration")
        # Largeur et hauteur ajustées pour être un peu moins large mais toujours confortable
        self.resize(1350, 850)
        self.setMinimumSize(1200, 800)
        
        # Store current mappings
        self.current_mappings = current_mappings or {
            'EMG': {},
            'IMU': {
                1: 'torso',
                2: 'left_elbow',
                3: 'right_elbow',
                4: 'left_knee',
                5: 'right_knee',
                6: 'head'
            },
            'pMMG': {}
        }
        
        # Track selected body part
        self.selected_body_part = None
        
        # Setup UI
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Tab widget for different sensor types
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.general_tab = self.create_general_tab()
        self.emg_tab = self.create_sensor_specific_tab("EMG", 8)
        self.imu_tab = self.create_sensor_specific_tab("IMU", 6)
        self.pmmg_tab = self.create_sensor_specific_tab("pMMG", 8)
        
        # Add tabs
        self.tab_widget.addTab(self.general_tab, "General")
        self.tab_widget.addTab(self.emg_tab, "EMG Configuration")
        self.tab_widget.addTab(self.imu_tab, "IMU Configuration")
        self.tab_widget.addTab(self.pmmg_tab, "pMMG Configuration")
        
        main_layout.addWidget(self.tab_widget)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Configuration")
        self.save_button.clicked.connect(self.save_mappings)
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def create_general_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # 1. Modèle 3D centré en haut
        self.general_model = Model3DWidget()
        main_layout.addWidget(self.general_model, stretch=2)

        # 2. Contrôles d’assignation dans un QGroupBox
        controls_group = QGroupBox("Assign a Sensor to a Body Part")
        controls_layout = QGridLayout()
        controls_group.setLayout(controls_layout)

        # Sélection de la partie du corps
        controls_layout.addWidget(QLabel("Body part:"), 0, 0)
        self.body_part_selector = QComboBox()
        available_parts = self.general_model.get_available_body_parts()
        readable_parts = [self._convert_model_part_to_ui(part) for part in available_parts]
        part_mapping = dict(zip(readable_parts, available_parts))
        self.body_part_selector.addItems(readable_parts)
        self.body_part_selector.currentTextChanged.connect(
            lambda text: self.select_body_part(part_mapping.get(text))
        )
        controls_layout.addWidget(self.body_part_selector, 0, 1)

        # Type de capteur
        controls_layout.addWidget(QLabel("Sensor type:"), 1, 0)
        self.sensor_type_combo = QComboBox()
        self.sensor_type_combo.addItems(["EMG", "IMU", "pMMG"])
        self.sensor_type_combo.currentTextChanged.connect(self.update_available_sensors)
        controls_layout.addWidget(self.sensor_type_combo, 1, 1)

        # Sélection du capteur
        controls_layout.addWidget(QLabel("Sensor:"), 2, 0)
        self.sensor_combo = QComboBox()
        self.update_available_sensors(self.sensor_type_combo.currentText())
        controls_layout.addWidget(self.sensor_combo, 2, 1)

        # Bouton d’assignation
        self.assign_button = QPushButton("Assign Sensor")
        self.assign_button.clicked.connect(self.assign_sensor)
        self.assign_button.setEnabled(False)
        controls_layout.addWidget(self.assign_button, 3, 0, 1, 2)

        # Partie sélectionnée
        self.selected_part_label = QLabel("No body part selected")
        self.selected_part_label.setStyleSheet("font-weight: bold;")
        controls_layout.addWidget(self.selected_part_label, 4, 0, 1, 2)

        main_layout.addWidget(controls_group, stretch=0)

        # 3. Badges des mappings en bas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        badges = MappingBadgesWidget(self.current_mappings["IMU"], self)
        scroll.setWidget(badges)
        main_layout.addWidget(scroll, stretch=1)

        return tab
        
    def create_sensor_specific_tab(self, sensor_type, num_sensors):
        tab = QWidget()
        layout = QHBoxLayout()
        
        # Left side - 3D Model
        model_widget = Model3DWidget()
        
        # Right side - Sensor specific controls
        control_widget = QWidget()
        control_layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(f"Assign {sensor_type} sensors to body parts")
        instructions.setWordWrap(True)
        control_layout.addWidget(instructions)
        
        # Selected part info (same as general tab)
        part_label = QLabel("No body part selected")
        part_label.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(part_label)
        
        # Body part selector (workaround)
        body_part_label = QLabel("Select body part:")
        control_layout.addWidget(body_part_label)
        
        body_part_combo = QComboBox()
        available_parts = model_widget.get_available_body_parts()
        readable_parts = [self._convert_model_part_to_ui(part) for part in available_parts]
        part_mapping = dict(zip(readable_parts, available_parts))
        body_part_combo.addItems(readable_parts)
        control_layout.addWidget(body_part_combo)
        
        # Sensor selection
        sensor_label = QLabel(f"Select {sensor_type} sensor:")
        control_layout.addWidget(sensor_label)
        
        sensor_combo = QComboBox()
        for i in range(1, num_sensors + 1):
            sensor_combo.addItem(f"{sensor_type}{i}")
        control_layout.addWidget(sensor_combo)
        
        # Assign button
        assign_button = QPushButton(f"Assign {sensor_type} Sensor")
        control_layout.addWidget(assign_button)
        
        # Current mappings table for this sensor type
        mappings_group = QGroupBox(f"Current {sensor_type} Mappings")
        mappings_layout = QVBoxLayout()
        mappings_table = QTableWidget(0, 2)  # Sensor ID, Body Part
        mappings_table.setHorizontalHeaderLabels(["Sensor", "Body Part"])
        mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        mappings_table.setMinimumHeight(200)  # Ajouter cette ligne
        mappings_layout.addWidget(mappings_table)
        mappings_group.setLayout(mappings_layout)
        control_layout.addWidget(mappings_group)
        
        # Store references to widgets for each tab
        setattr(self, f"{sensor_type.lower()}_model", model_widget)
        setattr(self, f"{sensor_type.lower()}_part_label", part_label)
        setattr(self, f"{sensor_type.lower()}_part_combo", body_part_combo)
        setattr(self, f"{sensor_type.lower()}_sensor_combo", sensor_combo)
        setattr(self, f"{sensor_type.lower()}_assign_button", assign_button)
        setattr(self, f"{sensor_type.lower()}_mappings_table", mappings_table)
        
        # Connect signals
        body_part_combo.currentTextChanged.connect(
            lambda text, st=sensor_type: self.select_specific_body_part(part_mapping.get(text), st)
        )
        assign_button.clicked.connect(
            lambda checked, st=sensor_type: self.assign_specific_sensor(st)
        )
        
        # Update mappings table
        self.update_specific_mappings_table(sensor_type)
        
        control_widget.setLayout(control_layout)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(model_widget)
        splitter.addWidget(control_widget)
        splitter.setSizes([650, 550])  # Augmenté de [500, 400]
        
        layout.addWidget(splitter)
        tab.setLayout(layout)
        
        return tab
        
    def select_body_part(self, part_name):
        self.selected_body_part = part_name
        self.selected_part_label.setText(f"Selected: {self._convert_model_part_to_ui(part_name)}")
        self.assign_button.setEnabled(part_name is not None)
        
    def select_specific_body_part(self, part_name, sensor_type):
        """Handle selection of a body part in a specific sensor tab"""
        part_label = getattr(self, f"{sensor_type.lower()}_part_label")
        part_label.setText(f"Selected: {self._convert_model_part_to_ui(part_name)}")
        
    def update_available_sensors(self, sensor_type=None):
        """Update the available sensors based on the selected sensor type"""
        if sensor_type is None:
            sensor_type = self.sensor_type_combo.currentText()
        self.sensor_combo.clear()
        if sensor_type == "EMG":
            for i in range(1, 9):  # EMG1-EMG8
                self.sensor_combo.addItem(f"EMG{i}")
        elif sensor_type == "IMU":
            for i in range(1, 7):  # IMU1-IMU6
                self.sensor_combo.addItem(f"IMU{i}")
        elif sensor_type == "pMMG":
            for i in range(1, 9):  # pMMG1-pMMG8
                self.sensor_combo.addItem(f"pMMG{i}")
                
    def assign_sensor(self):
        if not self.selected_body_part:
            QMessageBox.warning(self, "Warning", "Please select a body part first")
            return

        sensor_type = self.sensor_type_combo.currentText()
        sensor_id_text = self.sensor_combo.currentText()
        # Correction extraction du numéro
        match = re.match(rf"{sensor_type}(\d+)", sensor_id_text)
        if not match:
            QMessageBox.warning(self, "Warning", "Invalid sensor selection")
            return
        sensor_id = int(match.group(1))

        # Update the mapping
        self.current_mappings[sensor_type][sensor_id] = self.selected_body_part

        # Update tables
        self.update_general_mappings_table()
        self.update_specific_mappings_table(sensor_type)

        # Update the 3D model visualization
        if sensor_type == "IMU":
            self.general_model.map_imu_to_body_part(sensor_id, self.selected_body_part)
            self.imu_model.map_imu_to_body_part(sensor_id, self.selected_body_part)

        # Update badges in the general tab
        self.update_badges()

        QMessageBox.information(
            self,
            "Sensor Assigned",
            f"{sensor_type}{sensor_id} has been assigned to {self._convert_model_part_to_ui(self.selected_body_part)}"
        )
        
    def assign_specific_sensor(self, sensor_type):
        """Assign a sensor in a specific sensor tab"""
        part_combo = getattr(self, f"{sensor_type.lower()}_part_combo")
        sensor_combo = getattr(self, f"{sensor_type.lower()}_sensor_combo")
        
        part_text = part_combo.currentText()
        sensor_text = sensor_combo.currentText()
        
        # Get the actual body part name and sensor ID
        available_parts = getattr(self, f"{sensor_type.lower()}_model").get_available_body_parts()
        readable_parts = [self._convert_model_part_to_ui(part) for part in available_parts]
        part_mapping = dict(zip(readable_parts, available_parts))
        
        body_part = part_mapping.get(part_text)
        sensor_id = int(sensor_text[len(sensor_type):])
        
        # Update the mapping
        self.current_mappings[sensor_type][sensor_id] = body_part
        
        # Update tables
        self.update_general_mappings_table()
        self.update_specific_mappings_table(sensor_type)
        
        # Update the 3D model visualization
        if sensor_type == "IMU":
            self.general_model.map_imu_to_body_part(sensor_id, body_part)
            self.imu_model.map_imu_to_body_part(sensor_id, body_part)
        
        # Update badges in the general tab
        self.update_badges()

        QMessageBox.information(
            self, 
            "Sensor Assigned", 
            f"{sensor_type}{sensor_id} has been assigned to {part_text}"
        )
        
    def update_general_mappings_table(self):
        """Update the general mappings table with all current mappings"""
        self.general_mappings_table.setRowCount(0)
        
        row = 0
        for sensor_type, mappings in self.current_mappings.items():
            for sensor_id, body_part in mappings.items():
                self.general_mappings_table.insertRow(row)
                self.general_mappings_table.setItem(row, 0, QTableWidgetItem(sensor_type))
                self.general_mappings_table.setItem(row, 1, QTableWidgetItem(str(sensor_id)))
                self.general_mappings_table.setItem(row, 2, 
                                                  QTableWidgetItem(self._convert_model_part_to_ui(body_part)))
                row += 1
                
    def update_specific_mappings_table(self, sensor_type):
        """Update a specific sensor type mappings table"""
        mappings_table = getattr(self, f"{sensor_type.lower()}_mappings_table")
        mappings_table.setRowCount(0)
        
        row = 0
        for sensor_id, body_part in self.current_mappings[sensor_type].items():
            mappings_table.insertRow(row)
            mappings_table.setItem(row, 0, QTableWidgetItem(f"{sensor_type}{sensor_id}"))
            mappings_table.setItem(row, 1, 
                                 QTableWidgetItem(self._convert_model_part_to_ui(body_part)))
            row += 1
            
    def update_badges(self):
        """Mettre à jour les badges dans l'onglet général avec tous les mappings combinés"""
        scroll = self.general_tab.findChild(QScrollArea)
        if scroll:
            old_badges = scroll.widget()
            if old_badges:
                old_badges.deleteLater()
            
            # Créer de nouveaux badges avec tous les mappings combinés
            all_mappings = {}
            for sensor_type, mappings in self.current_mappings.items():
                for sensor_id, body_part in mappings.items():
                    all_mappings[f"{sensor_type}{sensor_id}"] = body_part
                    
            new_badges = MappingBadgesWidget(all_mappings, self)
            scroll.setWidget(new_badges)
            
    def save_mappings(self):
        """Save the mappings and close the dialog"""
        self.mappings_updated.emit(
            self.current_mappings["EMG"],
            self.current_mappings["IMU"],
            self.current_mappings["pMMG"]
        )
        self.accept()
        
    def reset_to_default(self):
        """Reset mappings to default values"""
        default_mappings = {
            'EMG': {},
            'IMU': {
                1: 'torso',
                2: 'left_elbow',
                3: 'right_elbow',
                4: 'left_knee',
                5: 'right_knee',
                6: 'head'
            },
            'pMMG': {}
        }
        
        self.current_mappings = default_mappings
        
        # Update all tables
        self.update_general_mappings_table()
        for sensor_type in ["EMG", "IMU", "pMMG"]:
            self.update_specific_mappings_table(sensor_type)
            
        # Update 3D models
        for imu_id, body_part in default_mappings["IMU"].items():
            self.general_model.map_imu_to_body_part(imu_id, body_part)
            self.imu_model.map_imu_to_body_part(imu_id, body_part)
            
        QMessageBox.information(self, "Reset Mappings", "Mappings have been reset to default values")
        
    def _convert_model_part_to_ui(self, model_part):
        """Convert model part names to user-friendly UI names"""
        if not model_part:
            return "Not assigned"
            
        mapping = {
            'head': 'Head',
            'neck': 'Neck',
            'torso': 'Torso',
            'left_shoulder': 'Left Shoulder',
            'right_shoulder': 'Right Shoulder',
            'left_elbow': 'Left Elbow',
            'right_elbow': 'Right Elbow',
            'left_hand': 'Left Hand',
            'right_hand': 'Right Hand',
            'hip': 'Hip',
            'left_knee': 'Left Knee',
            'right_knee': 'Right Knee',
            'left_foot': 'Left Foot',
            'right_foot': 'Right Foot'
        }
        return mapping.get(model_part, model_part)


if __name__ == '__main__':
    # For testing
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = SensorMappingDialog()
    if dialog.exec_() == QDialog.Accepted:
        print("Dialog accepted")
    sys.exit(0)