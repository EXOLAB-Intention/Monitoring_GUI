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
import json
import os

class MappingBadgesWidget(QWidget):
    def __init__(self, mappings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Define anatomical order of body parts (from head to feet)
        anatomical_order = [
            # Head and neck
            'head', 'neck',
            # Torso
            'torso',
            # Left arm
            'deltoid_l', 'biceps_l', 'forearm_l', 'dorsalis_major_l', 'pectorals_l', 'left_hand',
            # Right arm
            'deltoid_r', 'biceps_r', 'forearm_r', 'dorsalis_major_r', 'pectorals_r', 'right_hand',
            # Pelvis
            'hip',
            # Left leg
            'glutes_l', 'quadriceps_l', 'ishcio_hamstrings_l', 'calves_l', 'left_foot',
            # Right leg
            'glutes_r', 'quadriceps_r', 'ishcio_hamstrings_r', 'calves_r', 'right_foot'
        ]
        
        # Function to convert model name to more readable UI name
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
        
        # Create a dictionary grouping sensors by body part
        body_part_sensors = {}
        for sid, part in mappings.items():
            if part not in body_part_sensors:
                body_part_sensors[part] = []
            body_part_sensors[part].append(sid)
        
        # Add parts in anatomical order
        for part in anatomical_order:
            if part in body_part_sensors:
                h = QHBoxLayout()
                part_label = QLabel(f"<b>{get_display_name(part)}</b>")
                h.addWidget(part_label)
                
                # Add sensors for this part
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
                        badge.setStyleSheet(f"""
                            background: {self._color(typ)}; 
                            color: white; 
                            border-radius: 8px; 
                            padding: 4px 10px; 
                            margin: 3px;
                            font-weight: bold;
                            font-size: 13px;
                        """)
                        h.addWidget(badge)
                
                layout.addLayout(h)
        
        # Add parts not in predefined order (just in case)
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
                        badge.setStyleSheet(f"""
                            background: {self._color(typ)}; 
                            color: white; 
                            border-radius: 8px; 
                            padding: 4px 10px; 
                            margin: 3px;
                            font-weight: bold;
                            font-size: 13px;
                        """)
                        h.addWidget(badge)
                
                layout.addLayout(h)
        
        layout.addStretch(1)

    def _color(self, typ):
        return {
            "IMU": "#00CC33",   # Green as in model_3d_viewer.py
            "EMG": "#CC3300",   # Red as in model_3d_viewer.py
            "pMMG": "#0033CC"   # Blue as in model_3d_viewer.py
        }.get(typ, "#888")

class SimplifiedMappingDialog(QDialog):
    """Simplified interface with tabs for sensor mapping"""
    mappings_updated = pyqtSignal(dict, dict, dict)  # EMG, IMU, pMMG mappings
    
    def __init__(self, parent=None, current_mappings=None):
        super().__init__(parent)
        self.setWindowTitle("Sensor Configuration on 3D Model")
        self.resize(1200, 900)  # Increased from 1000x700 to 1200x900
        self.setMinimumSize(1100, 800)  # Increased from 900x650 to 1100x800
        
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
        title.setStyleSheet("""
            color: #333;
            margin: 10px 0;
            padding: 5px;
            border-bottom: 2px solid #4CAF50;
        """)
        main_layout.addWidget(title)

        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Style tabs
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background: white;
                padding: 10px;
            }
            QTabBar::tab {
                background: #e0e0e0;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 10px 20px;
                margin-right: 4px;
                font-weight: bold;
                font-size: 14px;
                color: #555555;
                min-width: 100px;
                text-align: center;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
                border: 1px solid #388E3C;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background: #f0f0f0;
                border-color: #b0b0b0;
            }
        """)
        
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
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #555;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.reset_button.clicked.connect(self.reset_to_default)
        
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        self.confirm_button.clicked.connect(self.confirm_mapping)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # Initialize combos with current mappings
        self.load_current_mappings()
        
        self.styleAllComboBoxes()

    def styleAllComboBoxes(self):
        """Style all comboboxes to fix dropdowns"""
        for widget in self.findChildren(QComboBox):
            widget.setStyleSheet("""
                QComboBox {
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    padding: 5px 10px;
                    min-height: 30px;
                    background: white;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #d0d0d0;
                }
                QComboBox::down-arrow {
                    image: url(none);
                    width: 14px;
                    height: 14px;
                }
                QComboBox::down-arrow:on {
                    /* shift the arrow when popup is open */
                    top: 1px;
                    left: 1px;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #d0d0d0;
                    selection-background-color: #e0e0e0;
                    selection-color: black;
                    background-color: white;
                    padding: 2px;
                }
            """)

    def create_general_tab(self):
        """Create general tab with 3D model and manual assignment"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Create a splitter for horizontal layout
        splitter = QSplitter(Qt.Horizontal)
        
        # 3D Model - Now in a container on the left
        model_container = QWidget()
        model_layout = QVBoxLayout(model_container)
        
        model_group = QGroupBox("3D Model")
        model_inner_layout = QVBoxLayout()
        self.general_model = Model3DWidget()
        model_inner_layout.addWidget(self.general_model)
        model_group.setLayout(model_inner_layout)
        model_layout.addWidget(model_group)
        
        splitter.addWidget(model_container)
        
        # Manual assignment - Now on the right side
        assign_container = QWidget()
        assign_container_layout = QVBoxLayout(assign_container)
        
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
        self.body_part_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 30px;
                background: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #d0d0d0;
            }
            QComboBox::down-arrow {
                image: url(none);
                width: 14px;
                height: 14px;
            }
            QComboBox::down-arrow:on {
                /* shift the arrow when popup is open */
                top: 1px;
                left: 1px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d0d0;
                selection-background-color: #e0e0e0;
                selection-color: black;
                background-color: white;
                padding: 2px;
            }
        """)
        assign_layout.addWidget(self.body_part_combo, 0, 1)
        
        # Sensor type
        assign_layout.addWidget(QLabel("Sensor type:"), 1, 0)
        self.sensor_type_combo = QComboBox()
        self.sensor_type_combo.addItems(["EMG", "IMU", "pMMG"])
        self.sensor_type_combo.currentTextChanged.connect(self.update_sensor_list)
        self.sensor_type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 30px;
                background: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #d0d0d0;
            }
            QComboBox::down-arrow {
                image: url(none);
                width: 14px;
                height: 14px;
            }
            QComboBox::down-arrow:on {
                /* shift the arrow when popup is open */
                top: 1px;
                left: 1px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d0d0;
                selection-background-color: #e0e0e0;
                selection-color: black;
                background-color: white;
                padding: 2px;
            }
        """)
        assign_layout.addWidget(self.sensor_type_combo, 1, 1)
        
        # Sensor number
        assign_layout.addWidget(QLabel("Sensor:"), 2, 0)
        self.sensor_id_combo = QComboBox()
        self.sensor_id_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 30px;
                background: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #d0d0d0;
            }
            QComboBox::down-arrow {
                image: url(none);
                width: 14px;
                height: 14px;
            }
            QComboBox::down-arrow:on {
                /* shift the arrow when popup is open */
                top: 1px;
                left: 1px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d0d0;
                selection-background-color: #e0e0e0;
                selection-color: black;
                background-color: white;
                padding: 2px;
            }
        """)
        assign_layout.addWidget(self.sensor_id_combo, 2, 1)
        self.update_sensor_list("IMU")
        
        # Assignment button
        self.manual_assign_button = QPushButton("Assign this Sensor")
        self.manual_assign_button.clicked.connect(self.manual_assign)
        self.manual_assign_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        assign_layout.addWidget(self.manual_assign_button, 3, 0, 1, 2)
        
        assign_group.setLayout(assign_layout)
        assign_container_layout.addWidget(assign_group)
        assign_container_layout.addStretch(1)  # Add stretch to keep the assign group at the top
        
        # Add a help section below the assignment controls
        help_group = QGroupBox("Help")
        help_layout = QVBoxLayout()
        help_text = QLabel(
            "Use this panel to assign sensors to body parts. "
            "Select the body part first, then choose the sensor type and number. "
            "Click 'Assign this Sensor' to complete the mapping."
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        help_group.setLayout(help_layout)
        assign_container_layout.addWidget(help_group)
        
        splitter.addWidget(assign_container)
        
        # Set the proportion (70% model, 30% controls)
        splitter.setSizes([int(splitter.width() * 0.7), int(splitter.width() * 0.3)])
        
        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def create_specific_tab(self, sensor_type, num_sensors):
        """Create a specific tab for each sensor type"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"{sensor_type} Sensor Configuration")
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
        instructions = QLabel(f"Assign {sensor_type} sensors to different body parts")
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
        
        # Determine sensor IDs to use based on type
        sensor_ids = []
        if sensor_type == "IMU" and self.detected_sensors and 'imu_ids' in self.detected_sensors:
            sensor_ids = self.detected_sensors['imu_ids']
        elif sensor_type == "EMG" and self.detected_sensors and 'emg_ids' in self.detected_sensors:
            sensor_ids = self.detected_sensors['emg_ids']
        elif sensor_type == "pMMG" and self.detected_sensors and 'pmmg_ids' in self.detected_sensors:
            sensor_ids = self.detected_sensors['pmmg_ids']
        else:
            # Fallback if no sensors detected
            sensor_ids = list(range(1, num_sensors + 1))
        
        # Create controls for each detected sensor ID
        for i, sensor_id in enumerate(sensor_ids):
            label = QLabel(f"{sensor_type} {sensor_id}")
            label.setStyleSheet(f"color: {self._get_color_for_type(sensor_type)};")
            
            combo = QComboBox()
            combo.addItems(body_parts)
            combo.setStyleSheet("""
                QComboBox {
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    padding: 5px 10px;
                    min-height: 30px;
                    background: white;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #d0d0d0;
                }
                QComboBox::down-arrow {
                    image: url(none);
                    width: 14px;
                    height: 14px;
                }
                QComboBox::down-arrow:on {
                    top: 1px;
                    left: 1px;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #d0d0d0;
                    selection-background-color: #e0e0e0;
                    selection-color: black;
                    background-color: white;
                    padding: 2px;
                }
            """)
            combo.currentTextChanged.connect(lambda text, s=sensor_type, id=sensor_id: self.on_combo_changed(s, id, text))
            
            control_grid.addWidget(label, i, 0)
            control_grid.addWidget(combo, i, 1)
            
            self.sensor_combos[sensor_type][sensor_id] = combo
        
        control_layout.addLayout(control_grid)
        control_layout.addStretch()
        
        # Reset button for this sensor type
        reset_button = QPushButton(f"Reset {sensor_type}")
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
        """Update the list of available sensors based on type and detected sensors"""
        self.sensor_id_combo.clear()
        
        # Check if detected_sensors is properly initialized
        if not hasattr(self, 'detected_sensors'):
            self.detected_sensors = {}
        
        # Limit to detected sensors
        has_detected_sensors = False
        
        if sensor_type == "IMU" and self.detected_sensors and 'imu_ids' in self.detected_sensors and self.detected_sensors['imu_ids']:
            for imu_id in self.detected_sensors['imu_ids']:
                self.sensor_id_combo.addItem(f"{imu_id}")
            has_detected_sensors = True
        elif sensor_type == "EMG" and self.detected_sensors and 'emg_ids' in self.detected_sensors and self.detected_sensors['emg_ids']:
            for emg_id in self.detected_sensors['emg_ids']:
                self.sensor_id_combo.addItem(f"{emg_id}")
            has_detected_sensors = True
        elif sensor_type == "pMMG" and self.detected_sensors and 'pmmg_ids' in self.detected_sensors and self.detected_sensors['pmmg_ids']:
            for pmmg_id in self.detected_sensors['pmmg_ids']:
                self.sensor_id_combo.addItem(f"{pmmg_id}")
            has_detected_sensors = True
        
        # Fallback to standard behavior if no sensors detected
        if not has_detected_sensors:
            num_sensors = 8 if sensor_type in ["EMG", "pMMG"] else 6
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
        """Load current mappings into combos"""
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
        
        # Update all 3D models
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
        """Update the badge display"""
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
        # Try to load custom default mappings
        filepath = os.path.join(os.path.dirname(__file__), 'default_sensor_mappings.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    default_mappings = json.load(f)
                
                # Convert string keys to int
                for sensor_type in ['EMG', 'IMU', 'pMMG']:
                    if sensor_type in default_mappings:
                        self.current_mappings[sensor_type] = {int(k): v for k, v in default_mappings[sensor_type].items()}
                
                QMessageBox.information(self, "Reset", "All mappings have been reset to your custom default values.")
            except Exception as e:
                # Use system defaults if there's an error
                self._use_system_defaults()
        else:
            # Use system defaults if no custom file exists
            self._use_system_defaults()
        
        # Update the UI
        self.load_current_mappings()
        self.update_badges()

    def _use_system_defaults(self):
        """Use system default mappings"""
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
        QMessageBox.information(self, "Reset", "All mappings have been reset to system default values.")

    def _convert_model_part_to_ui(self, model_part):
        """Convert model part names to more readable UI names."""
        mapping = {
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
        return mapping.get(model_part, model_part.capitalize())

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


class SensorMappingDialog(SimplifiedMappingDialog):
    def __init__(self, parent=None, current_mappings=None):
        # Initialize detected_sensors BEFORE calling the parent constructor
        self.detected_sensors = {}
        
        # Get detected sensors from parent
        if parent and hasattr(parent, 'backend') and hasattr(parent.backend, 'sensor_config'):
            self.detected_sensors = parent.backend.sensor_config or {}
        
        # Now call the parent constructor
        super().__init__(parent, current_mappings)
        
        self.setWindowTitle("Sensor Configuration on 3D Model")
        self.resize(1200, 900)
        self.setMinimumSize(1100, 800)

if __name__ == '__main__':
    # For testing
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = SensorMappingDialog()
    if dialog.exec_() == QDialog.Accepted:
        print("Dialog accepted")
    sys.exit(0)