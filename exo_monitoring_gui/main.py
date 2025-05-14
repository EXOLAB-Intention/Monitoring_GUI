import traceback
import sys
import os
from plots.model_3d_viewer import Model3DViewer

sys.path.append(os.path.abspath(os.path.dirname(__file__)))


def main():
    try:
        print("Starting application...")
        from app import launch
        print("Imported launch function")
        launch()
        print("Application launched")  # If this line is not displayed, the error is in launch()
    except Exception as e:
        print(f"ERROR: Failed to start application: {str(e)}")
        print(traceback.format_exc())
        input("Press Enter to exit...")  # To keep the console window open

if __name__ == "__main__":
    main()
