import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from exo_monitoring_gui.utils.hdf5_utils import load_hdf5_data

import numpy as np
import h5py
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QScrollArea, QGraphicsItem, QTextEdit, QGraphicsView, QGraphicsScene, QGraphicsRectItem
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QColor, QBrush, QPen, QPainter, QWheelEvent

class ZoomBar(QGraphicsView):
    def __init__(self, update_zoom_callback):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        
        # Taille totale de la barre de zoom (représente toutes les données)
        self.total_width = 800
        self.bar_height = 20
        
        # Rectangle de fond (représente la totalité des données)
        self.background_rect = QGraphicsRectItem(0, 0, self.total_width, self.bar_height)
        self.background_rect.setPen(QPen(Qt.black))
        self.background_rect.setBrush(QBrush(QColor(220, 220, 220)))
        self.scene.addItem(self.background_rect)
        
        # Rectangle de zoom (représente la partie visible)
        self.zoom_rect = QGraphicsRectItem(0, 0, self.total_width, self.bar_height)
        self.zoom_rect.setPen(QPen(Qt.darkBlue, 2))
        self.zoom_rect.setBrush(QBrush(QColor(100, 150, 255, 150)))
        self.zoom_rect.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.scene.addItem(self.zoom_rect)
        
        self.update_zoom_callback = update_zoom_callback
        self.setSceneRect(QRectF(0, 0, self.total_width, self.bar_height))
        
        # Variables pour gérer le zoom et la position
        self.data_length = 1000  # Longueur totale des données (sera mise à jour)
        self.zoom_level = 1.0    # Niveau de zoom (1.0 = pas de zoom)
        self.position_ratio = 0.0 # Position relative (0.0 à 1.0)
        
        # Empêcher le mouvement vertical
        self.last_mouse_pos = None

    def set_data_length(self, length):
        """Définir la longueur totale des données"""
        self.data_length = length
        self.update_zoom_rect()

    def wheelEvent(self, event: QWheelEvent):
        # Facteurs de zoom
        zoom_in_factor = 1.2
        zoom_out_factor = 1 / zoom_in_factor
        
        # Calculer le nouveau niveau de zoom
        if event.angleDelta().y() > 0:
            new_zoom = self.zoom_level * zoom_in_factor
        else:
            new_zoom = self.zoom_level * zoom_out_factor
        
        # Limiter le niveau de zoom (minimum 1.0, maximum 20.0)
        new_zoom = max(1.0, min(new_zoom, 20.0))
        
        # Calculer la position de la souris relative à la barre
        mouse_pos = self.mapToScene(event.pos())
        mouse_ratio = mouse_pos.x() / self.total_width
        
        # Ajuster la position pour centrer le zoom sur la souris
        if new_zoom > self.zoom_level:  # Zoom in
            # Calculer la nouvelle position pour centrer sur la souris
            visible_width = 1.0 / new_zoom
            new_position = mouse_ratio - visible_width / 2
        else:  # Zoom out
            # Maintenir la position relative
            current_center = self.position_ratio + (1.0 / self.zoom_level) / 2
            visible_width = 1.0 / new_zoom
            new_position = current_center - visible_width / 2
        
        # Limiter la position
        visible_width = 1.0 / new_zoom
        new_position = max(0.0, min(new_position, 1.0 - visible_width))
        
        self.zoom_level = new_zoom
        self.position_ratio = new_position
        self.update_zoom_rect()
        self.update_graphs()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is not None:
            # Calculer le déplacement horizontal uniquement
            delta_x = event.pos().x() - self.last_mouse_pos.x()
            
            # Convertir le déplacement en pixels en ratio
            delta_ratio = delta_x / self.total_width
            
            # Mettre à jour la position
            new_position = self.position_ratio + delta_ratio
            
            # Limiter la position
            visible_width = 1.0 / self.zoom_level
            new_position = max(0.0, min(new_position, 1.0 - visible_width))
            
            self.position_ratio = new_position
            self.update_zoom_rect()
            self.update_graphs()
            
            self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def update_zoom_rect(self):
        """Mettre à jour la taille et la position du rectangle de zoom"""
        visible_width = 1.0 / self.zoom_level
        rect_width = visible_width * self.total_width
        rect_x = self.position_ratio * self.total_width
        
        self.zoom_rect.setRect(rect_x, 0, rect_width, self.bar_height)

    def update_graphs(self):
        """Mettre à jour les graphiques en fonction du zoom et de la position"""
        visible_width = 1.0 / self.zoom_level
        
        # Calculer les indices de début et de fin
        start_index = int(self.position_ratio * self.data_length)
        end_index = int((self.position_ratio + visible_width) * self.data_length)
        
        # S'assurer que les indices sont valides
        start_index = max(0, start_index)
        end_index = min(self.data_length, end_index)
        
        self.update_zoom_callback(start_index, end_index)

    def reset_zoom(self):
        """Réinitialiser le zoom à la vue complète"""
        self.zoom_level = 1.0
        self.position_ratio = 0.0
        self.update_zoom_rect()
        self.update_graphs()


class Review(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logiciel de Surveillance des Données")
        self.resize(1600, 900)
        self.setMinimumSize(1400, 800)
        self.loaded_data = {}
        self.time_axis = None
        self.data = load_hdf5_data('C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\data6.h5')
        print(f"Données chargées : {self.data}")
        self.setStyleSheet(self.get_stylesheet())
        self.init_ui()

    def get_stylesheet(self):
        return """
        QMainWindow, QDialog {
            background-color: #f5f5f5;
        }
        QTreeWidget, QTableWidget {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            background: white;
        }
        QScrollArea {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            background: white;
        }
        """

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.build_header(main_layout)
        self.build_main_content(main_layout)
        self.build_footer(main_layout)
        self.build_text_areas(main_layout)

    def build_header(self, layout):
        header = QHBoxLayout()
        header.addWidget(QLabel("Systèmes Connectés"), stretch=1)
        header.addWidget(QLabel("Zone Graphique / Visuelle"), stretch=2)
        header.addWidget(QLabel("Perspective 3D"), stretch=1)
        layout.addLayout(header)

    def build_main_content(self, layout):
        content_layout = QHBoxLayout()
        layout.addLayout(content_layout, stretch=1)

        left_panel = self.build_left_panel()
        middle_panel = self.build_middle_panel()
        right_panel = self.build_right_panel()

        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(middle_panel, stretch=4)
        content_layout.addLayout(right_panel, stretch=2)

    def build_left_panel(self):
        layout = QVBoxLayout()
        self.connected_systems = QTreeWidget()
        self.connected_systems.setHeaderHidden(True)
        self.connected_systems.itemClicked.connect(self.on_sensor_clickedd)
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

        for group_name, count in [("IMU Data", 6), ("EMG Data", 8), ("pMMG Data", 8)]:
            group_item = QTreeWidgetItem([group_name])
            for i in range(1, count + 1):
                sensor = QTreeWidgetItem([f"{group_name[:-5]}{i}"])
                sensor.setForeground(0, QBrush(QColor("gray")))
                group_item.addChild(sensor)
            group_item.setExpanded(True)
            self.connected_systems.addTopLevelItem(group_item)

        layout.addWidget(self.connected_systems)

        # Ajoutez un bouton de test pour charger le fichier HDF5
        load_button = QPushButton("Charger fichier HDF5")
        load_button.clicked.connect(
            lambda: self.load_hdf5_and_populate_tree("C:\\Users\\samio\\Documents\\BUT\\BUT2\\stage\\travail\\Monitoring_GUI\\data6.h5")
        )
        layout.addWidget(load_button)

        return layout

    def create_plot_in_middle_panel(self, data, plot_name=None):
        import pyqtgraph as pg
        # Vérifie si le plot existe déjà (par son nom dans le titre caché)
        plot_titles = [self.middle_layout.itemAt(i).widget().titleLabel.text() for i in range(self.middle_layout.count()) if hasattr(self.middle_layout.itemAt(i).widget(), 'titleLabel')]
        plot_title = plot_name if plot_name else "Données du Capteur"
        if plot_title in plot_titles:
            # Si déjà affiché, on le retire
            for i in range(self.middle_layout.count()):
                widget = self.middle_layout.itemAt(i).widget()
                if hasattr(widget, 'titleLabel') and widget.titleLabel.text() == plot_title:
                    widget.setParent(None)
                    widget.deleteLater()
                    break
            # Recalcule la taille des autres plots
            count = self.middle_layout.count()
            for i in range(count):
                item = self.middle_layout.itemAt(i)
                widget = item.widget()
                if widget:
                    widget.setContentsMargins(0, 0, 0, 0)
                    widget.setMinimumHeight(200)
                    widget.setMaximumHeight(200)
            self.middle_placeholder.setContentsMargins(0, 0, 0, 0)
            self.middle_layout.setSpacing(0)
            self.middle_placeholder.setMinimumHeight(count * 200)
            return

        plot_widget = pg.PlotWidget()
        plot_widget.full_data = data
        plot_widget.plot(data, pen=pg.mkPen(color='b', width=2))
        plot_widget.setLabel('left', 'Valeur')
        plot_widget.setLabel('bottom', 'Index')
        if plot_name:
            plot_widget.setTitle(f"<span style='font-size:24pt; font-weight:bold'>{plot_name}</span>")
        else:
            plot_widget.setTitle("Données du Capteur")
        plot_widget.titleLabel = QLabel(plot_title)
        plot_widget.titleLabel.setVisible(False)
        self.middle_layout.addWidget(plot_widget)

        # Mettre à jour la longueur des données dans la zoom bar
        if len(data) > 0:
            self.zoom_bar.set_data_length(len(data))

        # Ajustez la taille des graphiques pour éviter la barre de défilement
        count = self.middle_layout.count()
        for i in range(count):
            item = self.middle_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setContentsMargins(0, 0, 0, 0)
                widget.setMinimumHeight(200)
                widget.setMaximumHeight(200)
        self.middle_placeholder.setContentsMargins(0, 0, 0, 0)
        self.middle_layout.setSpacing(0)
        self.middle_placeholder.setMinimumHeight(count * 200)

    def build_middle_panel(self):
        layout = QVBoxLayout()
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout(self.middle_placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.middle_placeholder)

        # Ajoutez la barre de zoom interactive
        self.zoom_bar = ZoomBar(self.update_zoom)
        self.zoom_bar.setFixedHeight(30)

        # Ajoutez un bouton pour le dézoom complet
        self.zoom_out_button = QPushButton("Dézoom Complet")
        self.zoom_out_button.clicked.connect(self.reset_zoom)

        layout.addWidget(scroll)
        layout.addWidget(self.zoom_bar)
        layout.addWidget(self.zoom_out_button)
        return layout

    def reset_zoom(self):
        # Réinitialiser la barre de zoom
        self.zoom_bar.reset_zoom()

    def update_zoom(self, start_index, end_index):
        """Mettre à jour la vue des graphiques avec les nouveaux indices"""
        for i in range(self.middle_layout.count()):
            widget = self.middle_layout.itemAt(i).widget()
            if hasattr(widget, 'getViewBox') and hasattr(widget, 'full_data'):
                view_box = widget.getViewBox()
                # Utiliser les indices pour définir la plage de vue
                view_box.setRange(xRange=(start_index, end_index))

    def build_right_panel(self):
        layout = QVBoxLayout()

        label = QLabel("Perspective 3D")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(label)

        self.model_3d_widget = QLabel("Placeholder du Modèle 3D")
        self.model_3d_widget.setAlignment(Qt.AlignCenter)
        self.model_3d_widget.setStyleSheet("background-color: #e0e0e0; border: 1px solid #ccc;")
        layout.addWidget(self.model_3d_widget, stretch=3)

        self.animate_button = QPushButton("Démarrer l'Animation")
        layout.addWidget(self.animate_button)

        self.reset_view_button = QPushButton("Réinitialiser la Vue")
        layout.addWidget(self.reset_view_button)

        return layout

    def build_footer(self, layout):
        footer = QHBoxLayout()

        self.connect_button = QPushButton("Connecter")
        footer.addWidget(self.connect_button)

        self.record_button = QPushButton("Démarrer l'Enregistrement")
        footer.addWidget(self.record_button)

        layout.addLayout(footer)

    def build_text_areas(self, layout):
        box_layout = QHBoxLayout()

        self.received_data_text = QTextEdit()
        self.received_data_text.setPlaceholderText("Données Reçues")
        self.received_data_text.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.received_data_text.setFixedHeight(100)
        box_layout.addWidget(self.received_data_text)

        self.experiment_protocol_text = QTextEdit()
        self.experiment_protocol_text.setPlaceholderText("Protocole Expérimental")
        self.experiment_protocol_text.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.experiment_protocol_text.setFixedHeight(100)
        box_layout.addWidget(self.experiment_protocol_text)

        layout.addLayout(box_layout)

    def on_sensor_clickedd(self, item, column):
        if item.data(0, Qt.UserRole) == "disabled":
            self.rienb()
            return
        sensor_name = item.text(0)
        print(f"Capteur cliqué : {sensor_name}")
        match sensor_name:
            case "EMGL1":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGL1"][5:], plot_name="EMGL1")
            case "EMGL2":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGL2"], plot_name="EMGL2")
            case "EMGL3":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGL3"], plot_name="EMGL3")
            case "EMGL4":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGL4"], plot_name="EMGL4")
            case "EMGR1":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGR1"], plot_name="EMGR1")
            case "EMGR2":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGR2"], plot_name="EMGR2")
            case "EMGR3":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGR3"], plot_name="EMGR3")
            case "EMGR4":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["EMGR4"], plot_name="EMGR4")
            case "IMU1":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU1"], plot_name="IMU1")
            case "IMU2":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU2"], plot_name="IMU2")
            case "IMU3":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU3"], plot_name="IMU3")
            case "IMU4":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU4"], plot_name="IMU4")
            case "IMU5":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU5"], plot_name="IMU5")
            case "IMU6":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["IMU6"], plot_name="IMU6")
            case "pMMGL1":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["pMMGL1"], plot_name="pMMGL1")
            case "pMMGL2":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["pMMGL2"], plot_name="pMMGL2")
            case "pMMGL3":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["pMMGL3"], plot_name="pMMGL3")
            case "pMMGL4":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["pMMGL4"], plot_name="pMMGL4")
            case "pMMGL5":
                self.create_plot_in_middle_panel(self.data["loaded_data"]["pMMGL5"], plot_name="pMMGL5")

    def load_emgL_datasets(self, file_path, group_name, dataset_name):
        emgL_data = {}
        with h5py.File(file_path, "r") as f:
            emg_group = f[f"Sensor/{group_name}"]
            for name in emg_group:
                if name.startswith(dataset_name):
                    emgL_data[name] = emg_group[name][:]
        return emgL_data

    def load_hdf5_and_populate_tree(self, file_path):
        self.connected_systems.clear()

        if hasattr(self, 'middle_layout'):
            while self.middle_layout.count():
                item = self.middle_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()

        self.loaded_data.clear()
        data_structure = {}
        time_length = None

        with h5py.File(file_path, "r") as f:
            def visitor(name, obj):
                nonlocal time_length
                if isinstance(obj, h5py.Dataset):
                    parts = name.strip("/").split("/")
                    if len(parts) >= 2:
                        group_name, dataset_name = parts[-2], parts[-1]
                        group_upper = group_name.upper()
                        dataset_upper = dataset_name.upper()

                        if group_upper == "TIME":
                            time_length = len(obj[:])
                            return
                        if group_upper == "LABEL":
                            return

                        if group_upper not in data_structure:
                            data_structure[group_upper] = []
                        data_structure[group_upper].append(dataset_upper)
                        data = obj[:]
                        if data.size > 0:
                            self.loaded_data[dataset_upper] = data

            f.visititems(visitor)

        if time_length is not None:
            self.time_axis = np.arange(time_length) * 0.040
        else:
            any_key = next(iter(self.loaded_data), None)
            if any_key:
                length = len(self.loaded_data[any_key])
                self.time_axis = np.arange(length) * 0.040
            else:
                self.time_axis = []

        for group_name, dataset_list in data_structure.items():
            group_item = QTreeWidgetItem([f"{group_name} Data"])
            self.connected_systems.addTopLevelItem(group_item)

            for dataset_name in dataset_list:
                sensor_item = QTreeWidgetItem([dataset_name])
                if dataset_name in self.loaded_data:
                    sensor_item.setForeground(0, QBrush(QColor("green")))
                    sensor_item.setFlags(sensor_item.flags() | Qt.ItemIsEnabled)
                else:
                    sensor_item.setForeground(0, QBrush(QColor("gray")))
                    sensor_item.setFlags(sensor_item.flags() | Qt.ItemIsEnabled)
                    sensor_item.setFlags(sensor_item.flags() & ~Qt.ItemIsSelectable)
                    sensor_item.setData(0, Qt.UserRole, "disabled")

                group_item.addChild(sensor_item)

            group_item.setExpanded(True)

    def rien(self):
        pass

    def rienb(self):
        pass

if __name__ == '__main__':
    if QApplication.instance() is None:
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()

    dashboard = Review()
    dashboard.show()
    sys.exit(app.exec_())