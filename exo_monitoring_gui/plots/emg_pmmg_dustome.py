import sys
import numpy as np
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QTextEdit
)
from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from data_generator.sensor_simulator import SensorSimulator

class RealtimePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Data Plot Demo")
        self.setGeometry(100, 100, 1200, 700)

        # Central widget & layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.v_layout = QVBoxLayout(self.main_widget)

        # Plot widget
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setBackground('k')
        self.graphWidget.addLegend()
        self.graphWidget.setLabel('left', 'Value')
        self.graphWidget.setLabel('bottom', 'Time (index)')
        self.graphWidget.showGrid(x=True, y=True)
        self.v_layout.addWidget(self.graphWidget)

        # Bottom layout: controls + value display
        self.bottom_layout = QHBoxLayout()
        self.v_layout.addLayout(self.bottom_layout)

        # Controls
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.bottom_layout.addWidget(self.pause_btn)

        self.clear_btn = QPushButton("Clear Graphs")
        self.clear_btn.clicked.connect(self.clear_graphs)
        self.bottom_layout.addWidget(self.clear_btn)

        # Checkboxes for EMG & pMMG
        self.checkboxes = {}
        for signal in ['EMG', 'pMMG']:
            for i in range(8):
                cb = QCheckBox(f"{signal}{i}")
                cb.setChecked(True)
                self.checkboxes[f"{signal}{i}"] = cb
                self.bottom_layout.addWidget(cb)

        # Display area for current values
        self.value_display = QTextEdit()
        self.value_display.setReadOnly(True)
        self.value_display.setMaximumHeight(90)
        self.v_layout.addWidget(self.value_display)

        # Simulator & data
        self.simulator = SensorSimulator()
        self.running = True
        self.time_window = 100
        self.time_data = deque(np.linspace(-self.time_window, 0, self.time_window), maxlen=self.time_window)
        self.emg_data = [deque([0]*self.time_window, maxlen=self.time_window) for _ in range(8)]
        self.pmmg_data = [deque([0]*self.time_window, maxlen=self.time_window) for _ in range(8)]
        self.emg_curves = []
        self.pmmg_curves = []

        for i in range(8):
            color = pg.intColor(i)
            self.emg_curves.append(
                self.graphWidget.plot(pen=pg.mkPen(color=color, width=1), name=f"EMG {i}")
            )
            self.pmmg_curves.append(
                self.graphWidget.plot(pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.DashLine), name=f"pMMG {i}")
            )

        self.logged_data = []

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def toggle_pause(self):
        self.running = not self.running
        self.pause_btn.setText("Resume" if not self.running else "Pause")

    def clear_graphs(self):
        for i in range(8):
            self.emg_data[i] = deque([0]*self.time_window, maxlen=self.time_window)
            self.pmmg_data[i] = deque([0]*self.time_window, maxlen=self.time_window)
            self.emg_curves[i].setData([], [])
            self.pmmg_curves[i].setData([], [])

    def update_plot(self):
        if not self.running:
            return

        packet = self.simulator.generate_packet()
        emg = packet["EMG"]
        pmmg = packet["pMMG"]

        self.time_data.append(self.time_data[-1] + 1)
        current_values = []

        for i in range(8):
            if self.checkboxes[f"EMG{i}"].isChecked():
                self.emg_data[i].append(emg[i])
                self.emg_curves[i].setData(self.time_data, list(self.emg_data[i]))
                current_values.append(f"EMG{i}: {emg[i]:.2f}")
            else:
                self.emg_curves[i].clear()

            if self.checkboxes[f"pMMG{i}"].isChecked():
                self.pmmg_data[i].append(pmmg[i])
                self.pmmg_curves[i].setData(self.time_data, list(self.pmmg_data[i]))
                current_values.append(f"pMMG{i}: {pmmg[i]:.2f}")
            else:
                self.pmmg_curves[i].clear()

        # Log values
        self.logged_data.append([self.time_data[-1]] + emg + pmmg)
        if len(self.logged_data) % 100 == 0:
            np.savetxt("logged_data.csv", self.logged_data, delimiter=",",
                       header="Time," + ",".join([f"EMG{i}" for i in range(8)] + [f"pMMG{i}" for i in range(8)]),
                       comments='')

        self.value_display.setText(" | ".join(current_values))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = RealtimePlot()
    main.show()
    sys.exit(app.exec_())
