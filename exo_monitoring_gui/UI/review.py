import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from exo_monitoring_gui.utils.hdf5_utils import load_hdf5_data, load_metadata

import numpy as np
import h5py
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QScrollArea, QGraphicsItem, QTextEdit, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QColorDialog
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QColor, QBrush, QPen, QPainter, QWheelEvent, QTextCharFormat, QFont


class ZoomBar(QGraphicsView):
    def __init__(self, update_zoom_callback):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        # Total size of the zoom bar (represents all data)
        self.total_width = 800
        self.bar_height = 20

        # Background rectangle (represents all data)
        self.background_rect = QGraphicsRectItem(0, 0, self.total_width, self.bar_height)
        self.background_rect.setPen(QPen(Qt.black))
        self.background_rect.setBrush(QBrush(QColor(220, 220, 220)))
        self.scene.addItem(self.background_rect)

        # Zoom rectangle (represents the visible part)
        self.zoom_rect = QGraphicsRectItem(0, 0, self.total_width, self.bar_height)
        self.zoom_rect.setPen(QPen(Qt.darkBlue, 2))
        self.zoom_rect.setBrush(QBrush(QColor(100, 150, 255, 150)))
        self.zoom_rect.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.scene.addItem(self.zoom_rect)

        self.update_zoom_callback = update_zoom_callback
        self.setSceneRect(QRectF(0, 0, self.total_width, self.bar_height))

        # Variables to manage zoom and position
        self.data_length = 1000  # Total length of data (will be updated)
        self.zoom_level = 1.0    # Zoom level (1.0 = no zoom)
        self.position_ratio = 0.0 # Relative position (0.0 to 1.0)

        # Prevent vertical movement
        self.last_mouse_pos = None

    def set_data_length(self, length):
        """Set the total length of the data"""
        self.data_length = length
        self.update_zoom_rect()

    def wheelEvent(self, event: QWheelEvent):
        # Zoom factors
        zoom_in_factor = 1.2
        zoom_out_factor = 1 / zoom_in_factor

        # Calculate the new zoom level
        if event.angleDelta().y() > 0:
            new_zoom = self.zoom_level * zoom_in_factor
        else:
            new_zoom = self.zoom_level * zoom_out_factor

        # Limit the zoom level (minimum 1.0, maximum 20.0)
        new_zoom = max(1.0, min(new_zoom, 20.0))

        # Calculate the mouse position relative to the bar
        mouse_pos = self.mapToScene(event.pos())
        mouse_ratio = mouse_pos.x() / self.total_width

        # Adjust the position to center the zoom on the mouse
        if new_zoom > self.zoom_level:  # Zoom in
            # Calculate the new position to center on the mouse
            visible_width = 1.0 / new_zoom
            new_position = mouse_ratio - visible_width / 2
        else:  # Zoom out
            # Maintain the relative position
            current_center = self.position_ratio + (1.0 / self.zoom_level) / 2
            visible_width = 1.0 / new_zoom
            new_position = current_center - visible_width / 2

        # Limit the position
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
            # Calculate the horizontal movement only
            delta_x = event.pos().x() - self.last_mouse_pos.x()

            # Convert the movement in pixels to ratio
            delta_ratio = delta_x / self.total_width

            # Update the position
            new_position = self.position_ratio + delta_ratio

            # Limit the position
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
        """Update the size and position of the zoom rectangle"""
        visible_width = 1.0 / self.zoom_level
        rect_width = visible_width * self.total_width
        rect_x = self.position_ratio * self.total_width

        self.zoom_rect.setRect(rect_x, 0, rect_width, self.bar_height)

    def update_graphs(self):
        """Update the graphs based on the zoom and position"""
        visible_width = 1.0 / self.zoom_level

        # Calculate start and end indices
        start_index = int(self.position_ratio * self.data_length)
        end_index = int((self.position_ratio + visible_width) * self.data_length)

        # Ensure indices are valid
        start_index = max(0, start_index)
        end_index = min(self.data_length, end_index)

        self.update_zoom_callback(start_index, end_index)

    def reset_zoom(self):
        """Reset the zoom to the full view"""
        self.zoom_level = 1.0
        self.position_ratio = 0.0
        self.update_zoom_rect()
        self.update_graphs()

class Review(QMainWindow):
    def __init__(self, parent=None, file_path=None, existing_load=False):
        super().__init__()
        self.setWindowTitle("Data Monitoring Software")
        self.resize(1600, 900)
        self.setMinimumSize(1400, 800)
        self.loaded_data = {}
        self.parent = parent
        self.file_path = file_path
        self.existing_load = existing_load

        from utils.Menu_bar import MainBar

        self.main_bar = MainBar(self)
        self.main_bar._create_menubar()
        self.main_bar._all_false_or_true(False)
        self.main_bar.review()
        self.metadata = load_metadata(file_path) if file_path else None
        self.time_axis = None
        self.plot_widgets = {}  # Track plot widgets with proper reference
        self.displayed_plots = set()  # Track which plots are currently displayed
        if file_path:
            self.data = load_hdf5_data(file_path)
        else:
            self.data = {"loaded_data": {}}  # Initialize empty data structure
        self.setStyleSheet(self.get_stylesheet())
        self.init_ui()
        if self.file_path:
            self.load_hdf5_and_populate_tree(self.file_path)

        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.setInterval(100)
        self._cleanup_queue = []
        self._is_cleaning = False
        self._cleanup_timer.timeout.connect(self._process_cleanup_queue)
        self._pending_zoom_updates = []
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(50)
        self._zoom_timer.timeout.connect(self._process_zoom_updates)

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

        # Disable the Start Recording button if existing_load is False
        if not getattr(self, 'existing_load', False):
            if hasattr(self, 'record_button'):
                self.record_button.setEnabled(False)
                self.connect_button.setEnabled(False)
            else:
                # If build_footer hasn't run yet, delay disabling
                QTimer.singleShot(0, lambda: self.record_button.setEnabled(False))

    def build_header(self, layout):
        header = QHBoxLayout()
        header.addWidget(QLabel("Connected Systems"), stretch=1)
        header.addWidget(QLabel("Graphical / Visual Zone"), stretch=2)
        header.addWidget(QLabel("3D Perspective"), stretch=1)
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

        return layout

    def _process_cleanup_queue(self):
        """Process any pending widget cleanups"""
        if self._is_cleaning or not self._cleanup_queue:
            return

        self._is_cleaning = True
        try:
            widget = self._cleanup_queue.pop(0)
            if widget:
                widget.hide()
                widget.blockSignals(True)

                if widget.scene():
                    widget.scene().clear()

                if widget.parent():
                    parent_layout = widget.parent().layout()
                    if parent_layout:
                        parent_layout.removeWidget(widget)

                # Disable ViewBox updates first
                view_box = widget.getViewBox()
                if view_box:
                    try:
                        view_box.blockSignals(True)
                        if hasattr(view_box, 'sigRangeChanged'):
                            view_box.sigRangeChanged.disconnect()
                        if hasattr(view_box, 'sigTransformChanged'):
                            view_box.sigTransformChanged.disconnect()
                    except Exception:
                        pass

                # Clear all plot items
                try:
                    if hasattr(widget, 'plot_curves'):
                        for curve in widget.plot_curves:
                            widget.removeItem(curve)
                        widget.plot_curves.clear()
                except Exception:
                    pass

                # Clean up axes
                for axis in ['left', 'bottom', 'top', 'right']:
                    try:
                        axis_item = widget.getAxis(axis)
                        if axis_item:
                            axis_item.setParentItem(None)
                            axis_item.blockSignals(True)
                            QTimer.singleShot(100, axis_item.deleteLater)
                    except Exception:
                        pass

                widget.setParent(None)
                QApplication.processEvents()  # ✅ Laisser Qt finir les événements graphiques
                QTimer.singleShot(200, widget.deleteLater)  # ✅ suppression différée

        finally:
            self._is_cleaning = False
            if self._cleanup_queue:
                self._cleanup_timer.start()



    def _process_zoom_updates(self):
        """Process pending zoom updates"""
        while self._pending_zoom_updates:
            widget, start, end = self._pending_zoom_updates.pop(0)
            try:
                if widget and not widget.isHidden():
                    view_box = widget.getViewBox()
                    if view_box and view_box.scene():
                        view_box.setRange(xRange=(start, end), padding=0)
            except:
                pass



    def safe_cleanup_plot_widget(self, plot_widget):
        """Safely cleanup a plot widget to avoid memory leaks and crashes"""
        if plot_widget is None or plot_widget in self._cleanup_queue:
            return

        try:
            plot_widget.blockSignals(True)
            plot_widget.hide()

            if hasattr(plot_widget, 'full_data'):
                plot_widget.full_data = None

            if plot_widget.scene():
                plot_widget.scene().clear()

            self._cleanup_queue.append(plot_widget)

            if not self._cleanup_timer.isActive():
                self._cleanup_timer.start()

        except Exception as e:
            print(f"Error queueing plot cleanup: {e}")



    def create_plot_in_middle_panel(self, data, plot_name=None):
        """Create a new plot widget with proper cleanup of existing ones"""
        plot_title = plot_name if plot_name else "Sensor Data"

        # Check if the plot already exists and remove it safely
        if plot_title in self.plot_widgets:
            existing_widget = self.plot_widgets[plot_title]
            self.safe_cleanup_plot_widget(existing_widget)
            del self.plot_widgets[plot_title]

        # Create new plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.full_data = data
        plot_widget.plot_title = plot_title  # Store title as attribute
        plot_widget.plot_curves = []  # Store references to plot curves

        # Check if data is a 2D array (e.g., IMU data with 4 components)
        if isinstance(data, np.ndarray) and data.ndim == 2 and data.shape[1] == 4:
            colors = ['b', 'y', 'g', 'r']  # Blue, Yellow, Green, Red
            for i, color in enumerate(colors):
                curve = plot_widget.plot(data[:, i], pen=pg.mkPen(color=color, width=2))
                plot_widget.plot_curves.append(curve)
        else:
            curve = plot_widget.plot(data, pen=pg.mkPen(color='b', width=2))
            plot_widget.plot_curves.append(curve)

        plot_widget.setLabel('left', 'Value')
        plot_widget.setLabel('bottom', 'Index')
        plot_widget.setTitle(plot_title)

        # Store reference to the plot widget
        self.plot_widgets[plot_title] = plot_widget
        self.middle_layout.addWidget(plot_widget)

        # Update zoom bar data length - use the length of the first dimension for 2D data
        data_length = len(data) if data.ndim == 1 else data.shape[0]
        if data_length > 0:
            self.zoom_bar.set_data_length(data_length)

        # Adjust plot sizes
        self.adjust_plot_sizes()

    def adjust_plot_sizes(self):
        """Adjust the sizes of all plot widgets"""
        count = self.middle_layout.count()
        for i in range(count):
            item = self.middle_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, pg.PlotWidget):
                widget.setContentsMargins(0, 0, 0, 0)
                widget.setMinimumHeight(180)
                widget.setMaximumHeight(180)

        # Update container size
        self.middle_placeholder.setContentsMargins(0, 0, 0, 0)
        self.middle_layout.setSpacing(0)
        self.middle_placeholder.setMinimumHeight(count * 180)

    def build_middle_panel(self):
        layout = QVBoxLayout()
        self.middle_placeholder = QWidget()
        self.middle_layout = QVBoxLayout(self.middle_placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.middle_placeholder)

        # Add the interactive zoom bar
        self.zoom_bar = ZoomBar(self.update_zoom)
        self.zoom_bar.setFixedHeight(30)

        # Add a button for full zoom-out
        self.zoom_out_button = QPushButton("Full Zoom Out")
        self.zoom_out_button.clicked.connect(self.reset_zoom)

        layout.addWidget(scroll)
        layout.addWidget(self.zoom_bar)
        layout.addWidget(self.zoom_out_button)
        return layout

    def reset_zoom(self):
        """Reset the zoom bar"""
        self.zoom_bar.reset_zoom()

    def update_zoom(self, start_index, end_index):
        """Update the view of the graphs with the new indices"""
        for plot_title, widget in list(self.plot_widgets.items()):
            if widget is None or not widget.isVisible():
                continue

            try:
                view_box = widget.getViewBox()
                if view_box is None or not hasattr(widget, 'full_data'):
                    continue

                data = widget.full_data
                if data is None:
                    continue

                data_length = len(data) if isinstance(data, np.ndarray) and data.ndim >= 1 else len(data)
                safe_start = max(0, min(start_index, data_length - 1))
                safe_end = max(safe_start + 1, min(end_index, data_length))

                # Queue zoom update
                self._pending_zoom_updates.append((widget, safe_start, safe_end))

            except Exception as e:
                print(f"Error queueing zoom update: {e}")
                self.safe_cleanup_plot_widget(widget)

        # Start zoom timer if not active
        if self._pending_zoom_updates and not self._zoom_timer.isActive():
            self._zoom_timer.start()

    def build_right_panel(self):
        layout = QVBoxLayout()

        label = QLabel("3D Perspective")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(label)

        self.model_3d_widget = QLabel("3D Model Placeholder")
        self.model_3d_widget.setAlignment(Qt.AlignCenter)
        self.model_3d_widget.setStyleSheet("background-color: #e0e0e0; border: 1px solid #ccc;")
        layout.addWidget(self.model_3d_widget, stretch=3)

        self.animate_button = QPushButton("Start Animation")
        layout.addWidget(self.animate_button)

        self.reset_view_button = QPushButton("Reset View")
        layout.addWidget(self.reset_view_button)

        return layout

    def build_footer(self, layout):
        footer = QHBoxLayout()

        self.connect_button = QPushButton("Connect")
        footer.addWidget(self.connect_button)

        self.record_button = QPushButton("Start Recording")
        footer.addWidget(self.record_button)

        layout.addLayout(footer)

    def build_text_areas(self, layout):
        box_layout = QHBoxLayout()

        self.received_data_text = QTextEdit()
        self.received_data_text.setPlaceholderText("Received Data")
        self.received_data_text.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; font-size: 15px;")
        self.received_data_text.setFixedHeight(200)
        box_layout.addWidget(self.received_data_text)

        # --- Experimental Protocol as a word-like editor ---
        protocol_layout = QVBoxLayout()
        toolbar_layout = QHBoxLayout()

        self.bold_button = QPushButton("Bold")
        self.bold_button.setCheckable(True)
        self.bold_button.clicked.connect(self.set_protocol_bold)
        toolbar_layout.addWidget(self.bold_button)

        self.color_button = QPushButton("Color")
        self.color_button.clicked.connect(self.set_protocol_color)
        toolbar_layout.addWidget(self.color_button)

        toolbar_layout.addStretch()
        protocol_layout.addLayout(toolbar_layout)

        self.experiment_protocol_text = QTextEdit()
        self.experiment_protocol_text.setPlaceholderText("Experimental Protocol")
        self.experiment_protocol_text.setStyleSheet("background-color: white; border: 1px solid #ccc; font-size: 15px;")
        self.experiment_protocol_text.setFixedHeight(200)
        protocol_layout.addWidget(self.experiment_protocol_text)

        protocol_widget = QWidget()
        protocol_widget.setLayout(protocol_layout)
        box_layout.addWidget(protocol_widget)

        layout.addLayout(box_layout)

    def set_protocol_bold(self):
        cursor = self.experiment_protocol_text.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            current_weight = cursor.charFormat().fontWeight()
            new_weight = QFont.Bold if current_weight != QFont.Bold else QFont.Normal
            fmt.setFontWeight(new_weight)
            cursor.mergeCharFormat(fmt)
        else:
            # Toggle bold for future typing
            is_bold = self.bold_button.isChecked()
            self.experiment_protocol_text.setFontWeight(QFont.Bold if is_bold else QFont.Normal)
        # Keep button checked state in sync with current format
        self.bold_button.setChecked(self.experiment_protocol_text.fontWeight() == QFont.Bold)

    def set_protocol_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            cursor = self.experiment_protocol_text.textCursor()
            if not cursor.hasSelection():
                return
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.mergeCharFormat(fmt)

    def reorganize_plots(self):
        """Reorganize the graphs after a deletion"""
        # Clean up any None references
        self.plot_widgets = {k: v for k, v in self.plot_widgets.items() if v is not None}

        # Adjust plot sizes
        self.adjust_plot_sizes()

    def on_sensor_clickedd(self, item, column):
        if item.data(0, Qt.UserRole) == "disabled":
            return

        sensor_name = item.text(0)

        # If the graph is already displayed, remove it
        if sensor_name in self.displayed_plots:
            if sensor_name in self.plot_widgets:
                widget = self.plot_widgets[sensor_name]
                self.safe_cleanup_plot_widget(widget)
                del self.plot_widgets[sensor_name]

            self.displayed_plots.remove(sensor_name)
            QTimer.singleShot(100, self.reorganize_plots)
            return

        # If the graph is not displayed, add it
        if sensor_name in self.data["loaded_data"]:
            data_to_plot = self.data["loaded_data"][sensor_name].copy()  # Make a copy

            if sensor_name.startswith("EMG"):
                data_to_plot = data_to_plot[5:]

            QTimer.singleShot(0, lambda: self.create_plot_in_middle_panel(data_to_plot, plot_name=sensor_name))
            self.displayed_plots.add(sensor_name)
            QTimer.singleShot(100, self.reorganize_plots)

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

        # Clean up existing plots
        for plot_title, widget in list(self.plot_widgets.items()):
            self.safe_cleanup_plot_widget(widget)
        self.plot_widgets.clear()
        self.displayed_plots.clear()

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

    def closeEvent(self, event):
        """Clean up resources when closing the application"""
        # Stop all timers
        self._cleanup_timer.stop()
        self._zoom_timer.stop()

        # Clear all queues
        self._cleanup_queue.clear()
        self._pending_zoom_updates.clear()

        # Disable updates on all widgets
        for widget in self.plot_widgets.values():
            if widget:
                widget.setUpdatesEnabled(False)
                widget.hide()

        # Process remaining cleanups
        while self.plot_widgets:
            title, widget = self.plot_widgets.popitem()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Let Qt handle the rest
        QTimer.singleShot(500, lambda: super().closeEvent(event))

    def rien(self):
        pass

    def rienb(self):
        pass

    def delete_hdf5_file(self):
        pass

if __name__ == '__main__':
    if QApplication.instance() is None:
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()

    dashboard = Review()
    dashboard.show()
    sys.exit(app.exec_())
