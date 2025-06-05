import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QSplitter, QGridLayout, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont
from .model_3d_viewer import Model3DWidget
import re
import json
import os

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
            "IMU": "#00CC33",   # Vert comme dans model_3d_viewer.py
            "EMG": "#CC3300",   # Rouge comme dans model_3d_viewer.py
            "pMMG": "#0033CC"   # Bleu comme dans model_3d_viewer.py
        }.get(typ, "#888")

class SimplifiedMappingDialog(QDialog):
    """Interface simplifiée avec onglets pour le mapping des capteurs"""
    mappings_updated = pyqtSignal(dict, dict, dict)  # EMG, IMU, pMMG mappings
    
    def __init__(self, parent=None, current_mappings=None, available_sensors=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration des capteurs sur le modèle 3D")
        # Adjust window size - not too big, not too small
        self.resize(1000, 800)  # Reduced size for better proportion
        self.setMinimumSize(800, 600)  # Smaller minimum size
        
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
        
        # Store available sensors
        self.available_sensors = available_sensors or {
            'EMG': [],
            'IMU': [],
            'pMMG': []
        }
        
        # Debug log
        print(f"Creating sensor mapping dialog with mappings: {self.current_mappings}")
        print(f"Available sensors: {self.available_sensors}")
        
        # Initialize UI immediately instead of delaying
        self.setup_ui()
        
        # Load mappings
        try:
            self.load_current_mappings()
            print("Current mappings loaded successfully")
        except Exception as e:
            print(f"Error loading mappings: {e}")
        
        # For logging when dialog is actually shown
        self.is_visible = False
    
    def showEvent(self, event):
        """Gérer l'affichage de la boîte de dialogue de manière efficace."""
        super().showEvent(event)
        if not self.is_visible:
            print("Sensor mapping dialog is now visible")
            self.is_visible = True
            
            # Update all combo boxes to reflect current selections
            self.styleAllComboBoxes()
            
            # Ensure 3D models in each tab are properly sized and rendered
            if hasattr(self, 'general_model'):
                self.general_model.update()
                
                # Reset view to ensure all models are properly centered and visible
                self.general_model.reset_view()
            
            # Update all 3D models in all tabs
            for sensor_type in ['emg', 'imu', 'pmmg']:
                model_attr = f"{sensor_type}_model"
                if hasattr(self, model_attr):
                    model = getattr(self, model_attr)
                    if model:
                        model.update()
                        model.reset_view()
            
            # Force repaint
            self.repaint()
    
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

        # Add a message at the top if we have available sensors to assign
        if any(self.available_sensors.values()):
            available_msg = QLabel("New sensors detected! Please match them with the correct body parts.")
            available_msg.setStyleSheet("""
                background-color: #e3f2fd;
                color: #0d47a1;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px 0;
            """)
            main_layout.addWidget(available_msg)
            
            # Highlight unassigned sensors
            if self.available_sensors.get('EMG'):
                emg_msg = QLabel(f"EMG: {', '.join([f'EMG{id}' for id in self.available_sensors['EMG']])}")
                emg_msg.setStyleSheet("color: #CC3300; font-weight: bold;")
                main_layout.addWidget(emg_msg)
                
            if self.available_sensors.get('IMU'):
                imu_msg = QLabel(f"IMU: {', '.join([f'IMU{id}' for id in self.available_sensors['IMU']])}")
                imu_msg.setStyleSheet("color: #00CC33; font-weight: bold;")
                main_layout.addWidget(imu_msg)
                
            if self.available_sensors.get('pMMG'):
                pmmg_msg = QLabel(f"pMMG: {', '.join([f'pMMG{id}' for id in self.available_sensors['pMMG']])}")
                pmmg_msg.setStyleSheet("color: #0033CC; font-weight: bold;")
                main_layout.addWidget(pmmg_msg)

        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Style des onglets - ajoutez ceci juste après la création du widget tab_widget
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
        
        # 3D Model - Using proper size policies instead of fixed sizes
        model_container = QWidget()
        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)  # Reduce margins
        
        model_group = QGroupBox("3D Model")
        model_inner_layout = QVBoxLayout()
        self.general_model = Model3DWidget()
        
        # Use minimum size and proper size policy instead of fixed size
        self.general_model.setMinimumSize(300, 400)
        self.general_model.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set camera distance to see the entire model including feet
        self.general_model.model_viewer.camera_distance = 5.0  # Reduced distance
        
        model_inner_layout.addWidget(self.general_model)
        model_group.setLayout(model_inner_layout)
        model_layout.addWidget(model_group)
        
        # Set better size policy
        model_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        splitter.addWidget(model_container)
        
        # Manual assignment - Now on the right side
        assign_container = QWidget()
        assign_layout = QVBoxLayout(assign_container)
        assign_layout.setContentsMargins(5, 5, 5, 5)  # Reduced margins
        
        assign_group = QGroupBox("Assign a Sensor")
        assign_inner_layout = QGridLayout()
        assign_inner_layout.setVerticalSpacing(10)  # Add spacing between rows
        
        # Body part selection
        assign_inner_layout.addWidget(QLabel("Body part:"), 0, 0)
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
        assign_inner_layout.addWidget(self.body_part_combo, 0, 1)
        
        # Sensor type
        assign_inner_layout.addWidget(QLabel("Sensor type:"), 1, 0)
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
        assign_inner_layout.addWidget(self.sensor_type_combo, 1, 1)
        
        # Sensor number
        assign_inner_layout.addWidget(QLabel("Sensor:"), 2, 0)
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
        assign_inner_layout.addWidget(self.sensor_id_combo, 2, 1)
        self.update_sensor_list("IMU")
        
        # Assignment button with proper sizing
        self.manual_assign_button = QPushButton("Assign this Sensor")
        self.manual_assign_button.clicked.connect(self.manual_assign)
        self.manual_assign_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;  /* Reduced padding */
                color: white;
                font-size: 13px;    /* Smaller font */
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        assign_inner_layout.addWidget(self.manual_assign_button, 3, 0, 1, 2)
        
        # Auto-suggest button
        self.auto_suggest_button = QPushButton("Suggest IMU Mappings")
        self.auto_suggest_button.clicked.connect(self.auto_suggest_mappings)
        self.auto_suggest_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1E88E5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
        """)
        assign_inner_layout.addWidget(self.auto_suggest_button, 4, 0, 1, 2)
        
        assign_group.setLayout(assign_inner_layout)
        assign_layout.addWidget(assign_group)
        
        # Better size policy for the right panel
        assign_container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        assign_container.setMaximumWidth(350)  # Limit maximum width
        
        splitter.addWidget(assign_container)
        
        # Set better proportion (60% model, 40% controls)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def create_specific_tab(self, sensor_type, num_sensors):
        """Create a specific tab for each sensor type"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header with reduced margins
        header = QLabel(f"{sensor_type} Sensor Configuration")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setContentsMargins(0, 5, 0, 5)  # Reduced vertical margins
        layout.addWidget(header)
        
        # Split view: 3D model on left, controls on right
        splitter = QSplitter(Qt.Horizontal)
        
        # 3D Model with proper size policy instead of fixed size
        model_container = QWidget()
        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)  # Reduced margins
        
        model_widget = Model3DWidget()
        model_widget.setMinimumSize(300, 400)  # Reduced minimum size
        model_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set camera distance to see the entire model including feet
        model_widget.model_viewer.camera_distance = 5.0  # Reduced distance
        
        model_layout.addWidget(model_widget)
        model_container.setLayout(model_layout)
        
        splitter.addWidget(model_container)
        
        # Store model reference
        setattr(self, f"{sensor_type.lower()}_model", model_widget)
        
        # Assignment controls with better sizing
        control_widget = QWidget()
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)  # Reduced margins
        
        # Instructions with less space
        instructions = QLabel(f"Assign {sensor_type} sensors to different body parts")
        instructions.setWordWrap(True)
        instructions.setContentsMargins(0, 0, 0, 5)  # Reduced bottom margin
        control_layout.addWidget(instructions)
        
        # Use a scroll area to handle many sensors - with better sizing
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        control_grid = QGridLayout(scroll_content)
        control_grid.setVerticalSpacing(8)  # Reduced spacing
        control_grid.setHorizontalSpacing(10)
        control_grid.setContentsMargins(5, 5, 5, 5)  # Reduced margins
        
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
        
        # Use only the available sensors if they exist, otherwise use empty list
        # No fallback to default range - only show detected sensors
        sensors_to_show = self.available_sensors.get(sensor_type, [])
        
        # Display a message if no sensors are available
        if not sensors_to_show:
            no_sensors_label = QLabel(f"No {sensor_type} sensors detected")
            no_sensors_label.setStyleSheet("color: #999; font-style: italic; padding: 20px;")
            control_grid.addWidget(no_sensors_label, 0, 0, 1, 2)
        
        # Group sensors by 5 for better organization when there are many
        SENSORS_PER_ROW = 1  # One sensor per row for clarity
        
        for i, sensor_id in enumerate(sensors_to_show):
            row = i // SENSORS_PER_ROW
            col = (i % SENSORS_PER_ROW) * 2  # *2 because we use 2 columns per sensor
            
            label = QLabel(f"{sensor_type} {sensor_id}:")
            label.setStyleSheet(f"color: {self._get_color_for_type(sensor_type)}; font-weight: bold;")
            
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
            """)
            
            # Store reference to combo box for later access
            self.sensor_combos[sensor_type][sensor_id] = combo
            
            # Setup change handler
            combo.currentTextChanged.connect(
                lambda text, st=sensor_type, sid=sensor_id: 
                self.on_combo_changed(st, sid, text)
            )
            
            control_grid.addWidget(label, row, col)
            control_grid.addWidget(combo, row, col + 1)
        
        scroll_content.setLayout(control_grid)
        scroll.setWidget(scroll_content)
        
        # Better size for the scroll area
        scroll.setMinimumHeight(200)
        control_layout.addWidget(scroll)
        
        control_layout.addStretch()
        
        # Reset button with better sizing
        reset_button = QPushButton(f"Reset {sensor_type}")
        reset_button.clicked.connect(lambda: self.reset_sensor_type(sensor_type))
        reset_button.setMaximumWidth(200)  # Limit width
        reset_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;  /* Reduced padding */
                font-size: 13px;    /* Smaller font */
            }
        """)
        control_layout.addWidget(reset_button, 0, Qt.AlignCenter)
        
        control_widget.setLayout(control_layout)
        control_widget.setMaximumWidth(350)  # Limit maximum width
        control_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        
        splitter.addWidget(control_widget)
        
        # Set better proportions
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def update_sensor_list(self, sensor_type):
        """Mettre à jour la liste des capteurs disponibles en fonction du type sélectionné"""
        self.sensor_id_combo.clear()
        
        # Use only available sensors, no fallback to default range
        sensors_to_show = self.available_sensors.get(sensor_type, [])
        
        # If no sensors are available, add a disabled item
        if not sensors_to_show:
            self.sensor_id_combo.addItem("No sensors detected")
            self.sensor_id_combo.setEnabled(False)
        else:
            self.sensor_id_combo.setEnabled(True)
            for sensor_id in sensors_to_show:
                self.sensor_id_combo.addItem(f"{sensor_id}")

    def manual_assign(self):
        """Manually assign a sensor to a body part"""
        body_part_ui = self.body_part_combo.currentText()
        sensor_type = self.sensor_type_combo.currentText()
        
        if not self.sensor_id_combo.currentText():
            QMessageBox.warning(self, "Warning", "Please select a sensor ID")
            return
            
        try:
            sensor_id = int(self.sensor_id_combo.currentText())
        except ValueError:
            QMessageBox.warning(self, "Warning", "Invalid sensor ID")
            return
            
        body_part_model = self._convert_ui_to_model_part(body_part_ui)
        
        # Update the mapping in the appropriate dictionary
        if sensor_type == "IMU":
            self.current_mappings["IMU"][sensor_id] = body_part_model
            # Mettre à jour le modèle 3D pour montrer immédiatement le changement
            self.general_model.map_imu_to_body_part(sensor_id, body_part_model)
        elif sensor_type == "EMG":
            self.current_mappings["EMG"][sensor_id] = body_part_model
        elif sensor_type == "pMMG":
            self.current_mappings["pMMG"][sensor_id] = body_part_model
            
        # Update the badges
        self.update_badges()
        
        # Feedback to user
        QMessageBox.information(
            self, 
            "Sensor Assigned", 
            f"{sensor_type} sensor {sensor_id} has been assigned to {body_part_ui}."
        )

    def auto_suggest_mappings(self):
        """Suggère automatiquement des mappings pour les IMU basés sur des positions logiques"""
        # Mappages suggérés basés sur l'expérience et les positions anatomiques
        suggested_mappings = {
            # IMU mappings - ajustez selon vos besoins spécifiques
            'IMU': {
                1: 'head',           # Tête
                2: 'left_hand',      # Main gauche
                3: 'right_hand',     # Main droite
                4: 'torso',          # Torse
                5: 'left_foot',      # Pied gauche
                6: 'right_foot',     # Pied droit
                7: 'forearm_l',      # Avant-bras gauche
                8: 'forearm_r',      # Avant-bras droit
                9: 'biceps_l',       # Biceps gauche
                10: 'biceps_r',      # Biceps droit
                11: 'quadriceps_l',  # Quadriceps gauche
                12: 'quadriceps_r',  # Quadriceps droit
                13: 'calves_l',      # Mollet gauche
                14: 'calves_r',      # Mollet droit
                15: 'neck',          # Cou
                16: 'hip',           # Hanche
                17: 'left_hand',     # Main gauche (alternative)
                18: 'forearm_l',     # Avant-bras gauche (alternative)
                19: 'biceps_l',      # Biceps gauche (alternative)
                20: 'forearm_r',     # Avant-bras droit (alternative)
                21: 'right_hand'     # Main droite (alternative)
            }
        }
        
        # Demander confirmation à l'utilisateur
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Appliquer les mappages automatiques suggérés pour les IMU?")
        msg.setInformativeText("Cela remplacera tous les mappages IMU existants.")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            # Appliquer les mappages suggérés
            self.current_mappings["IMU"] = suggested_mappings['IMU'].copy()
            
            # Mettre à jour le modèle 3D pour montrer immédiatement les changements
            for imu_id, body_part in self.current_mappings["IMU"].items():
                self.general_model.map_imu_to_body_part(imu_id, body_part)
            
            # Mettre à jour les badges
            self.update_badges()
            
            QMessageBox.information(
                self,
                "Mappages appliqués",
                "Les mappages automatiques pour les IMU ont été appliqués avec succès."
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
        
        # Force refresh to prevent display glitches
        self.scroll_badges.setVisible(False)
        self.scroll_badges.setVisible(True)

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
        
        # Update badges
        self.update_badges()
        
        QMessageBox.information(
            self, 
            "Reset", 
            f"{sensor_type} sensors have been reset."
        )

    def confirm_mapping(self):
        """Confirm and emit the mapping values."""
        try:
            # Generate final mappings
            emg_mappings = {}
            imu_mappings = {}
            pmmg_mappings = {}
            
            for sensor_id, body_part in self.current_mappings["EMG"].items():
                emg_mappings[sensor_id] = body_part
            
            for sensor_id, body_part in self.current_mappings["IMU"].items():
                imu_mappings[sensor_id] = body_part
            
            for sensor_id, body_part in self.current_mappings["pMMG"].items():
                pmmg_mappings[sensor_id] = body_part
            
            # Emit the signals
            self.mappings_updated.emit(emg_mappings, imu_mappings, pmmg_mappings)
            print(f"Emitted mappings: EMG={emg_mappings}, IMU={imu_mappings}, pMMG={pmmg_mappings}")
            
            # Close the dialog after confirmation
            self.accept()
            
        except Exception as e:
            print(f"Error in confirm_mapping: {e}")
            import traceback
            traceback.print_exc()

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
        # Essayer de charger les mappages par défaut personnalisés
        filepath = os.path.join(os.path.dirname(__file__), 'default_sensor_mappings.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    default_mappings = json.load(f)
                
                # Convertir les clés string en int
                for sensor_type in ['EMG', 'IMU', 'pMMG']:
                    if sensor_type in default_mappings:
                        self.current_mappings[sensor_type] = {int(k): v for k, v in default_mappings[sensor_type].items()}
                
                QMessageBox.information(self, "Reset", "All mappings have been reset to your custom default values.")
            except Exception as e:
                # Utiliser les mappages par défaut du système en cas d'erreur
                self._use_system_defaults()
        else:
            # Utiliser les mappages par défaut du système s'il n'y a pas de fichier personnalisé
            self._use_system_defaults()
        
        # Mettre à jour l'interface utilisateur
        self.load_current_mappings()
        self.update_badges()

    def _use_system_defaults(self):
        """Utilise les mappages par défaut du système"""
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
        """Convertit les noms des parties du modèle 3D vers des noms plus lisibles pour l'UI."""
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