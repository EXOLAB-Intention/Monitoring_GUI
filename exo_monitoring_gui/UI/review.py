import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,  QMessageBox, QAction, QGroupBox, QTextEdit, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush
import pyqtgraph as pg
from utils.hdf5_utils import extract_group_data
class Review(QMainWindow):
    def __init__(self, parent=None, filename=None):
        super().__init__(parent)
        self.filename = filename   # ✅ défini avant toute utilisation
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1400, 800)
        self.setStyleSheet("background-color: white; color: black;")
        self._create_menubar()
        self.init_ui()             # ✅ maintenant c’est bon


    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Titles
        print(self.filename)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Connected Systems"), stretch=1)
        title_layout.addWidget(QLabel("2D Plots"), stretch=2)
        title_layout.addWidget(QLabel("3D"), stretch=1)
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
        """)
        self.connected_systems.setVisible(True)
        self.connected_systems.itemClicked.connect(self.on_sensor_clicked)

        # Organisation des capteurs par sous-groupes
        sensors = ["EMG", "IMU", "pHMG"]
        for sensor_group in sensors:
            group_item = QTreeWidgetItem([f"{sensor_group} Data"])
            self.connected_systems.addTopLevelItem(group_item)
            for i in range(1, 9):
                sensor_item = QTreeWidgetItem([f"{sensor_group}{i:02d}"])
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté
                sensor_item.setHidden(False)  # Visible au départ
                group_item.addChild(sensor_item)

        left_panel = QVBoxLayout()
        left_panel.addWidget(self.connected_systems)

        # Graphics / Visual Zone (centre)
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout()
        self.middle_placeholder.setLayout(self.middle_layout)

        # Ajouter une QScrollArea pour les graphiques
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.middle_placeholder)
        self.scroll_area.setVisible(False)  # Masquer la barre de défilement au départ

        middle_panel = QVBoxLayout()
        middle_panel.addWidget(self.scroll_area)

        # 3D Perspective (droite)
        right_panel = QVBoxLayout()
        label_3d = QLabel("3D Perspective")
        label_3d.setAlignment(Qt.AlignCenter)
        label_3d.setStyleSheet("background-color: #f0f0f0; padding: 30px; border: 1px solid #ccc;")
        right_panel.addWidget(label_3d)

        # Ajout des panneaux gauche / centre / droite
        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(middle_panel, stretch=2)
        content_layout.addLayout(right_panel, stretch=1)

        # Footer
        footer_layout = QHBoxLayout()

        # Connect Button
        self.connect_button = QPushButton("CONNECT")
        self.connect_button.setStyleSheet("font-size: 14px; padding: 8px 20px; background-color: lightblue;")
        self.connect_button.clicked.connect(self.show_sensors)

        # Record Start Button
        self.record_button = QPushButton("RECORD START")
        self.record_button.setStyleSheet("font-size: 14px; padding: 8px 20px; background-color: lightgreen;")
        self.record_button.clicked.connect(self.show_sensors)

        footer_layout.addWidget(self.connect_button)
        footer_layout.addWidget(self.record_button)

        # Received Data Section
        received_data_group = QGroupBox("Received Data")
        received_data_layout = QVBoxLayout()
        self.received_data_text = QTextEdit()
        self.received_data_text.setPlainText("0 Taeyeon Kim\n- 250503_trial_001_TaeyeonKim.h5")
        received_data_layout.addWidget(self.received_data_text)
        received_data_group.setLayout(received_data_layout)
        footer_layout.addWidget(received_data_group)

        # Experiment Protocol Section
        experiment_protocol_group = QGroupBox("Experiment Protocol")
        experiment_protocol_layout = QVBoxLayout()
        self.experiment_protocol_text = QTextEdit()
        self.experiment_protocol_text.setPlainText("Initially standing\nStarts to walk, with button b click\nFlat ground, free speed")
        experiment_protocol_layout.addWidget(self.experiment_protocol_text)
        experiment_protocol_group.setLayout(experiment_protocol_layout)
        footer_layout.addWidget(experiment_protocol_group)

        main_layout.addLayout(footer_layout)

        # Initialiser les graphiques
        self.plots = {}
        self.plot_data = {}

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

    def exit(self):
        QApplication.quit()

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

    def return_to_main(self):
        """Return to the main window"""
        self.close()
        from UI.main_window import MainApp
        self.main_app = MainApp()
        self.main_app.show()

    def _create_menubar(self):
        """Create the application menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('&File')

        # File menu actions
        return_main_page = self._create_action("&Return to main page", self.return_to_main, "Ctrl+P",
                                                  tip="Exit without saving")
        exit_button = self._create_action("&Exit", self.exit, "Ctrl+Shift+Q",
                                                  tip="Exit without saving")

        file_menu.addAction(return_main_page)
        file_menu.addAction(exit_button)

        # Help menu
        help_menu = menubar.addMenu('&Help')
        # Help menu actions
        about_action = self._create_action("&About", self.show_about_dialog,
                                         tip="About the application")

        help_menu.addAction(about_action)

    def show_sensors(self):
        # Afficher les capteurs et les connecter
        for i in range(self.connected_systems.topLevelItemCount()):
            group_item = self.connected_systems.topLevelItem(i)
            for j in range(group_item.childCount()):
                sensor_item = group_item.child(j)
                sensor_item.setHidden(False)
                sensor_item.setForeground(0, QBrush(QColor("green")))  # Vert pour connecté

    def on_sensor_clicked(self, item, column):
        sensor_name = item.text(0)  # Extraire le nom du capteur
        self.plot_sensor_data(sensor_name)

    def plot_sensor_data(self, sensor_name):
        # Exemple de données à tracer (ordonnées)
        print(sensor_name)
        match sensor_name:
            case "EMG01":
                info = extract_group_data(self.filename, "EMG")["emgL1"]
            case "EMG02":
                info =  extract_group_data(self.filename, "EMG")["emgL2"]
            case "EMG03":
                info = extract_group_data(self.filename, "EMG")["emgL3"]
            case "EMG04":
                info = extract_group_data(self.filename, "EMG")["emgL4"]
            case "EMG05":
                info = extract_group_data(self.filename, "EMG")["emgR1"]
            case "EMG06":
                info = extract_group_data(self.filename, "EMG")["emgR2"]
            case "EMG07":
                info = extract_group_data(self.filename, "EMG")["emgR3"]
            case "EMG08":
                info = extract_group_data(self.filename, "EMG")["emgR4"]
            case "IMU01":
                info = extract_group_data(self.filename, "IMU")["imu1"]
            case "IMU02":
                info = extract_group_data(self.filename, "IMU")["imu2"]
            case "IMU03":
                info = extract_group_data(self.filename, "IMU")["imu3"]
            case "IMU04":
                info = extract_group_data(self.filename, "IMU")["imu4"]
            case "IMU05":
                info = extract_group_data(self.filename, "IMU")["imu5"]
            case "IMU06":
                info = extract_group_data(self.filename, "IMU")["imu6"]
            case _:
                raise ValueError(f"Capteur '{sensor_name}' non reconnu.")


        # Axe des abscisses : espacement de 10
        x_values = np.arange(0, len(info) * 10, 10)

        # Créer un nouveau graphique pour le capteur sélectionné
        plot_widget = pg.PlotWidget(title=sensor_name)
        plot_widget.setBackground('#1e1e1e')
        plot_widget.getAxis('left').setTextPen('white')
        plot_widget.getAxis('bottom').setTextPen('white')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setTitle(sensor_name, color='white', size='14pt')

        # Définir une taille minimale pour le graphique
        plot_widget.setMinimumHeight(150)

        # Ajouter le graphique à la section "2D Plots"
        self.middle_layout.addWidget(plot_widget)

        # Stocker le graphique et les données
        self.plots[sensor_name] = plot_widget
        self.plot_data[sensor_name] = info

        # Tracer les données avec l'espacement sur l'axe des abscisses
        plot_widget.plot(x_values, self.plot_data[sensor_name], clear=True, pen=pg.mkPen('b', width=2))

        # Ajuster automatiquement l'échelle
        plot_widget.enableAutoRange(axis='xy', enable=True)

        # Affichage du scroll si au moins un graphique est présent
        self.scroll_area.setVisible(len(self.plots) > 0)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = Review()
    dashboard.show()
    sys.exit(app.exec_())
