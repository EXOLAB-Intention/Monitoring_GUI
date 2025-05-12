import sys
import time
import numpy as np
from PyQt5 import QtWidgets, QtGui
import pyqtgraph as pg

from data_generator.sensor_simulator import SensorSimulator

class RealtimePlot(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMG & pMMG Live Dashboard")
        self.resize(1400, 800)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")

        # Main layout
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # Plot area
        self.plot_area = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.plot_area)

        # pMMG Plot
        self.pmmg_plot = self.create_plot("pMMG Data (mV)")
        self.pmmg_curves = [self.pmmg_plot.plot(pen=pg.intColor(i)) for i in range(8)]
        self.plot_area.addWidget(self.pmmg_plot)

        # EMG Plot
        self.emg_plot = self.create_plot("EMG Data (µV)")
        self.emg_curves = [self.emg_plot.plot(pen=pg.intColor(i)) for i in range(8)]
        self.plot_area.addWidget(self.emg_plot)

        # Buffers
        self.pmmg_data = [np.zeros(100) for _ in range(8)]
        self.emg_data = [np.zeros(100) for _ in range(8)]

        # Value display
        self.value_display = QtWidgets.QTextEdit()
        self.value_display.setReadOnly(True)
        self.value_display.setMaximumHeight(100)
        self.value_display.setStyleSheet("background-color: #2b2b2b; font-size: 14px;")
        self.layout.addWidget(self.value_display)

        # Controls
        self.setup_controls()

        # State
        self.simulator = SensorSimulator()
        self.running = True
        self.start_time = time.time()
        self.logged_data = []

        # Timer
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(40)

    def create_plot(self, title):
        plot = pg.PlotWidget(title=title)
        plot.setBackground('#1e1e1e')
        plot.getAxis('left').setTextPen('white')
        plot.getAxis('bottom').setTextPen('white')
        plot.showGrid(x=True, y=True, alpha=0.3)
        plot.setTitle(title, color='white', size='14pt')
        return plot

    def setup_controls(self):
        controls = QtWidgets.QHBoxLayout()
        self.layout.addLayout(controls)

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_btn)

        self.clear_btn = QtWidgets.QPushButton("Close / Save")
        self.clear_btn.clicked.connect(self.close_and_save)
        controls.addWidget(self.clear_btn)

        # Screenshot button
        self.screenshot_btn = QtWidgets.QPushButton("Take Screenshot")
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        controls.addWidget(self.screenshot_btn)

        controls.addSpacing(20)

        self.checkboxes = {}
        for signal_type in ['pMMG', 'EMG']:
            for i in range(8):
                cb = QtWidgets.QCheckBox(f"{signal_type}{i}")
                cb.setChecked(True)
                cb.setStyleSheet("margin-right: 10px;")
                controls.addWidget(cb)
                self.checkboxes[f"{signal_type}{i}"] = cb

    def toggle_pause(self):
        self.running = not self.running
        self.pause_btn.setText("Resume" if not self.running else "Pause")

    def close_and_save(self):
        np.savetxt("logged_data.csv", self.logged_data, delimiter=",",
                   header="Time," + ",".join([f"pMMG{i}" for i in range(8)] + [f"EMG{i}" for i in range(8)]),
                   comments='')
        QtWidgets.qApp.quit()

    def update_data(self):
        if not self.running:
            return

        t = time.time() - self.start_time
        packet = self.simulator.generate_packet(t)
        current_values = []

        for i in range(8):
            # pMMG
            if self.checkboxes[f"pMMG{i}"].isChecked():
                self.pmmg_data[i] = np.roll(self.pmmg_data[i], -1)
                self.pmmg_data[i][-1] = packet["pMMG"][i]
                self.pmmg_curves[i].setData(self.pmmg_data[i])
                current_values.append(f"pMMG{i}: {packet['pMMG'][i]:.2f}")
            else:
                self.pmmg_curves[i].clear()

            # EMG
            if self.checkboxes[f"EMG{i}"].isChecked():
                self.emg_data[i] = np.roll(self.emg_data[i], -1)
                self.emg_data[i][-1] = packet["EMG"][i]
                self.emg_curves[i].setData(self.emg_data[i])
                current_values.append(f"EMG{i}: {packet['EMG'][i]:.2f}")
            else:
                self.emg_curves[i].clear()

        # Text display
        self.value_display.setText(" | ".join(current_values))

        # Log
        row = [t] + packet["pMMG"] + packet["EMG"]
        self.logged_data.append(row)

        if len(self.logged_data) % 100 == 0:
            np.savetxt("logged_data.csv", self.logged_data, delimiter=",",
                       header="Time," + ",".join([f"pMMG{i}" for i in range(8)] + [f"EMG{i}" for i in range(8)]),
                       comments='')

    def take_screenshot(self):
        filename = "screenshot.png"
        screenshot = self.grab()  # Capture the whole widget as an image
        screenshot.save(filename, "PNG")
        QtWidgets.QMessageBox.information(self, "Screenshot", f"Screenshot saved as {filename}")

