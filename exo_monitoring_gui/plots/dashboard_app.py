import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QMenuBar, QComboBox, QMessageBox, QRadioButton, QButtonGroup, QGroupBox, QTableWidget, QTableWidgetItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush, QCursor
from PyQt5.QtWidgets import QScrollArea
import pyqtgraph as pg

# Ajouter le chemin du répertoire parent de data_generator au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Ajouter l'import du model_3d_viewer et du dialogue de mapping
from plots.model_3d_viewer import Model3DWidget
from plots.sensor_dialogue import SensorMappingDialog
from data_generator.sensor_simulator import SensorSimulator

class DashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1600, 900)
        self.setMinimumSize(1400, 800)
        self.setStyleSheet("background-color: white; color: black;")
        self.modified = False
        self.simulator = SensorSimulator()
        self.recording = False  # Ajouter l'attribut recording
        self.recorded_data = {"EMG": [[] for _ in range(8)], "IMU": [[] for _ in range(6)], "pMMG": [[] for _ in range(8)]}  # Ajouter l'attribut recorded_data

        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(40)  # Mettre à jour les données toutes les 40 ms

    def init_ui(self):
        # Menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet("background-color: white; color: black;")
        self.main_bar = self.some_method()
        self.main_bar._create_menubar()

        # Create actions for the Edit menu
        self.Clear_plots = self.main_bar._create_action(
            "&Clear plots",
            lambda: self.clear_plots(),
            "Ctrl+N"
        )
        self.Refresh_the_connected_system = self.main_bar._create_action(
            "&Refresh the connected system",
            lambda: self.refresh_connected_system(),
            "Ctrl+R"
        )
        self.Request_h5_file_transfer = self.main_bar._create_action(
            "&Request .h5 file transfer",
            lambda: self.request_h5_file_transfer(),
            "Ctrl+H"
        )

        # Add Edit menu
        edit_menu = menubar.addMenu('&Edit')
        edit_menu.addAction(self.Clear_plots)
        edit_menu.addAction(self.Refresh_the_connected_system)
        edit_menu.addAction(self.Request_h5_file_transfer)

        # Enable actions
        self.Clear_plots.setEnabled(True)
        self.Refresh_the_connected_system.setEnabled(True)
        self.Request_h5_file_transfer.setEnabled(True)

        self.main_bar._all_false_or_true(False)
        
        self.Clear_plots.setEnabled(False)
        self.Refresh_the_connected_system.setEnabled(False)
        self.Request_h5_file_transfer.setEnabled(False)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Titles
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Connected Systems"), stretch=1)
        title_layout.addWidget(QLabel("Graphics / Visual Zone"), stretch=2)
        title_layout.addWidget(QLabel("3D Perspective"), stretch=1)
        main_layout.addLayout(title_layout)

        # Main content layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # Connected Systems Panel (gauche)
        self.connected_systems = QTreeWidget()
        self.connected_systems.setHeaderHidden(True)
        self.connected_systems.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            QTreeWidget::item:selected {
                background-color: lightblue;
            }
        """)
        self.connected_systems.setVisible(True)
        self.connected_systems.itemClicked.connect(self.on_sensor_clicked)

        # Organisation des capteurs par sous-groupes
        sensors = ["EMG Data", "IMU Data", "pMMG Data"]
        for sensor_group in sensors:
            group_item = QTreeWidgetItem([sensor_group])
            self.connected_systems.addTopLevelItem(group_item)
            if sensor_group == "IMU Data":
                num_sensors = 6
            else:
                num_sensors = 8
            for i in range(1, num_sensors + 1):
                sensor_item = QTreeWidgetItem([f"{sensor_group[:-5]}{i}"])
                sensor_item.setForeground(0, QBrush(QColor("gray")))  # Gris pour déconnecté
                sensor_item.setHidden(False)  # Affiché par défaut
                group_item.addChild(sensor_item)
            group_item.setExpanded(True)  # Ouvrir la liste déroulante par défaut

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

        # Choix du mode d'affichage
        self.display_mode_group = QButtonGroup()
        self.display_mode_layout = QHBoxLayout()

        self.single_sensor_mode = QRadioButton("1 sensor per plot")
        self.group_sensor_mode = QRadioButton("Plots by sensor groups")
        self.display_mode_group.addButton(self.single_sensor_mode)
        self.display_mode_group.addButton(self.group_sensor_mode)
        self.single_sensor_mode.setChecked(True)

        self.display_mode_layout.addWidget(self.single_sensor_mode)
        self.display_mode_layout.addWidget(self.group_sensor_mode)
        left_panel.addLayout(self.display_mode_layout)

        # Graphics / Visual Zone (centre)
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout()
        self.middle_placeholder.setLayout(self.middle_layout)

        # Ajouter un QScrollArea pour la section "Graphics / Visual Zone"
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.middle_placeholder)

        middle_panel = QVBoxLayout()
        middle_panel.addWidget(scroll_area)

        # 3D Perspective (droite)
        right_panel = QVBoxLayout()
        label_3d_title = QLabel("3D Perspective")
        label_3d_title.setAlignment(Qt.AlignCenter)
        label_3d_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_panel.addWidget(label_3d_title)

        # Remplacer le label statique par le widget 3D
        self.model_3d_widget = Model3DWidget()
        right_panel.addWidget(self.model_3d_widget, stretch=3)

        # Ajouter un bouton pour contrôler l'animation
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        right_panel.addWidget(self.animate_button)

        # Ajouter un bouton pour réinitialiser la vue du modèle 3D
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_model_view)
        right_panel.addWidget(self.reset_view_button)

        # Ajouter le bouton "Load 3D Model"
        self.load_model_button = QPushButton("Load 3D Model")
        self.load_model_button.clicked.connect(self.load_external_model)
        right_panel.addWidget(self.load_model_button)

        # Ajouter le bouton "Configure Sensor Mapping" en bas à droite
        self.config_button = QPushButton("Configure Sensor Mapping")
        self.config_button.setStyleSheet("font-size: 14px; padding: 8px 20px;")
        self.config_button.clicked.connect(self.open_sensor_mapping_dialog)
        right_panel.addWidget(self.config_button)

        # Ajout des panneaux gauche / centre / droite
        content_layout.addLayout(left_panel, stretch=1)  # Réduire la largeur de la section "Connected Systems"
        content_layout.addLayout(middle_panel, stretch=4)  # Augmenter la largeur de la section "Graphics / Visual Zone"
        content_layout.addLayout(right_panel, stretch=2)

        # Footer
        footer_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_sensors)
        self.record_button = QPushButton("Record Start")
        self.record_button.clicked.connect(self.toggle_recording)

        # Style moderne pour les boutons
        button_style = """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 8px 16px;
            color: #333;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
        }

        QPushButton:pressed {
            background-color: #d0d0d0;
            border: 1px solid #b0b0b0;
        }

        QPushButton:disabled {
            background-color: #f9f9f9;
            border: 1px solid #e0e0e0;
            color: #a0a0a0;
        }
        """

        # Boutons spéciaux
        record_button_style = """
        QPushButton {
            background-color: #4caf50;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #43a047;
        }

        QPushButton:pressed {
            background-color: #388e3c;
        }
        """

        animate_button_style = """
        QPushButton {
            background-color: #2196f3;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #1e88e5;
        }

        QPushButton:pressed {
            background-color: #1976d2;
        }
        """

        reset_view_button_style = """
        QPushButton {
            background-color: #9e9e9e;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #8e8e8e;
        }

        QPushButton:pressed {
            background-color: #757575;
        }
        """

        config_button_style = """
        QPushButton {
            background-color: #ff9800;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            min-width: 120px;
        }

        QPushButton:hover {
            background-color: #fb8c00;
        }

        QPushButton:pressed {
            background-color: #f57c00;
        }
        """

        # Appliquer les styles aux boutons
        self.animate_button.setStyleSheet(animate_button_style)
        self.reset_view_button.setStyleSheet(reset_view_button_style)
        self.load_model_button.setStyleSheet(button_style)
        self.config_button.setStyleSheet(config_button_style)
        self.connect_button.setStyleSheet(button_style)
        self.record_button.setStyleSheet(record_button_style)

        for btn in (self.connect_button, self.record_button):
            footer_layout.addWidget(btn)

        main_layout.addLayout(footer_layout)

        # Initialiser les graphiques
        self.plots = {}
        self.plot_data = {}
        self.highlighted_sensors = set()
        self.group_plots = {}
        self.group_plot_data = {}

        # Connecter le signal de changement de mode
        self.display_mode_group.buttonClicked.connect(self.on_display_mode_changed)

    def some_method(self):
        from utils.Menu_bar import MainBar
        return MainBar(self)

    def clear_plots(self):
        # Implement the functionality to clear plots
        print("Clear plots")

    def refresh_connected_system(self):
        # Implement the functionality to refresh the connected system
        print("Refresh the connected system")

    def request_h5_file_transfer(self):
        # Implement the functionality to request .h5 file transfer
        print("Request .h5 file transfer")

    def connect_sensors(self):
        # Connecter les capteurs et les afficher en vert
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_item.setHidden(False)
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté

    def show_sensors(self):
        # Afficher les capteurs et les connecter
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_item.setHidden(False)
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté

        # Créer les graphiques de groupe si le mode est "Graphiques par groupe de capteurs" et qu'ils n'existent pas déjà
        if self.group_sensor_mode.isChecked() and not self.group_plots:
            self.create_group_plots()

    def create_group_plots(self):
        # Vérifier si les graphiques de groupe existent déjà
        if not self.group_plots:
            # Créer les graphiques de groupe pour EMG et pMMG uniquement
            for group in ["EMG", "pMMG"]:
                plot_widget = pg.PlotWidget(title=group)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(group, color='white', size='14pt')
                self.middle_layout.addWidget(plot_widget)
                self.group_plots[group] = plot_widget
                self.group_plot_data[group] = {}

    def update_matched_part(self, text):
        self.matched_part_combo.clear()
        if text == "Upper body w/o head":
            self.matched_part_combo.addItems([
                "pectorals_l", "deltoid_l", "biceps_l", "forearm_l", "dorsalis_major_l",
                "pectorals_r", "deltoid_r", "biceps_r", "forearm_r", "dorsalis_major_r"
            ])
        elif text == "Upper body w/ head":
            self.matched_part_combo.addItems(["pectorals_L", "Deltoid_L", "Biceps_L", "forearm_L", "dorsalis major_L", "pectorals_R", "Deltoid_R", "Biceps_R", "forearm_R",  "dorsalis major_R"])
        elif text == "Lower body":
            self.matched_part_combo.addItems(["Quadriceps_L", "ishcio-hamstrings_L", "calves_L", "glutes_L", "Quadriceps_R", "ishcio-hamstrings_R", "calves_R", "glutes_R"])

    def update_matched_sensors(self, text):
        # Mettre à jour les options de Matched Sensors en fonction de la sélection de Matched Part
        if text:
            self.matched_sensors_combo.clear()
            sensors = ["EMG1", "EMG2", "EMG3", "EMG4", "EMG5", "EMG6", "EMG7", "EMG8",
                       "IMU1", "IMU2", "IMU3", "IMU4", "IMU5", "IMU6",
                       "pMMG1", "pMMG2", "pMMG3", "pMMG4", "pMMG5", "pMMG6", "pMMG7", "pMMG8"]
            self.matched_sensors_combo.addItems(sensors)

    def update_sensor_label(self, text):
        # Mettre à jour le label du capteur avec le Matched Part sélectionné
        self.selected_sensor = text

    def confirm_selection(self):
        # Confirmer la sélection et mettre à jour le label du capteur
        if hasattr(self, 'selected_sensor') and self.selected_sensor and self.matched_part_combo.currentText():
            for i in range(self.connected_systems.topLevelItemCount()):
                group_item = self.connected_systems.topLevelItem(i)
                for j in range(group_item.childCount()):
                    sensor_item = group_item.child(j)
                    if sensor_item.text(0).startswith(self.selected_sensor):
                        matched_part = self.matched_part_combo.currentText()
                        sensor_item.setText(0, f"{self.selected_sensor} ({matched_part})")
                        # Mettre à jour les données du capteur avec le "matched part"
                        self.update_sensor_data(sensor_item.text(0), matched_part)

    def update_sensor_data(self, sensor_name, matched_part):
        # Mettre à jour les données du capteur avec le "matched part"
        pass

    def on_sensor_clicked(self, item, column):
        # Vérifier si le capteur est connecté
        if item.foreground(0).color() != QColor("green"):
            QMessageBox.warning(self, "Error", "The sensor is not connected. Please connect the sensor first.")
            return

        sensor_name = item.text(0).split()[0]  # Extraire le nom du capteur
        if sensor_name in self.plots or sensor_name in self.highlighted_sensors:
            # Désélectionner le capteur
            self.remove_sensor_plot(sensor_name)
        else:
            self.plot_sensor_data(item.text(0))

    def plot_sensor_data(self, sensor_name):
        # Ajouter la courbe du capteur au graphique de groupe correspondant
        if self.group_sensor_mode.isChecked():
            if sensor_name.startswith("IMU"):
                # Créer un nouveau graphique pour le capteur IMU sélectionné
                plot_widget = pg.PlotWidget(title=sensor_name)
                plot_widget.setBackground('#1e1e1e')
                plot_widget.getAxis('left').setTextPen('white')
                plot_widget.getAxis('bottom').setTextPen('white')
                plot_widget.showGrid(x=True, y=True, alpha=0.3)
                plot_widget.setTitle(sensor_name, color='white', size='14pt')

                # Ajouter le graphique à la section "2D Plots"
                self.middle_layout.addWidget(plot_widget)

                # Stocker le graphique et les données
                self.plots[sensor_name.split()[0]] = plot_widget
                self.plot_data[sensor_name.split()[0]] = np.zeros(100)

                # Mettre en surbrillance le capteur sélectionné
                self.highlight_sensor(sensor_name.split()[0])
            else:
                sensor_group = sensor_name.split()[0][:-1]
                if sensor_group in self.group_plots:
                    if sensor_name not in self.group_plot_data[sensor_group]:
                        self.group_plot_data[sensor_group][sensor_name] = np.zeros(100)

                    # Mettre en surbrillance le capteur sélectionné
                    self.highlight_sensor(sensor_name.split()[0])
        else:
            # Créer un nouveau graphique pour le capteur sélectionné
            plot_widget = pg.PlotWidget(title=sensor_name)
            plot_widget.setBackground('#1e1e1e')
            plot_widget.getAxis('left').setTextPen('white')
            plot_widget.getAxis('bottom').setTextPen('white')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setTitle(sensor_name, color='white', size='14pt')

            # Ajouter le graphique à la section "2D Plots"
            self.middle_layout.addWidget(plot_widget)

            # Stocker le graphique et les données
            self.plots[sensor_name.split()[0]] = plot_widget
            self.plot_data[sensor_name.split()[0]] = np.zeros(100)

            # Mettre en surbrillance le capteur sélectionné
            self.highlight_sensor(sensor_name.split()[0])

    def remove_sensor_plot(self, sensor_name):
        # Supprimer le graphique du capteur de la section "2D Plots"
        if sensor_name in self.plots:
            plot_widget = self.plots.pop(sensor_name)
            plot_widget.setParent(None)
            plot_widget.deleteLater()

            # Retirer la surbrillance du capteur
            self.unhighlight_sensor(sensor_name)
        else:
            sensor_group = sensor_name.split()[0][:-1]
            if sensor_group in self.group_plots:
                if sensor_name in self.group_plot_data[sensor_group]:
                    self.group_plot_data[sensor_group].pop(sensor_name, None)

            # Retirer la surbrillance du capteur
            self.unhighlight_sensor(sensor_name)

    def highlight_sensor(self, sensor_name):
        # Mettre en surbrillance le capteur sélectionné
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("lightblue")))
                    self.highlighted_sensors.add(sensor_name)

    def unhighlight_sensor(self, sensor_name):
        # Retirer la surbrillance du capteur
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                if sensor_item.text(0).startswith(sensor_name):
                    sensor_item.setBackground(0, QBrush(QColor("white")))
                    self.highlighted_sensors.discard(sensor_name)

    def update_data(self):
        # Mettre à jour les données des graphiques en temps réel
        if self.recording:
            packet = self.simulator.generate_packet()

            # Enregistrer les données dans self.recorded_data
            for i in range(8):
                self.recorded_data["EMG"][i].append(packet["EMG"][i])
                self.recorded_data["pMMG"][i].append(packet["pMMG"][i])

            for i in range(6):
                self.recorded_data["IMU"][i].append(packet["IMU"][i])

            # Mettre à jour le modèle 3D avec les données IMU
            if "IMU" in packet:
                for i, quaternion in enumerate(packet["IMU"]):
                    imu_id = i + 1  # IMU IDs start at 1
                    if imu_id <= 6:  # Nous n'utilisons que 6 IMUs dans notre mapping
                        self.model_3d_widget.apply_imu_data(imu_id, quaternion)

            for sensor_name, plot_widget in self.plots.items():
                if sensor_name.startswith("EMG"):
                    index = int(sensor_name[3]) - 1
                    self.plot_data[sensor_name] = np.roll(self.plot_data[sensor_name], -1)
                    self.plot_data[sensor_name][-1] = packet["EMG"][index]
                    plot_widget.plot(self.plot_data[sensor_name], clear=True, pen=pg.mkPen('b', width=2))
                elif sensor_name.startswith("pMMG"):
                    index = int(sensor_name[4]) - 1
                    self.plot_data[sensor_name] = np.roll(self.plot_data[sensor_name], -1)
                    self.plot_data[sensor_name][-1] = packet["pMMG"][index]
                    plot_widget.plot(self.plot_data[sensor_name], clear=True, pen=pg.mkPen('b', width=2))
                elif sensor_name.startswith("IMU"):
                    index = int(sensor_name[3]) - 1
                    quaternion = packet["IMU"][index]
                    plot_widget.clear()
                    for i, axis in enumerate(['w', 'x', 'y', 'z']):
                        self.plot_data[f"{sensor_name}_{axis}"] = np.roll(self.plot_data.get(f"{sensor_name}_{axis}", np.zeros(100)), -1)
                        self.plot_data[f"{sensor_name}_{axis}"][-1] = quaternion[i]
                        plot_widget.plot(self.plot_data[f"{sensor_name}_{axis}"], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)

                    plot_widget.addLegend()

            for sensor_group, plot_widget in self.group_plots.items():
                plot_widget.clear()
                for sensor_name, data in self.group_plot_data[sensor_group].items():
                    if sensor_name.startswith("IMU"):
                        index = int(sensor_name[3]) - 1
                        quaternion = packet["IMU"][index]
                        for i, axis in enumerate(['w', 'x', 'y', 'z']):
                            self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"] = np.roll(self.group_plot_data[sensor_group].get(f"{sensor_name}_{axis}", np.zeros(100)), -1)
                            self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"][-1] = quaternion[i]
                            plot_widget.plot(self.group_plot_data[sensor_group][f"{sensor_name}_{axis}"], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=f"{sensor_name}_{axis}")
                    else:
                        # Extraire le numéro du capteur en ignorant les "matched parts"
                        sensor_num = int(''.join(filter(str.isdigit, sensor_name)))
                        if sensor_name.startswith("EMG"):
                            index = sensor_num - 1
                            self.group_plot_data[sensor_group][sensor_name] = np.roll(self.group_plot_data[sensor_group][sensor_name], -1)
                            self.group_plot_data[sensor_group][sensor_name][-1] = packet["EMG"][index]
                        elif sensor_name.startswith("pMMG"):
                            index = sensor_num - 1
                            self.group_plot_data[sensor_group][sensor_name] = np.roll(self.group_plot_data[sensor_group][sensor_name], -1)
                            self.group_plot_data[sensor_group][sensor_name][-1] = packet["pMMG"][index]

                        plot_widget.plot(self.group_plot_data[sensor_group][sensor_name], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'k', 'w'][sensor_num - 1], width=2), name=sensor_name)

                plot_widget.addLegend()

    def on_display_mode_changed(self):
        if hasattr(self, 'recording') and self.recording:
            QMessageBox.warning(self, 'Warning', "You cannot change the display mode once recording has started.")
            # Revenir au mode précédent
            if self.single_sensor_mode.isChecked():
                self.group_sensor_mode.setChecked(True)
            else:
                self.single_sensor_mode.setChecked(True)
        else:
            reply = QMessageBox.question(self, 'Change Mode',
                                         "Are you sure you want to change the display mode?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.update_display_mode()
            else:
                # Revenir au mode précédent
                if self.single_sensor_mode.isChecked():
                    self.group_sensor_mode.setChecked(True)
                else:
                    self.single_sensor_mode.setChecked(True)

    def update_display_mode(self):
        # Effacer les graphiques actuels
        for plot_widget in self.plots.values():
            plot_widget.setParent(None)
            plot_widget.deleteLater()
        self.plots.clear()
        self.plot_data.clear()

        for plot_widget in self.group_plots.values():
            plot_widget.setParent(None)
            plot_widget.deleteLater()
        self.group_plots.clear()
        self.group_plot_data.clear()

        # Reconstruire les graphiques en fonction du mode sélectionné
        if self.group_sensor_mode.isChecked():
            self.create_group_plots()
        else:
            # Re-sélectionner les capteurs précédemment sélectionnés
            for sensor_name in self.highlighted_sensors:
                self.plot_sensor_data(sensor_name)

    def start_recording(self):
        self.recording = True
        self.recorded_data = {"EMG": [[] for _ in range(8)], "IMU": [[] for _ in range(6)], "pMMG": [[] for _ in range(8)]}
        self.record_button.setText("Record Stop")

    def stop_recording(self):
        self.recording = False
        self.record_button.setText("Record Start")
        self.Clear_plots.setEnabled(True)
        self.Refresh_the_connected_system.setEnabled(True)
        self.Request_h5_file_transfer.setEnabled(True)
        self.show_recorded_data()

    def show_recorded_data(self):
        # Afficher les données enregistrées sur les graphiques existants
        if not any(self.recorded_data["EMG"][0]) and not any(self.recorded_data["IMU"][0]) and not any(self.recorded_data["pMMG"][0]):
            QMessageBox.warning(self, 'Warning', "No data recorded.")
            return

        # Arrêter la génération de données
        self.timer.stop()

        # Afficher les données enregistrées sur les graphiques existants
        for sensor_name, plot_widget in self.plots.items():
            if sensor_name.startswith("EMG"):
                index = int(sensor_name[3]) - 1
                plot_widget.plot(self.recorded_data["EMG"][index], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("pMMG"):
                index = int(sensor_name[4]) - 1
                plot_widget.plot(self.recorded_data["pMMG"][index], clear=True, pen=pg.mkPen('b', width=2))
            elif sensor_name.startswith("IMU"):
                index = int(sensor_name[3]) - 1
                quaternion = self.recorded_data["IMU"][index]
                plot_widget.clear()
                for i, axis in enumerate(['w', 'x', 'y', 'z']):
                    plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=axis)

                plot_widget.addLegend()

        for sensor_group, plot_widget in self.group_plots.items():
            plot_widget.clear()
            for sensor_name, data in self.group_plot_data[sensor_group].items():
                if sensor_name.startswith("IMU"):
                    index = int(sensor_name[3]) - 1
                    quaternion = self.recorded_data["IMU"][index]
                    for i, axis in enumerate(['w', 'x', 'y', 'z']):
                        plot_widget.plot([q[i] for q in quaternion], pen=pg.mkPen(['r', 'g', 'b', 'y'][i], width=2), name=f"{sensor_name}_{axis}")
                else:
                    # Extraire le numéro du capteur en ignorant les "matched parts"
                    sensor_num = int(''.join(filter(str.isdigit, sensor_name)))
                    if sensor_name.startswith("EMG"):
                        index = sensor_num - 1
                        plot_widget.plot(self.recorded_data["EMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'k', 'w'][sensor_num - 1], width=2), name=sensor_name)
                    elif sensor_name.startswith("pMMG"):
                        index = sensor_num - 1
                        plot_widget.plot(self.recorded_data["pMMG"][index], pen=pg.mkPen(['r', 'g', 'b', 'y', 'c', 'm', 'k', 'w'][sensor_num - 1], width=2), name=sensor_name)

            plot_widget.addLegend()

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
            self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                text-align: center;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #43a047;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
            """)
        else:
            self.connect_sensors()
            self.start_recording()
            # Style rouge pour le bouton d'arrêt d'enregistrement
            self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                text-align: center;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
            """)

    def toggle_animation(self):
        """Toggle stickman walking animation."""
        is_walking = self.model_3d_widget.toggle_animation()
        self.animate_button.setText("Stop Animation" if is_walking else "Start Animation")

    def reset_model_view(self):
        """Réinitialiser la vue avec animation et retour visuel"""
        # Obtenir les rotations actuelles
        start_rotation = (self.model_3d_widget.model_viewer.rotation_x,
                        self.model_3d_widget.model_viewer.rotation_y,
                        self.model_3d_widget.model_viewer.rotation_z)

        # Créer un timer pour animer le retour à zéro
        steps = 10
        timer = QTimer(self)
        step_counter = [0]  # Utiliser une liste pour pouvoir la modifier dans la closure

        def animation_step():
            step_counter[0] += 1
            progress = step_counter[0] / steps

            # Interpolation linéaire vers zéro
            x = start_rotation[0] * (1 - progress)
            y = start_rotation[1] * (1 - progress)
            z = start_rotation[2] * (1 - progress)

            self.model_3d_widget.model_viewer.rotation_x = x
            self.model_3d_widget.model_viewer.rotation_y = y
            self.model_3d_widget.model_viewer.rotation_z = z
            self.model_3d_widget.model_viewer.update()

            if step_counter[0] >= steps:
                timer.stop()

        timer.timeout.connect(animation_step)
        timer.start(20)  # 50 FPS

    def open_sensor_mapping_dialog(self):
        """Ouvrir le dialogue de configuration des capteurs"""
        # Récupérer les mappages actuels
        current_mappings = {
            'EMG': {},  # TODO: Stocker les mappages EMG
            'IMU': self.model_3d_widget.get_current_mappings(),
            'pMMG': {}  # TODO: Stocker les mappages pMMG
        }

        dialog = SensorMappingDialog(None, current_mappings)
        dialog.exec_()

    def update_sensor_mappings(self, emg_mappings, imu_mappings, pmmg_mappings):
        """Mettre à jour les mappages de capteurs après fermeture du dialogue"""
        # Mettre à jour les mappages IMU
        for imu_id, body_part in imu_mappings.items():
            self.model_3d_widget.map_imu_to_body_part(imu_id, body_part)

        # Mettre à jour les mappages EMG et pMMG
        self.model_3d_widget.model_viewer.set_emg_mapping(emg_mappings)
        self.model_3d_widget.model_viewer.set_pmmg_mapping(pmmg_mappings)

        # Stocker les mappages localement
        self.emg_mappings = emg_mappings
        self.pmmg_mappings = pmmg_mappings

    def _convert_model_part_to_ui(self, model_part):
        """Convertit les noms des parties du modèle 3D vers des noms plus lisibles pour l'UI."""
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

    def load_external_model(self):
        """Charger un modèle 3D externe"""
        from PyQt5.QtWidgets import QFileDialog

        # Ouvrir un dialogue de sélection de fichier
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load 3D Model", "",
            "3D Model Files (*.obj *.stl *.3ds);;All Files (*)"
        )

        if file_path:
            success = self.model_3d_widget.load_external_model(file_path)
            if not success:
                QMessageBox.warning(self, "Error", f"Failed to load model from {file_path}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = DashboardApp()
    dashboard.show()
    sys.exit(app.exec_())
