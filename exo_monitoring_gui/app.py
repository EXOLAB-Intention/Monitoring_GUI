import sys
import os
import traceback
from PyQt5.QtWidgets import QApplication

def launch():
    """Launch the application"""
    try:
        # Set OpenGL to software rendering mode to avoid GPU issues
        os.environ["QT_OPENGL"] = "software"
        
        print("Creating QApplication instance...")
        app = QApplication(sys.argv)
        
        # Add project root to path to fix import issues
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        print("Project root added to path:", project_root)
        
        print("Importing MainApp...")
        try:
            from UI.main_window import MainApp
            print("MainApp imported successfully")
        except Exception as e:
            print(f"Error importing MainApp: {e}")
            print(traceback.format_exc())
            return
        
        print("Creating MainApp instance...")
        window = MainApp()
        
        print("Showing window...")
        window.show()
        
        print("Entering application event loop...")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"ERROR in launch(): {str(e)}")
        print(traceback.format_exc())
        input("Press Enter to exit...")  # To keep console window open

