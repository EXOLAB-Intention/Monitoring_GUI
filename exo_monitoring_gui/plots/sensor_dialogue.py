import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QSplitter, QGridLayout, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont
from plots.model_3d_viewer import Model3DWidget
import re

class MappingBadgesWidget(QWidget):
    def __init__(self, mappings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Définir l'ordre anatomique des parties du corps (de la tête aux pieds)
        anatomical_order = [
            # Tête et cou
            'head', 'neck',
            # Torse
            'torso',
            # Bras gauche
            'deltoid_l', 'biceps_l', 'forearm_l', 'dorsalis_major_l', 'pectorals_l', 'left_hand',
            # Bras droit
            'deltoid_r', 'biceps_r', 'forearm_r', 'dorsalis_major_r', 'pectorals_r', 'right_hand',
            # Bassin
            'hip',
            # Jambe gauche
            'glutes_l', 'quadriceps_l', 'ishcio_hamstrings_l', 'calves_l', 'left_foot',
            # Jambe droite
            'glutes_r', 'quadriceps_r', 'ishcio_hamstrings_r', 'calves_r', 'right_foot'
        ]
        
        # Fonction pour convertir le nom du modèle en nom UI plus lisible
        def get_display_name(part):
            part_names = {
                'head': 'Head', 
                'neck': 'Neck',
                'torso': 'Torso',
                'deltoid_l': 'Left Deltoid',
                'biceps_l': 'Left Biceps',
                'forearm_l': 'Left Forearm',
                'dorsalis_major_l': 'Left Latissimus Dorsi',
                'pectorals_l': 'Left Pectorals',
                'left_hand': 'Left Hand',
                'deltoid_r': 'Right Deltoid',
                'biceps_r': 'Right Biceps',
                'forearm_r': 'Right Forearm',
                'dorsalis_major_r': 'Right Latissimus Dorsi',
                'pectorals_r': 'Right Pectorals',
                'right_hand': 'Right Hand',
                'hip': 'Hip',
                'glutes_l': 'Left Gluteus',
                'quadriceps_l': 'Left Quadriceps',
                'ishcio_hamstrings_l': 'Left Hamstrings',
                'calves_l': 'Left Calf',
                'left_foot': 'Left Foot',
                'glutes_r': 'Right Gluteus',
                'quadriceps_r': 'Right Quadriceps',
                'ishcio_hamstrings_r': 'Right Hamstrings',
                'calves_r': 'Right Calf',
                'right_foot': 'Right Foot'
            }
            return part_names.get(part, part.capitalize())
        
        # Créer un dictionnaire regroupant les capteurs par partie du corps
        body_part_sensors = {}
        for sid, part in mappings.items():
            if part not in body_part_sensors:
                body_part_sensors[part] = []
            body_part_sensors[part].append(sid)
        
        # Ajouter les parties dans l'ordre anatomique
        for part in anatomical_order:
            if part in body_part_sensors:
                h = QHBoxLayout()
                part_label = QLabel(f"<b>{get_display_name(part)}</b>")
                h.addWidget(part_label)
                
                # Ajouter les capteurs pour cette partie
                for sid in sorted(body_part_sensors[part]):
                    typ = None
                    if str(sid).startswith("I"):
                        typ = "IMU"
                    elif str(sid).startswith("E"):
                        typ = "EMG"
                    elif str(sid).startswith("p"):
                        typ = "pMMG"
                    
                    if typ:
                        badge = QLabel(f"{sid}")
                        badge.setStyleSheet(f"background: {self._color(typ)}; color: white; border-radius: 8px; padding: 2px 8px; margin: 2px;")
                        h.addWidget(badge)
                
                layout.addLayout(h)
        
        # Ajouter les parties qui ne sont pas dans notre ordre prédéfini (au cas où)
        for part in body_part_sensors:
            if part not in anatomical_order:
                h = QHBoxLayout()
                part_label = QLabel(f"<b>{get_display_name(part)}</b>")
                h.addWidget(part_label)
                
                for sid in sorted(body_part_sensors[part]):
                    typ = None
                    if str(sid).startswith("I"):
                        typ = "IMU"
                    elif str(sid).startswith("E"):
                        typ = "EMG"
                    elif str(sid).startswith("p"):
                        typ = "pMMG"
                    
                    if typ:
                        badge = QLabel(f"{sid}")
                        badge.setStyleSheet(f"background: {self._color(typ)}; color: white; border-radius: 8px; padding: 2px 8px; margin: 2px;")
                        h.addWidget(badge)
                
                layout.addLayout(h)
        
        layout.addStretch(1)

    def _color(self, typ):
        return {
            "IMU": "#00CC33",   # Vert comme dans model_3d_viewer.py
            "EMG": "#CC3300",   # Rouge comme dans model_3d_viewer.py
            "pMMG": "#0033CC"   # Bleu comme dans model_3d_viewer.py
        }.get(typ, "#888")

class SimplifiedMappingDialog(QDialog):
    """Interface simplifiée avec onglets pour le mapping des capteurs"""
    mappings_updated = pyqtSignal(dict, dict, dict)  # EMG, IMU, pMMG mappings
    
    def __init__(self, parent=None, current_mappings=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration des capteurs sur le modèle 3D")
        # Augmenter significativement la taille de la fenêtre
        self.resize(1200, 900)  # Augmenté de 1000x700 à 1200x900
        self.setMinimumSize(1100, 800)  # Augmenté de 900x650 à 1100x800
        
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
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("Sensor Mapping Configuration")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.general_tab = self.create_general_tab()
        self.emg_tab = self.create_specific_tab("EMG", 8)
        self.imu_tab = self.create_specific_tab("IMU", 6)
        self.pmmg_tab = self.create_specific_tab("pMMG", 8)
        
        # Add tabs
        self.tab_widget.addTab(self.general_tab, "General View")
        self.tab_widget.addTab(self.emg_tab, "EMG")
        self.tab_widget.addTab(self.imu_tab, "IMU")
        self.tab_widget.addTab(self.pmmg_tab, "pMMG")
        
        main_layout.addWidget(self.tab_widget)

        # Summary of mappings with badges
        badges_group = QGroupBox("Assignment Summary")
        badges_layout = QVBoxLayout()
        self.scroll_badges = QScrollArea()
        self.scroll_badges.setWidgetResizable(True)
        self.scroll_badges.setMinimumHeight(150)  # Add this line to ensure minimum height
        all_mappings = {}
        for sensor_type, mappings in self.current_mappings.items():
            for sensor_id, body_part in mappings.items():
                all_mappings[f"{sensor_type}{sensor_id}"] = body_part
        self.badges_widget = MappingBadgesWidget(all_mappings, self)
        self.scroll_badges.setWidget(self.badges_widget)
        badges_layout.addWidget(self.scroll_badges)
        badges_group.setLayout(badges_layout)
        main_layout.addWidget(badges_group, 1)  # Add stretch factor 1 to give more space

        # Control buttons
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Reset to Default Values")
        self.reset_button.setStyleSheet("padding: 8px 16px;")
        self.reset_button.clicked.connect(self.reset_to_default)
        
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setStyleSheet("padding: 8px 16px; font-weight: bold; background-color: #4CAF50; color: white;")
        self.confirm_button.clicked.connect(self.confirm_mapping)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("padding: 8px 16px;")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # Initialize combos with current mappings
        self.load_current_mappings()

    def create_general_tab(self):
        """Create general tab with 3D model and manual assignment"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 3D Model
        model_group = QGroupBox("3D Model")
        model_layout = QVBoxLayout()
        self.general_model = Model3DWidget()
        model_layout.addWidget(self.general_model)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group, 3)
        
        # Manual assignment
        assign_group = QGroupBox("Assign a Sensor")
        assign_layout = QGridLayout()
        
        # Body part selection
        assign_layout.addWidget(QLabel("Body part:"), 0, 0)
        self.body_part_combo = QComboBox()
        
        # Upper body parts
        upper_body = [
            "Head", "Neck", "Torso",
            "Left Deltoid", "Left Biceps", "Left Forearm", "Left Latissimus Dorsi", "Left Pectorals", "Left Hand",
            "Right Deltoid", "Right Biceps", "Right Forearm", "Right Latissimus Dorsi", "Right Pectorals", "Right Hand"
        ]
        # Lower body parts
        lower_body = [
            "Hip", 
            "Left Quadriceps", "Left Hamstrings", "Left Calves", "Left Gluteus", "Left Foot",
            "Right Quadriceps", "Right Hamstrings", "Right Calves", "Right Gluteus", "Right Foot"
        ]
        
        # Add all body parts
        body_parts = upper_body + lower_body
        self.body_part_combo.addItems(body_parts)
        assign_layout.addWidget(self.body_part_combo, 0, 1)
        
        # Sensor type
        assign_layout.addWidget(QLabel("Sensor type:"), 1, 0)  # Changed from French
        self.sensor_type_combo = QComboBox()
        self.sensor_type_combo.addItems(["EMG", "IMU", "pMMG"])
        self.sensor_type_combo.currentTextChanged.connect(self.update_sensor_list)
        assign_layout.addWidget(self.sensor_type_combo, 1, 1)
        
        # Sensor number
        assign_layout.addWidget(QLabel("Sensor:"), 2, 0)  # Changed from French
        self.sensor_id_combo = QComboBox()
        assign_layout.addWidget(self.sensor_id_combo, 2, 1)
        self.update_sensor_list("IMU")
        
        # Assignment button
        self.manual_assign_button = QPushButton("Assign this Sensor")  # Changed from French
        self.manual_assign_button.clicked.connect(self.manual_assign)
        self.manual_assign_button.setStyleSheet("font-weight: bold;")
        assign_layout.addWidget(self.manual_assign_button, 3, 0, 1, 2)
        
        assign_group.setLayout(assign_layout)
        layout.addWidget(assign_group, 1)
        
        tab.setLayout(layout)
        return tab

    def create_specific_tab(self, sensor_type, num_sensors):
        """Create a specific tab for each sensor type"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"{sensor_type} Sensor Configuration")  # Changed from French
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Split view: 3D model on left, controls on right
        splitter = QSplitter(Qt.Horizontal)
        
        # 3D Model
        model_widget = Model3DWidget()
        splitter.addWidget(model_widget)
        
        # Store model reference
        setattr(self, f"{sensor_type.lower()}_model", model_widget)
        
        # Assignment controls
        control_widget = QWidget()
        control_layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(f"Assign {sensor_type} sensors to different body parts")  # Changed from French
        instructions.setWordWrap(True)
        control_layout.addWidget(instructions)
        
        # Create controls for each sensor
        control_grid = QGridLayout()
        
        # ComboBox storage
        self.sensor_combos = getattr(self, "sensor_combos", {})
        self.sensor_combos[sensor_type] = {}
        
        # Upper body parts
        upper_body = [
            "Head", "Neck", "Torso",
            "Left Deltoid", "Left Biceps", "Left Forearm", "Left Latissimus Dorsi", "Left Pectorals", "Left Hand",
            "Right Deltoid", "Right Biceps", "Right Forearm", "Right Latissimus Dorsi", "Right Pectorals", "Right Hand"
        ]
        # Lower body parts
        lower_body = [
            "Hip", 
            "Left Quadriceps", "Left Hamstrings", "Left Calves", "Left Gluteus", "Left Foot",
            "Right Quadriceps", "Right Hamstrings", "Right Calves", "Right Gluteus", "Right Foot"
        ]
        
        body_parts = ["-- Not assigned --"] + upper_body + lower_body
        
        for i in range(1, num_sensors + 1):
            label = QLabel(f"{sensor_type} {i}")
            label.setStyleSheet(f"color: {self._get_color_for_type(sensor_type)};")
            
            combo = QComboBox()
            combo.addItems(body_parts)
            combo.currentTextChanged.connect(lambda text, s=sensor_type, id=i: self.on_combo_changed(s, id, text))
            
            control_grid.addWidget(label, i-1, 0)
            control_grid.addWidget(combo, i-1, 1)
            
            self.sensor_combos[sensor_type][i] = combo
        
        control_layout.addLayout(control_grid)
        control_layout.addStretch()
        
        # Reset button for this sensor type
        reset_button = QPushButton(f"Reset {sensor_type}")  # Changed from French
        reset_button.clicked.connect(lambda: self.reset_sensor_type(sensor_type))
        control_layout.addWidget(reset_button)
        
        control_widget.setLayout(control_layout)
        splitter.addWidget(control_widget)
        
        # Set initial sizes
        splitter.setSizes([int(splitter.width() * 0.6), int(splitter.width() * 0.4)])
        
        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def update_sensor_list(self, sensor_type):
        """Mettre à jour la liste des capteurs disponibles en fonction du type sélectionné"""
        self.sensor_id_combo.clear()
        num_sensors = 8 if sensor_type in ["EMG", "pMMG"] else 6  # IMU a 6 capteurs, les autres 8
        for i in range(1, num_sensors + 1):
            self.sensor_id_combo.addItem(f"{i}")

    def manual_assign(self):
        """Manually assign a sensor from the general tab"""
        body_part_ui = self.body_part_combo.currentText()
        sensor_type = self.sensor_type_combo.currentText()
        sensor_id = int(self.sensor_id_combo.currentText())
        
        body_part = self._convert_ui_to_model_part(body_part_ui)
        
        # Update mapping
        self.current_mappings[sensor_type][sensor_id] = body_part
        
        # Update combos in specific tab
        if sensor_type in self.sensor_combos and sensor_id in self.sensor_combos[sensor_type]:
            combo = self.sensor_combos[sensor_type][sensor_id]
            index = combo.findText(body_part_ui)
            if index >= 0:
                combo.setCurrentIndex(index)
        
        # Update 3D model
        if sensor_type == "IMU":
            self.general_model.map_imu_to_body_part(sensor_id, body_part)
            self.imu_model.map_imu_to_body_part(sensor_id, body_part)
        
        # Update badges
        self.update_badges()
        
        # Confirmation message
        QMessageBox.information(
            self, 
            "Sensor Assigned", 
            f"{sensor_type} {sensor_id} has been assigned to {body_part_ui}"
        )

    def _get_color_for_type(self, typ):
        return {"IMU": "#00CC33", "EMG": "#CC3300", "pMMG": "#0033CC"}.get(typ, "#888")

    def load_current_mappings(self):
        """Charge les mappings actuels dans les combos"""
        for sensor_type, mappings in self.current_mappings.items():
            if sensor_type not in self.sensor_combos:
                continue
                
            for sensor_id, body_part in mappings.items():
                if sensor_id in self.sensor_combos[sensor_type]:
                    combo = self.sensor_combos[sensor_type][sensor_id]
                    body_part_ui = self._convert_model_part_to_ui(body_part)
                    index = combo.findText(body_part_ui)
                    if index >= 0:
                        combo.setCurrentIndex(index)
        
        # Mettre à jour tous les modèles 3D
        for sensor_id, body_part in self.current_mappings["IMU"].items():
            self.general_model.map_imu_to_body_part(sensor_id, body_part)
            self.imu_model.map_imu_to_body_part(sensor_id, body_part)

    def on_combo_changed(self, sensor_type, sensor_id, body_part_ui):
        """Called when a combo is changed in a specific tab"""
        if body_part_ui == "-- Not assigned --":
            if sensor_id in self.current_mappings[sensor_type]:
                del self.current_mappings[sensor_type][sensor_id]
        else:
            body_part = self._convert_ui_to_model_part(body_part_ui)
            self.current_mappings[sensor_type][sensor_id] = body_part
            
            # Update 3D model for IMU
            if sensor_type == "IMU":
                self.general_model.map_imu_to_body_part(sensor_id, body_part)
                self.imu_model.map_imu_to_body_part(sensor_id, body_part)
        
        # Update badges
        self.update_badges()

    def update_badges(self):
        """Mettre à jour l'affichage des badges"""
        old_badges = self.scroll_badges.widget()
        if old_badges:
            old_badges.deleteLater()
        
        all_mappings = {}
        for sensor_type, mappings in self.current_mappings.items():
            for sensor_id, body_part in mappings.items():
                all_mappings[f"{sensor_type}{sensor_id}"] = body_part
                
        new_badges = MappingBadgesWidget(all_mappings, self)
        self.scroll_badges.setWidget(new_badges)

    def reset_sensor_type(self, sensor_type):
        """Reset a specific sensor type"""
        default_values = {}
        if sensor_type == "IMU":
            default_values = {
                1: 'torso',
                2: 'forearm_l',
                3: 'forearm_r',
                4: 'calves_l',
                5: 'calves_r',
                6: 'head'
            }
        elif sensor_type == "EMG":
            default_values = {
                1: 'biceps_l',
                2: 'biceps_r',
                3: 'quadriceps_l', 
                4: 'quadriceps_r'
            }
        elif sensor_type == "pMMG":
            default_values = {
                1: 'deltoid_l',
                2: 'deltoid_r'
            }
        
        # Update mapping
        self.current_mappings[sensor_type] = default_values.copy()
        
        # Update combos
        if sensor_type in self.sensor_combos:
            for sensor_id, combo in self.sensor_combos[sensor_type].items():
                if sensor_id in default_values:
                    body_part_ui = self._convert_model_part_to_ui(default_values[sensor_id])
                    index = combo.findText(body_part_ui)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)  # "-- Not assigned --"
        
        # Update 3D model
        if sensor_type == "IMU":
            for sensor_id, body_part in default_values.items():
                self.general_model.map_imu_to_body_part(sensor_id, body_part)
                self.imu_model.map_imu_to_body_part(sensor_id, body_part)
        
        # Update badges
        self.update_badges()
        
        QMessageBox.information(
            self, 
            "Reset", 
            f"{sensor_type} sensors have been reset."
        )

    def confirm_mapping(self):
        """Confirm and save mappings"""
        # Mappings are already updated in self.current_mappings
        
        # Emit signal with mappings
        self.mappings_updated.emit(
            self.current_mappings["EMG"],
            self.current_mappings["IMU"],
            self.current_mappings["pMMG"]
        )
        
        # Show summary
        summary = self.generate_mapping_summary(self.current_mappings)
        QMessageBox.information(self, "Mapping Confirmed", summary)
        
        self.accept()

    def generate_mapping_summary(self, mappings):
        """Generate a textual summary of mappings"""
        summary = ""
        for sensor_type, sensors in mappings.items():
            if sensors:  # If sensors are mapped for this type
                summary += f"\n{sensor_type}:\n"
                for sensor_id, body_part in sensors.items():
                    summary += f"  {sensor_type}{sensor_id} → {self._convert_model_part_to_ui(body_part)}\n"
        
        if not summary:
            return "No sensors have been assigned."
        
        return summary

    def reset_to_default(self):
        """Reset all mappings to default values"""
        default_mappings = {
            'EMG': {
                1: 'biceps_l',
                2: 'biceps_r',
                3: 'quadriceps_l', 
                4: 'quadriceps_r'
            },
            'IMU': {
                1: 'torso',
                2: 'forearm_l',
                3: 'forearm_r',
                4: 'calves_l',
                5: 'calves_r',
                6: 'head'
            },
            'pMMG': {
                1: 'deltoid_l',
                2: 'deltoid_r'
            }
        }
        
        self.current_mappings = default_mappings
        
        # Update combos
        self.load_current_mappings()
        
        # Update badges
        self.update_badges()
        
        QMessageBox.information(self, "Reset", "All mappings have been reset to default values.")

    def _convert_model_part_to_ui(self, model_part):
        """Convert a model part name to a readable UI name"""
        if not model_part:
            return "-- Not assigned --"
            
        mapping = {
            # Head/Neck
            'head': 'Head',
            'neck': 'Neck',
            
            # Torso
            'torso': 'Torso',
            
            # Upper body - Left side
            'deltoid_l': 'Left Deltoid',
            'biceps_l': 'Left Biceps',
            'forearm_l': 'Left Forearm',
            'dorsalis_major_l': 'Left Latissimus Dorsi',
            'pectorals_l': 'Left Pectorals',
            'left_hand': 'Left Hand',
            
            # Upper body - Right side
            'deltoid_r': 'Right Deltoid',
            'biceps_r': 'Right Biceps',
            'forearm_r': 'Right Forearm', 
            'dorsalis_major_r': 'Right Latissimus Dorsi',
            'pectorals_r': 'Right Pectorals',
            'right_hand': 'Right Hand',
            
            # Lower body
            'hip': 'Hip',
            'quadriceps_l': 'Left Quadriceps',
            'quadriceps_r': 'Right Quadriceps',
            'ishcio_hamstrings_l': 'Left Hamstrings',
            'ishcio_hamstrings_r': 'Right Hamstrings',
            'calves_l': 'Left Calf',
            'calves_r': 'Right Calf',
            'glutes_l': 'Left Gluteus',
            'glutes_r': 'Right Gluteus',
            'left_foot': 'Left Foot',
            'right_foot': 'Right Foot'
        }
        return mapping.get(model_part, model_part)

    def _convert_ui_to_model_part(self, ui_name):
        """Convert a UI name to a model part name"""
        mapping = {
            # Head/Neck
            'Head': 'head',
            'Neck': 'neck',
            
            # Torso
            'Torso': 'torso',
            
            # Upper body - Left side
            'Left Deltoid': 'deltoid_l',
            'Left Biceps': 'biceps_l',
            'Left Forearm': 'forearm_l',
            'Left Latissimus Dorsi': 'dorsalis_major_l',
            'Left Pectorals': 'pectorals_l',
            'Left Hand': 'left_hand',
            
            # Upper body - Right side
            'Right Deltoid': 'deltoid_r',
            'Right Biceps': 'biceps_r',
            'Right Forearm': 'forearm_r',
            'Right Latissimus Dorsi': 'dorsalis_major_r',
            'Right Pectorals': 'pectorals_r',
            'Right Hand': 'right_hand',
            
            # Lower body
            'Hip': 'hip',
            'Left Quadriceps': 'quadriceps_l',
            'Right Quadriceps': 'quadriceps_r',
            'Left Hamstrings': 'ishcio_hamstrings_l',
            'Right Hamstrings': 'ishcio_hamstrings_r',
            'Left Calves': 'calves_l',
            'Right Calves': 'calves_r',
            'Left Gluteus': 'glutes_l',
            'Right Gluteus': 'glutes_r',
            'Left Foot': 'left_foot',
            'Right Foot': 'right_foot'
        }
        return mapping.get(ui_name, ui_name.lower().replace(' ', '_'))


# Renommer la classe existante pour éviter les conflits
SensorMappingDialog = SimplifiedMappingDialog

if __name__ == '__main__':
    # For testing
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = SensorMappingDialog()
    if dialog.exec_() == QDialog.Accepted:
        print("Dialog accepted")
    sys.exit(0)