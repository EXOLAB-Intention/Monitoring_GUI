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
        
        # Store available sensors
        self.available_sensors = available_sensors or {
            'EMG': [],
            'IMU': [],
            'pMMG': []
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

        # Add a message at the top if we have available sensors to assign
        if any(self.available_sensors.values()):
            info_label = QLabel("📍 Configure sensor assignments for optimal motion tracking")
            info_label.setStyleSheet("""
                QLabel {
                    background-color: #E3F2FD;
                    border: 1px solid #2196F3;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: #1976D2;
                    font-size: 13px;
                }
            """)
            main_layout.addWidget(info_label)

        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Style des onglets - ajoutez ceci juste après la création du widget tab_widget
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                background: white;
                margin-top: 10px;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 10px 20px;
                margin-right: 2px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
                color: #2196F3;
            }
            QTabBar::tab:hover:!selected {
                background: #e8e8e8;
            }
        """)

        # Create tabs for each sensor type
        if self.available_sensors.get('EMG'):
            emg_tab = self.create_specific_tab('EMG', len(self.available_sensors['EMG']))
            self.tab_widget.addTab(emg_tab, f"EMG Sensors ({len(self.available_sensors['EMG'])})")
        
        if self.available_sensors.get('IMU'):
            imu_tab = self.create_specific_tab('IMU', len(self.available_sensors['IMU']))
            self.tab_widget.addTab(imu_tab, f"IMU Sensors ({len(self.available_sensors['IMU'])})")
            
        if self.available_sensors.get('pMMG'):
            pmmg_tab = self.create_specific_tab('pMMG', len(self.available_sensors['pMMG']))
            self.tab_widget.addTab(pmmg_tab, f"pMMG Sensors ({len(self.available_sensors['pMMG'])})")

        # Add general overview tab
        general_tab = self.create_general_tab()
        self.tab_widget.addTab(general_tab, "Overview & Summary")

        main_layout.addWidget(self.tab_widget)

        # Grouper les contrôles avancés
        advanced_controls_group = QGroupBox("Advanced Controls")
        advanced_layout = QHBoxLayout()
        
        # Boutons de calibration et debug
        self.calibration_button = QPushButton("🎯 Start IMU Calibration")
        self.calibration_button.setToolTip("Calibrate IMU sensors for better accuracy\n(Stand in T-pose for 3 seconds)")
        self.calibration_button.clicked.connect(self.start_calibration)
        
        self.debug_button = QPushButton("🐛 Debug Mode")
        self.debug_button.setToolTip("Enable debug mode to monitor sensor data quality")
        self.debug_button.clicked.connect(self.toggle_debug)
        
        # Boutons d'action rapide
        self.auto_assign_button = QPushButton("⚡ Auto Assign")
        self.auto_assign_button.setToolTip("Automatically assign sensors to body parts")
        self.auto_assign_button.clicked.connect(self.auto_suggest_mappings)
        
        self.reset_button = QPushButton("🔄 Reset All")
        self.reset_button.setToolTip("Reset all sensor assignments")
        self.reset_button.clicked.connect(self.reset_to_default)
        
        # Style pour les boutons avancés
        advanced_button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 16px;
                color: #495057;
                font-size: 12px;
                font-weight: 500;
                min-height: 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """
        
        # Styles spéciaux pour certains boutons
        calibration_style = """
            QPushButton {
                background-color: #FF9800;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                min-height: 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
        """
        
        debug_style = """
            QPushButton {
                background-color: #9C27B0;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 12px;
                font-weight: 500;
                min-height: 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
        """
        
        self.calibration_button.setStyleSheet(calibration_style)
        self.debug_button.setStyleSheet(debug_style)
        self.auto_assign_button.setStyleSheet(advanced_button_style)
        self.reset_button.setStyleSheet(advanced_button_style)
        
        advanced_layout.addWidget(self.calibration_button)
        advanced_layout.addWidget(self.debug_button)
        advanced_layout.addWidget(self.auto_assign_button)
        advanced_layout.addWidget(self.reset_button)
        advanced_layout.addStretch()
        
        advanced_controls_group.setLayout(advanced_layout)
        advanced_controls_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #555;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(advanced_controls_group)

        # Boutons de confirmation avec un meilleur style
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.confirm_button = QPushButton("✅ Apply Configuration")
        self.confirm_button.clicked.connect(self.confirm_mapping)
        self.confirm_button.setDefault(True)
        
        # Styles pour les boutons de confirmation
        cancel_style = """
            QPushButton {
                background-color: #6c757d;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """
        
        confirm_style = """
            QPushButton {
                background-color: #28a745;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """
        
        self.cancel_button.setStyleSheet(cancel_style)
        self.confirm_button.setStyleSheet(confirm_style)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # Load current mappings and update badges
        self.load_current_mappings()
        self.update_badges()

    def start_calibration(self):
        """Démarre la calibration des IMU."""
        if hasattr(self.parent(), 'model_3d_widget'):
            result = QMessageBox.question(self, "IMU Calibration", 
                                   "🎯 IMU Calibration Process\n\n"
                                   "This will calibrate your IMU sensors for better accuracy.\n\n"
                                   "Instructions:\n"
                                   "1. Stand in T-pose (arms extended horizontally)\n"
                                   "2. Face forward and remain completely still\n"
                                   "3. Calibration will start in 3 seconds and last 3 seconds\n\n"
                                   "Are you ready to start?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.Yes)
            
            if result == QMessageBox.Yes:
                # Délai de 3 secondes pour se préparer
                QTimer.singleShot(3000, lambda: self.parent().model_3d_widget.model_viewer.start_calibration(3))
                
                # Désactiver le bouton temporairement
                self.calibration_button.setEnabled(False)
                self.calibration_button.setText("🎯 Calibrating...")
                
                # Réactiver après 6 secondes (3s préparation + 3s calibration)
                QTimer.singleShot(6000, self._reset_calibration_button)
        else:
            QMessageBox.warning(self, "Error", "3D model viewer not available")

    def _reset_calibration_button(self):
        """Remet le bouton de calibration à l'état normal."""
        self.calibration_button.setEnabled(True)
        self.calibration_button.setText("🎯 Start IMU Calibration")
        QMessageBox.information(self, "Calibration Complete", 
                               "✅ IMU calibration completed successfully!\n\n"
                               "Your sensors are now calibrated for optimal tracking accuracy.")

    def toggle_debug(self):
        """Active/désactive le mode debug."""
        if hasattr(self.parent(), 'model_3d_widget'):
            debug_active = self.parent().model_3d_widget.model_viewer.toggle_debug_mode()
            
            if debug_active:
                self.debug_button.setText("🐛 Debug: ON")
                self.debug_button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                        color: white;
                        font-size: 12px;
                        font-weight: 500;
                        min-height: 30px;
                        min-width: 120px;
                    }
                    QPushButton:hover {
                        background-color: #43A047;
                    }
                """)
                # Afficher les informations de debug
                QTimer.singleShot(500, self._show_debug_info)
            else:
                self.debug_button.setText("🐛 Debug Mode")
                self.debug_button.setStyleSheet("""
                    QPushButton {
                        background-color: #9C27B0;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                        color: white;
                        font-size: 12px;
                        font-weight: 500;
                        min-height: 30px;
                        min-width: 120px;
                    }
                    QPushButton:hover {
                        background-color: #7B1FA2;
                    }
                """)

    def _show_debug_info(self):
        """Affiche les informations de debug dans une fenêtre séparée."""
        if hasattr(self.parent(), 'model_3d_widget'):
            debug_info = self.parent().model_3d_widget.model_viewer.get_debug_info()
            if debug_info:
                msg = f"""🐛 Debug Information:

📡 Active IMUs: {', '.join(map(str, debug_info['active_imus'])) if debug_info['active_imus'] else 'None'}

📊 Signal Quality:
{chr(10).join([f"   • IMU {imu_id}: {info['signal_strength']}% @ {info['data_rate']}Hz" 
               for imu_id, info in debug_info['signal_quality'].items()]) if debug_info['signal_quality'] else '   No active signals'}

🎯 Calibration Status:
   • Calibrated IMUs: {', '.join(map(str, debug_info['calibration_status']['calibrated_imus'])) if debug_info['calibration_status']['calibrated_imus'] else 'None'}
   • Calibration Active: {'Yes' if debug_info['calibration_status']['calibration_active'] else 'No'}

🎮 Animation Priorities:
{chr(10).join([f"   • {part}: {source}" for part, source in debug_info['animation_priorities'].items()]) if debug_info['animation_priorities'] else '   No active animations'}
"""
                QMessageBox.information(self, "Debug Information", msg)

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
        """Suggère automatiquement des mappages pour les IMU basés sur des positions logiques"""
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