from PyQt5.QtWidgets import QMainWindow, QPushButton, QLabel, QAction, QFileDialog
from ui.informations import createInformationWindow  # change le nom de la fonction si tu veux
import h5py
from ui.informations import createInformationWindow  # change le nom de la fonction si tu veux
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Data Monitoring Software")
        self.setGeometry(0, 0, 1920, 1080)
        menubar = self.menuBar()

        # Création du menu "File"
        file_menu = menubar.addMenu("File")

        create_subject_action = QAction("Create new subject", self)
        create_subject_action.triggered.connect(self.create_new_subject)
        file_menu.addAction(create_subject_action)

        file_menu.addAction("Load existing subject")
        file_menu.addSeparator()

        # Création des actions désactivées
        self.save_subject_action = QAction("Save subject", self)
        self.save_subject_action.setEnabled(False)

        self.save_subject_as_action = QAction("Save subject as...", self)
        self.save_subject_as_action.setEnabled(False)

        file_menu.addAction(self.save_subject_action)
        file_menu.addAction(self.save_subject_as_action)
        file_menu.addSeparator()

        file_menu.addAction("Load existing trial")

        self.Save = QAction("Save current trial", self)
        self.Save.setEnabled(False)

        self.SaveAs = QAction("Save current trial as...", self)
        self.SaveAs.setEnabled(False)
        
        self.SaveImage = QAction("Save current plot as image", self)
        self.SaveImage.setEnabled(False)

        file_menu.addAction(self.Save)
        file_menu.addAction(self.SaveAs)
        file_menu.addAction(self.SaveImage)
        file_menu.addSeparator()

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Clear plots")
        edit_menu.addAction("Refresh the connected system")
        edit_menu.addAction("Request .h5 transfer")

        self.setStyleSheet("""
            QMenu {
                background-color: #f7f7f7;
                border: 1px solid #ccc;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #dceaff;
                color: black;
            }
            QMenu::separator {
                height: 1px;
                background: lightgray;
                margin-left: 10px;
                margin-right: 10px;
            }
        """)


        #button = QPushButton("Update Data", self)
        #button.setGeometry(50, 150, 200, 50)
        #button.clicked.connect(self.showInformationWindow)

    def showInformationWindow(self):
        from ui.informations import createInformationWindow
        self.info_window = createInformationWindow()  # garde une référence
        self.info_window.show()

    def create_new_subject(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Create New Subject File",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
            options=options
        )

        if filename:
            if not filename.endswith(".h5") and not filename.endswith(".hdf5"):
                filename += ".h5"

            with h5py.File(filename, 'w') as f:
                f.attrs['subject_created'] = True 

            self.save_subject_action.setEnabled(True)
            self.save_subject_as_action.setEnabled(True)

            print(f"Nouveau fichier HDF5 créé : {filename}")
            d = createInformationWindow()
            d.show()
