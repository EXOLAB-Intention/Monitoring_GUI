import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget, QSplitter, QGridLayout, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont
import json
import os

# Add parent directory to sys.path for relative imports
if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from plots.model_3d_viewer import Model3DWidget

# Centraliser les mappings de noms de parties du corps et les couleurs de capteurs
BODY_PART_UI_TO_MODEL = {
    'Head': 'head', 'Neck': 'neck', 'Torso': 'torso',
    'Left Deltoid': 'deltoid_l', 'Left Biceps': 'biceps_l', 'Left Forearm': 'forearm_l',
    'Left Latissimus Dorsi': 'dorsalis_major_l', 'Left Pectorals': 'pectorals_l',
    'Left Hand': 'left_hand', 'Right Deltoid': 'deltoid_r', 'Right Biceps': 'biceps_r',
    'Right Forearm': 'forearm_r', 'Right Latissimus Dorsi': 'dorsalis_major_r',
    'Right Pectorals': 'pectorals_r', 'Right Hand': 'right_hand', 'Hip': 'hip',
    'Left Quadriceps': 'quadriceps_l', 'Right Quadriceps': 'quadriceps_r',
    'Left Hamstrings': 'ishcio_hamstrings_l', 'Right Hamstrings': 'ishcio_hamstrings_r',
    'Left Calves': 'calves_l', 'Right Calves': 'calves_r',
    'Left Gluteus': 'glutes_l', 'Right Gluteus': 'glutes_r',
    'Left Foot': 'left_foot', 'Right Foot': 'right_foot'
}
BODY_PART_MODEL_TO_UI = {v: k for k, v in BODY_PART_UI_TO_MODEL.items()}
SENSOR_TYPE_COLORS = {"IMU": "#00CC33", "EMG": "#CC3300", "pMMG": "#0033CC"}

class MappingBadgesWidget(QWidget):
    def __init__(self, mappings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        anatomical_order = [
            'head', 'neck', 'torso',
            'deltoid_l', 'biceps_l', 'forearm_l', 'dorsalis_major_l', 'pectorals_l', 'left_hand',
            'deltoid_r', 'biceps_r', 'forearm_r', 'dorsalis_major_r', 'pectorals_r', 'right_hand',
            'hip', 'glutes_l', 'quadriceps_l', 'ishcio_hamstrings_l', 'calves_l', 'left_foot',
            'glutes_r', 'quadriceps_r', 'ishcio_hamstrings_r', 'calves_r', 'right_foot'
        ]

        def get_display_name(part):
            part_names = {
                'head': 'Head', 'neck': 'Neck', 'torso': 'Torso',
                'deltoid_l': 'Left Deltoid', 'biceps_l': 'Left Biceps', 'forearm_l': 'Left Forearm',
                'dorsalis_major_l': 'Left Latissimus Dorsi', 'pectorals_l': 'Left Pectorals',
                'left_hand': 'Left Hand', 'deltoid_r': 'Right Deltoid', 'biceps_r': 'Right Biceps',
                'forearm_r': 'Right Forearm', 'dorsalis_major_r': 'Right Latissimus Dorsi',
                'pectorals_r': 'Right Pectorals', 'right_hand': 'Right Hand', 'hip': 'Hip',
                'glutes_l': 'Left Gluteus', 'quadriceps_l': 'Left Quadriceps',
                'ishcio_hamstrings_l': 'Left Hamstrings', 'calves_l': 'Left Calf', 'left_foot': 'Left Foot',
                'glutes_r': 'Right Gluteus', 'quadriceps_r': 'Right Quadriceps',
                'ishcio_hamstrings_r': 'Right Hamstrings', 'calves_r': 'Right Calf', 'right_foot': 'Right Foot'
            }
            return part_names.get(part, part.capitalize())

        body_part_sensors = {}
        for sid, part in mappings.items():
            if part not in body_part_sensors:
                body_part_sensors[part] = []
            body_part_sensors[part].append(sid)

        for part in anatomical_order:
            if part in body_part_sensors:
                h = QHBoxLayout()
                h.setSpacing(10)
                part_label = QLabel(f"<b>{get_display_name(part)}</b>")
                part_label.setMinimumWidth(120)
                part_label.setStyleSheet("font-size: 14px;")
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
                            padding: 4px 14px;
                            margin: 3px;
                            font-weight: bold;
                            font-size: 14px;
                        """)
                        h.addWidget(badge)

                layout.addLayout(h)

        for part in body_part_sensors:
            if part not in anatomical_order:
                h = QHBoxLayout()
                h.setSpacing(10)
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
                            padding: 4px 14px;
                            margin: 3px;
                            font-weight: bold;
                            font-size: 14px;
                        """)
                        h.addWidget(badge)

                layout.addLayout(h)

        layout.addStretch(1)

    def _color(self, typ):
        return SENSOR_TYPE_COLORS.get(typ, "#888")

class SimplifiedMappingDialog(QDialog):
    mappings_updated = pyqtSignal(dict, dict, dict)

    def __init__(self, parent=None, current_mappings=None, available_sensors=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration des capteurs sur le modèle 3D")
        # Increased initial and minimum height
        self.resize(1200, 960) 
        self.setMinimumSize(1100, 920)

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

        self.available_sensors = available_sensors or {
            'EMG': [],
            'IMU': [],
            'pMMG': []
        }

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title = QLabel("Sensor Mapping Configuration")
        title.setFont(QFont("Arial", 24, QFont.Bold)) # Increased font size from 20 to 24
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #333; margin: 10px 0; padding: 5px; border-bottom: 2px solid #4CAF50;")
        main_layout.addWidget(title)

        if any(self.available_sensors.values()):
            available_msg = QLabel("New sensors detected! Please match them with the correct body parts.")
            available_msg.setStyleSheet("background-color: #e3f2fd; color: #0d47a1; padding: 10px; border-radius: 5px; font-weight: bold; margin: 5px 0;")
            main_layout.addWidget(available_msg)

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

        self.tab_widget = QTabWidget()
        # Ensure the tab widget has a good minimum height and can expand vertically
        self.tab_widget.setMinimumHeight(450) 
        self.tab_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #d0d0d0; border-radius: 4px; background: white; padding: 10px; }
            QTabBar::tab { background: #e0e0e0; border: 1px solid #c0c0c0; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; padding: 10px 20px; margin-right: 4px; font-weight: bold; font-size: 14px; color: #555555; min-width: 100px; text-align: center; }
            QTabBar::tab:selected { background: #4CAF50; color: white; border: 1px solid #388E3C; border-bottom: none; }
            QTabBar::tab:hover:!selected { background: #f0f0f0; border-color: #b0b0b0; }
        """)

        self.general_tab = self.create_general_tab()
        self.emg_tab = self.create_specific_tab("EMG", 8)
        self.imu_tab = self.create_specific_tab("IMU", 6)
        self.pmmg_tab = self.create_specific_tab("pMMG", 8)

        self.tab_widget.addTab(self.general_tab, "General View")
        self.tab_widget.addTab(self.emg_tab, "EMG")
        self.tab_widget.addTab(self.imu_tab, "IMU")
        self.tab_widget.addTab(self.pmmg_tab, "pMMG")

        main_layout.addWidget(self.tab_widget, 1) # Ensure tab_widget expands (already set in previous step, confirming)

        badges_group = QGroupBox("Assignment Summary")
        badges_group.setStyleSheet("QGroupBox { margin-top: 20px; }")
        badges_layout = QVBoxLayout()
        self.scroll_badges = QScrollArea()
        self.scroll_badges.setWidgetResizable(True)
        self.scroll_badges.setMinimumHeight(200)
        self.scroll_badges.setMaximumHeight(350)

        all_mappings = {}
        for sensor_type, mappings in self.current_mappings.items():
            for sensor_id, body_part in mappings.items():
                all_mappings[f"{sensor_type}{sensor_id}"] = body_part

        self.badges_widget = MappingBadgesWidget(all_mappings, self)
        self.scroll_badges.setWidget(self.badges_widget)
        badges_layout.addWidget(self.scroll_badges)
        badges_group.setLayout(badges_layout)
        main_layout.addWidget(badges_group)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(18)
        button_layout.setContentsMargins(0, 10, 0, 0)

        self.reset_button = QPushButton("Reset to Default Values")
        self.reset_button.setStyleSheet("""
            QPushButton { background-color: #f0f0f0; border: none; border-radius: 6px; padding: 10px 20px; color: #555; font-size: 14px; font-weight: 500; }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)
        self.reset_button.clicked.connect(self.reset_to_default)

        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; border: none; border-radius: 6px; padding: 10px 20px; color: white; font-size: 14px; font-weight: 500; }
            QPushButton:hover { background-color: #43A047; }
            QPushButton:pressed { background-color: #388E3C; }
        """)
        self.confirm_button.clicked.connect(self.confirm_mapping)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton { background-color: #f44336; border: none; border-radius: 6px; padding: 10px 20px; color: white; font-size: 14px; font-weight: 500; }
            QPushButton:hover { background-color: #e53935; }
            QPushButton:pressed { background-color: #d32f2f; }
        """)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

        self.load_current_mappings()
        self.styleAllComboBoxes()

    def styleAllComboBoxes(self):
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
        tab = QWidget()
        layout = QVBoxLayout()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        model_container = QWidget()
        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(0)

        model_group = QGroupBox("3D Model")
        model_inner_layout = QVBoxLayout()
        self.general_model = Model3DWidget()
        self.general_model.setMinimumSize(250, 350)
        self.general_model.setMaximumSize(350, 500)
        self.general_model.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        model_inner_layout.addWidget(self.general_model)
        model_group.setLayout(model_inner_layout)
        model_layout.addWidget(model_group)
        model_layout.addStretch(1)
        model_container.setMinimumWidth(260)
        model_container.setMaximumWidth(380)
        model_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        splitter.addWidget(model_container)

        if hasattr(self.general_model, "set_camera_distance"):
            self.general_model.set_camera_distance(2.5)
        elif hasattr(self.general_model, "set_view_distance"):
            self.general_model.set_view_distance(2.5)
        elif hasattr(self.general_model, "setCameraDistance"):
            self.general_model.setCameraDistance(2.5)
        elif hasattr(self.general_model, "zoom_out"):
            self.general_model.zoom_out()

        assign_container = QWidget()
        assign_container_layout = QVBoxLayout(assign_container)
        assign_container_layout.setContentsMargins(0, 0, 0, 0)
        assign_container_layout.setSpacing(0)

        assign_group = QGroupBox("Assign a Sensor")
        assign_layout = QGridLayout()
        assign_layout.setVerticalSpacing(12)
        assign_layout.setHorizontalSpacing(10)

        assign_layout.addWidget(QLabel("Body part:"), 0, 0)
        self.body_part_combo = QComboBox()

        upper_body = [
            "Head", "Neck", "Torso",
            "Left Deltoid", "Left Biceps", "Left Forearm", "Left Latissimus Dorsi", "Left Pectorals", "Left Hand",
            "Right Deltoid", "Right Biceps", "Right Forearm", "Right Latissimus Dorsi", "Right Pectorals", "Right Hand"
        ]

        lower_body = [
            "Hip",
            "Left Quadriceps", "Left Hamstrings", "Left Calves", "Left Gluteus", "Left Foot",
            "Right Quadriceps", "Right Hamstrings", "Right Calves", "Right Gluteus", "Right Foot"
        ]

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
        assign_layout.addWidget(self.auto_suggest_button, 4, 0, 1, 2)

        assign_group.setLayout(assign_layout)
        assign_container_layout.addWidget(assign_group)
        assign_container_layout.addStretch(1)
        assign_container.setMinimumWidth(350)
        assign_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(assign_container)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 700])

        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def create_specific_tab(self, sensor_type, num_sensors):
        tab = QWidget()
        layout = QVBoxLayout()

        header = QLabel(f"{sensor_type} Sensor Configuration")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        header_row = QHBoxLayout()
        header_row.addStretch()
        reset_button = QPushButton(f"Reset {sensor_type}")
        reset_button.setFixedWidth(120)
        reset_button.clicked.connect(lambda: self.reset_sensor_type(sensor_type))
        header_row.addWidget(reset_button)
        layout.addLayout(header_row)

        instructions = QLabel(f"Assign {sensor_type} sensors to different body parts")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin-bottom: 5px; font-style: italic; color: #333;")
        layout.addWidget(instructions)

        control_widget = QWidget()
        control_layout = QVBoxLayout()
        control_layout.setSpacing(14)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        self.sensor_combos = getattr(self, "sensor_combos", {})
        self.sensor_combos[sensor_type] = {}

        upper_body = [
            "Head", "Neck", "Torso",
            "Left Deltoid", "Left Biceps", "Left Forearm", "Left Latissimus Dorsi", "Left Pectorals", "Left Hand",
            "Right Deltoid", "Right Biceps", "Right Forearm", "Right Latissimus Dorsi", "Right Pectorals", "Right Hand"
        ]
        lower_body = [
            "Hip",
            "Left Quadriceps", "Left Hamstrings", "Left Calves", "Left Gluteus", "Left Foot",
            "Right Quadriceps", "Right Hamstrings", "Right Calves", "Right Gluteus", "Right Foot"
        ]
        body_parts = ["-- Not assigned --"] + upper_body + lower_body

        sensors_to_show = self.available_sensors.get(sensor_type, [])
        if not sensors_to_show:
            sensors_to_show = range(1, num_sensors + 1)

        for i, sensor_id in enumerate(sensors_to_show):
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(f"{sensor_type} {sensor_id}")
            label.setStyleSheet(f"color: {self._get_color_for_type(sensor_type)}; font-size: 14px; min-width: 90px;")
            combo = QComboBox()
            combo.addItems(body_parts)
            combo.setStyleSheet("""
                QComboBox {
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    padding: 6px 14px;
                    min-height: 32px;
                    font-size: 14px;
                    background: white;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 22px;
                    border-left: 1px solid #d0d0d0;
                    background: transparent;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #d0d0d0;
                    selection-background-color: #e0e0e0;
                    selection-color: black;
                    background-color: white;
                    padding: 2px;
                    font-size: 14px;
                }
            """)
            combo.currentTextChanged.connect(lambda text, s=sensor_type, id=sensor_id: self.on_combo_changed(s, id, text))
            row.addWidget(label)
            row.addWidget(combo)
            row.addStretch()
            self.sensor_combos[sensor_type][sensor_id] = combo
            scroll_layout.addLayout(row)

        scroll_layout.addStretch(1)

        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        control_layout.addWidget(scroll_area, stretch=1)

        control_widget.setLayout(control_layout)
        control_widget.setMinimumWidth(420)
        control_widget.setMaximumWidth(900)
        control_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(control_widget, 1) # Add stretch factor here

        tab.setLayout(layout)
        return tab

    def update_sensor_list(self, sensor_type):
        self.sensor_id_combo.clear()
        sensors_to_show = self.available_sensors.get(sensor_type, [])
        if not sensors_to_show:
            num_sensors = 8 if sensor_type in ["EMG", "pMMG"] else 6
            sensors_to_show = range(1, num_sensors + 1)
        for sensor_id in sensors_to_show:
            self.sensor_id_combo.addItem(f"{sensor_id}")

    def manual_assign(self):
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

        if sensor_type == "IMU":
            self.current_mappings["IMU"][sensor_id] = body_part_model
            self.general_model.map_imu_to_body_part(sensor_id, body_part_model)
        elif sensor_type == "EMG":
            self.current_mappings["EMG"][sensor_id] = body_part_model
        elif sensor_type == "pMMG":
            self.current_mappings["pMMG"][sensor_id] = body_part_model

        self.update_badges()

        QMessageBox.information(
            self,
            "Sensor Assigned",
            f"{sensor_type} sensor {sensor_id} has been assigned to {body_part_ui}."
        )

    def auto_suggest_mappings(self):
        suggested_mappings = {
            'IMU': {
                1: 'head',
                2: 'left_hand',
                3: 'right_hand',
                4: 'torso',
                5: 'left_foot',
                6: 'right_foot',
                7: 'forearm_l',
                8: 'forearm_r',
                9: 'biceps_l',
                10: 'biceps_r',
                11: 'quadriceps_l',
                12: 'quadriceps_r',
                13: 'calves_l',
                14: 'calves_r',
                15: 'neck',
                16: 'hip',
                17: 'left_hand',
                18: 'forearm_l',
                19: 'biceps_l',
                20: 'forearm_r',
                21: 'right_hand'
            }
        }

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Apply the suggested automatic mappings for IMUs?")
        msg.setInformativeText("This will replace all existing IMU mappings.")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() == QMessageBox.Yes:
            self.current_mappings["IMU"] = suggested_mappings['IMU'].copy()

            for imu_id, body_part in self.current_mappings["IMU"].items():
                self.general_model.map_imu_to_body_part(imu_id, body_part)

            self.update_badges()

            QMessageBox.information(
                self,
                "Mappings Applied",
                "The automatic mappings for IMUs have been successfully applied."
            )

    def _get_color_for_type(self, typ):
        return SENSOR_TYPE_COLORS.get(typ, "#888")

    def load_current_mappings(self):
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

        for sensor_id, body_part in self.current_mappings["IMU"].items():
            self.general_model.map_imu_to_body_part(sensor_id, body_part)

    def on_combo_changed(self, sensor_type, sensor_id, body_part_ui):
        if body_part_ui == "-- Not assigned --":
            if sensor_id in self.current_mappings[sensor_type]:
                del self.current_mappings[sensor_type][sensor_id]
        else:
            body_part = self._convert_ui_to_model_part(body_part_ui)
            self.current_mappings[sensor_type][sensor_id] = body_part

            if sensor_type == "IMU":
                self.general_model.map_imu_to_body_part(sensor_id, body_part)

        self.update_badges()

    def update_badges(self):
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

        self.current_mappings[sensor_type] = default_values.copy()

        if sensor_type in self.sensor_combos:
            for sensor_id, combo in self.sensor_combos[sensor_type].items():
                if sensor_id in default_values:
                    body_part_ui = self._convert_model_part_to_ui(default_values[sensor_id])
                    index = combo.findText(body_part_ui)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)

        if sensor_type == "IMU":
            for sensor_id, body_part in default_values.items():
                self.general_model.map_imu_to_body_part(sensor_id, body_part)

        self.update_badges()

        QMessageBox.information(
            self,
            "Reset",
            f"{sensor_type} sensors have been reset."
        )

    def confirm_mapping(self):
        self.mappings_updated.emit(
            self.current_mappings["EMG"],
            self.current_mappings["IMU"],
            self.current_mappings["pMMG"]
        )

        summary = self.generate_mapping_summary(self.current_mappings)
        QMessageBox.information(self, "Mapping Confirmed", summary)

        self.accept()

    def generate_mapping_summary(self, mappings):
        summary = ""
        for sensor_type, sensors in mappings.items():
            if sensors:
                summary += f"\n{sensor_type}:\n"
                for sensor_id, body_part in sensors.items():
                    summary += f"  {sensor_type}{sensor_id} → {self._convert_model_part_to_ui(body_part)}\n"

        if not summary:
            return "No sensors have been assigned."

        return summary

    def reset_to_default(self):
        filepath = os.path.join(os.path.dirname(__file__), 'default_sensor_mappings.json')
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    default_mappings = json.load(f)

                for sensor_type in ['EMG', 'IMU', 'pMMG']:
                    if sensor_type in default_mappings:
                        self.current_mappings[sensor_type] = {int(k): v for k, v in default_mappings[sensor_type].items()}

                QMessageBox.information(self, "Reset", "All mappings have been reset to your custom default values.")
            except Exception as e:
                self._use_system_defaults()
        else:
            self._use_system_defaults()

        self.load_current_mappings()
        self.update_badges()

    def _use_system_defaults(self):
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
        return BODY_PART_MODEL_TO_UI.get(model_part, model_part.capitalize())

    def _convert_ui_to_model_part(self, ui_name):
        return BODY_PART_UI_TO_MODEL.get(ui_name, ui_name.lower().replace(' ', '_'))

SensorMappingDialog = SimplifiedMappingDialog
