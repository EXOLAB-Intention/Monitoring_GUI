import sys
import traceback
from PyQt5.QtWidgets import QApplication

def launch():
    """Launch the application"""
    try:
        print("Creating QApplication instance...")
        app = QApplication(sys.argv)
        
        print("Importing MainApp...")
        from UI.main_window import MainApp
        
        print("Creating MainApp instance...")
        window = MainApp()
        
        print("Showing window...")
        window.show()
        
        print("Entering application event loop...")
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"ERROR in launch(): {str(e)}")
        print(traceback.format_exc())
        input("Press Enter to exit...")  # Pour garder la fenêtre de console ouverte

