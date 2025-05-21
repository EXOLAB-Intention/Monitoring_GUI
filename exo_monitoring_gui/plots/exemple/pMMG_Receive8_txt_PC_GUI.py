import sys
import serial
import serial.tools.list_ports
import time

import numpy as np

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QCheckBox,
                             QLineEdit, QMessageBox, QGroupBox, QFormLayout)
from PyQt5.QtGui import QIcon

# PyQtGraph
import pyqtgraph as pg

# pour créer l'exécutable
# pyinstaller --onefile --noconsole --strip pMMG_Receive8_txt_PC_GUI.py

#############################################################################
PROGRAM_VERSION = "1.11"
# 1.00   Première version
# 1.10   Ajout d'un timer pour surveiller la connexion/déconnexion USB, optimisation du graphique temps réel (objet Line)
# 1.11   Nom de fichier automatique
#############################################################################

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"pMMG Receiver v{PROGRAM_VERSION}")
        self.resize(1200, 700)

        # ----------- Options globales PyQtGraph (optimisation) -----------
        pg.setConfigOptions(
            antialias=False,       # Désactive l'anticrénelage (plus rapide)
            useOpenGL=True,        # Accélération OpenGL
            foreground='k',        # Couleur des labels (noir)
            background='w'         # Fond blanc
        )

        # Initialisation des variables série et données
        self.serial_port = None
        self.is_reading = False          # Indique si la réception des données est en cours
        self.rx_buffer = ""              # Buffer de réception accumulé
        self.max_time_ms = 10000         # Temps max affiché sur le graphique (10s)

        # Variables pour la gestion automatique du nom de fichier
        self.lastBaseName = ""           # Dernier nom de base utilisé
        self.lastFileIndex = 0           # Numéro de fichier pour le même nom de base

        # Buffer temps réel (liste) - suppression des données >10s via trimData()
        self.data_buffer = {
            'Time': [],
            'Pressure1': [],
            'Pressure2': [],
            'Pressure3': [],
            'Pressure4': [],
            'Pressure5': [],
            'Pressure6': [],
            'Pressure7': [],
            'Pressure8': [],
            'FSR_L': [],
            'FSR_R': []
        }

        # Initialisation de l'interface graphique
        self._initUI()

        # Tentative de connexion au port série
        self._connectSerial()

        # Timer pour mise à jour du graphique (50ms)
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(50)
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start()

        # Timer pour lecture série (5ms)
        self.read_timer = QTimer(self)
        self.read_timer.setInterval(5)
        self.read_timer.timeout.connect(self.read_data)

    def _initUI(self):
        """Construction de l'interface graphique"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # ----------- (Gauche) Zone graphique PyQtGraph ------------
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Pressure / FSR')
        self.plot_widget.setLabel('bottom', 'Time [ms]')
        self.plot_widget.setTitle('Graphique temps réel')
        self.plot_widget.addLegend()  # Légende
        self.plot_widget.showGrid(x=True, y=True, alpha=0.4)
        main_layout.addWidget(self.plot_widget, stretch=7)

        # Dictionnaire pour stocker les courbes
        self.curves = {}

        # Nom/couleur/label pour chaque donnée
        self.plot_config = {
            'Pressure1': ('pMMG1', 'b'),
            'Pressure2': ('pMMG2', 'orange'),
            'Pressure3': ('pMMG3', 'yellow'),
            'Pressure4': ('pMMG4', 'g'),
            'Pressure5': ('pMMG5', 'blue'),
            'Pressure6': ('pMMG6', 'indigo'),
            'Pressure7': ('pMMG7', 'violet'),
            'Pressure8': ('pMMG8', 'brown'),
            'FSR_L'    : ('FSR_L', 'lightblue'),
            'FSR_R'    : ('FSR_R', 'lime'),
        }

        # Création des courbes dans le PlotItem (données vides au départ)
        for key, (label, color) in self.plot_config.items():
            pen = pg.mkPen(color=color, width=1)
            curve = self.plot_widget.plot(name=label, pen=pen)
            curve.setData([], [])
            self.curves[key] = curve

        # ----------- (Droite) Zone réglages/boutons ------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(20)
        main_layout.addWidget(right_widget, stretch=3)

        # (1) Zone des cases à cocher
        checkbox_group = QGroupBox("Sélectionner les données à afficher")
        form_chk_layout = QFormLayout(checkbox_group)
        self.checkbox_list = {}

        for key, (label_text, _) in self.plot_config.items():
            cb = QCheckBox(label_text)
            cb.setChecked(True)  # Tout afficher par défaut
            self.checkbox_list[key] = cb
            form_chk_layout.addRow(cb)

        right_layout.addWidget(checkbox_group)

        # (2) Zone de saisie du nom de fichier (l'extension .txt sera ajoutée automatiquement)
        file_group = QGroupBox("Nom de base du fichier de sortie")
        file_layout = QVBoxLayout(file_group)
        self.file_edit = QLineEdit()
        self.file_edit.setText("dataFile")  # Valeur par défaut
        file_layout.addWidget(self.file_edit)
        right_layout.addWidget(file_group)

        # (3) Zone d'état + boutons
        self.label_state = QLabel("Non connecté")
        self.label_state.setStyleSheet("font-weight: bold; color: red;")

        self.btn_start = QPushButton("Démarrer la lecture")
        self.btn_start.clicked.connect(self.toggle_reading)

        right_layout.addWidget(self.label_state, alignment=Qt.AlignCenter)
        right_layout.addWidget(self.btn_start)

    def _connectSerial(self):
        """Recherche automatique du port COM affiché comme STMicroelectronics puis tentative de connexion"""
        ports = serial.tools.list_ports.comports()
        stm_port = None
        for port in ports:
            if port.manufacturer and "STMicroelectronics" in port.manufacturer:
                stm_port = port.device
                break

        if stm_port:
            try:
                self.serial_port = serial.Serial(stm_port, 921600, timeout=0.1)
                self.label_state.setText("Connecté")
                self.label_state.setStyleSheet("font-weight: bold; color: green;")
            except serial.SerialException as e:
                QMessageBox.critical(self, "Erreur série", str(e))
                self.serial_port = None
                self.label_state.setText("Non connecté")
                self.label_state.setStyleSheet("font-weight: bold; color: red;")
        else:
            self.serial_port = None
            self.label_state.setText("Non connecté")
            self.label_state.setStyleSheet("font-weight: bold; color: red;")

    def toggle_reading(self):
        """Action lors du clic sur le bouton Démarrer/Arrêter la lecture"""
        if not self.serial_port:
            QMessageBox.warning(self, "Attention", "Port série non connecté !")
            return

        if not self.is_reading:
            # --- Démarrer la lecture ---
            base_name = self.file_edit.text().strip()
            if not base_name:
                QMessageBox.warning(self, "Attention", "Veuillez saisir un nom de base pour le fichier.")
                return

            # Si le nom de base a changé, on réinitialise l'index
            if base_name != self.lastBaseName:
                self.lastBaseName = base_name
                self.lastFileIndex = 0

            # Incrémentation de l'index du fichier
            self.lastFileIndex += 1
            # Nom du fichier : baseName_XX.txt (XX = 2 chiffres)
            filename = f"{self.lastBaseName}_{self.lastFileIndex:02d}.txt"

            try:
                self.file_obj = open(filename, mode='w', encoding='utf-8')
                header = ("Time[ms],Pressure1[kPa],Pressure2[kPa],Pressure3[kPa],"
                          "Pressure4[kPa],Pressure5[kPa],Pressure6[kPa],Pressure7[kPa],"
                          "Pressure8[kPa],FSR_L,FSR_R\n")
                self.file_obj.write(header)
            except Exception as e:
                QMessageBox.critical(self, "Erreur fichier", str(e))
                return

            # Nouvelle mesure : on réinitialise le buffer et le graphique
            for key in self.data_buffer:
                self.data_buffer[key].clear()

            # Mise à jour de l'état et du bouton
            self.is_reading = True
            self.label_state.setText("Lecture en cours")
            self.label_state.setStyleSheet("font-weight: bold; color: blue;")
            self.btn_start.setText("Arrêter la lecture")

            # Démarrage du timer de lecture série
            self.read_timer.start()

        else:
            # --- Arrêter la lecture ---
            self.is_reading = False
            self.label_state.setText("Connecté")
            self.label_state.setStyleSheet("font-weight: bold; color: green;")
            self.btn_start.setText("Démarrer la lecture")

            # Fermeture du fichier
            if hasattr(self, 'file_obj'):
                self.file_obj.close()

            # Arrêt du timer de lecture
            self.read_timer.stop()

    def read_data(self):
        """Lit toutes les données du buffer série puis les analyse ligne par ligne"""
        if not self.serial_port or not self.is_reading:
            return

        data_bytes = self.serial_port.read_all()
        if not data_bytes:
            return

        self.rx_buffer += data_bytes.decode('utf-8', errors='ignore')

        # Découpage par ligne
        lines = self.rx_buffer.split('\n')
        # La dernière ligne peut être incomplète, on la garde dans le buffer
        self.rx_buffer = lines.pop(-1)

        for line in lines:
            line = line.strip()
            if not line:
                continue
            data_list = line.split(',')
            if len(data_list) >= 11:
                try:
                    # Conversion en float
                    time_val   = float(data_list[0].strip())
                    p1_val     = float(data_list[1].strip())
                    p2_val     = float(data_list[2].strip())
                    p3_val     = float(data_list[3].strip())
                    p4_val     = float(data_list[4].strip())
                    p5_val     = float(data_list[5].strip())
                    p6_val     = float(data_list[6].strip())
                    p7_val     = float(data_list[7].strip())
                    p8_val     = float(data_list[8].strip())
                    fsr_l_val  = float(data_list[9].strip())
                    fsr_r_val  = float(data_list[10].strip())

                    # Sauvegarde dans le buffer
                    self.data_buffer['Time'].append(time_val)
                    self.data_buffer['Pressure1'].append(p1_val)
                    self.data_buffer['Pressure2'].append(p2_val)
                    self.data_buffer['Pressure3'].append(p3_val)
                    self.data_buffer['Pressure4'].append(p4_val)
                    self.data_buffer['Pressure5'].append(p5_val)
                    self.data_buffer['Pressure6'].append(p6_val)
                    self.data_buffer['Pressure7'].append(p7_val)
                    self.data_buffer['Pressure8'].append(p8_val)
                    self.data_buffer['FSR_L'].append(fsr_l_val)
                    self.data_buffer['FSR_R'].append(fsr_r_val)

                    # Sauvegarde dans le fichier
                    if hasattr(self, 'file_obj'):
                        save_str = (f"{time_val},{p1_val},{p2_val},{p3_val},"
                                    f"{p4_val},{p5_val},{p6_val},{p7_val},"
                                    f"{p8_val},{fsr_l_val},{fsr_r_val}\n")
                        self.file_obj.write(save_str)

                    # Suppression des données de plus de 10 secondes
                    self._trimData(time_val)

                except ValueError:
                    print(f"Erreur de conversion dans la ligne : {line}")
            else:
                print(f"Données incomplètes : {line}")

    def _trimData(self, current_time_ms):
        """Supprime les données plus anciennes que max_time_ms (par défaut 10s)"""
        threshold = current_time_ms - self.max_time_ms
        if threshold < 0:
            return

        time_list = self.data_buffer['Time']
        keep_index = 0
        for i, t in enumerate(time_list):
            if t >= threshold:
                keep_index = i
                break

        if keep_index > 0:
            for key in self.data_buffer:
                self.data_buffer[key] = self.data_buffer[key][keep_index:]

    def update_plot(self):
        """Met à jour le graphique toutes les 50ms"""
        if not self.data_buffer['Time']:
            return

        time_vals = np.array(self.data_buffer['Time'], dtype=float)

        # Plage de l'axe X (10 secondes)
        x_min = max(0, time_vals[-1] - self.max_time_ms)
        x_max = max(time_vals[-1], 10)
        self.plot_widget.setXRange(x_min, x_max, padding=0)

        # Mise à jour des courbes selon les cases cochées
        for key in self.curves:
            if self.checkbox_list[key].isChecked():
                y_vals = np.array(self.data_buffer[key], dtype=float)
                # Pas de downsample, skipFiniteCheck à True pour optimiser la vitesse
                self.curves[key].setData(time_vals, y_vals, skipFiniteCheck=True)
            else:
                self.curves[key].setData([], [])

    def closeEvent(self, event):
        """Nettoyage des ressources à la fermeture de la fenêtre"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        if hasattr(self, 'file_obj') and not self.file_obj.closed:
            self.file_obj.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
