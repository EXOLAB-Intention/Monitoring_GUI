import traceback
import importlib
import os
import subprocess
    
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_OPENGL"] = "software"

def check_dependencies():
    # Check non-problematic packages first
    required_packages = ["PyQt5", "h5py", "numpy", "setuptools"]
    missing = []
    
    for pkg in required_packages:
        try:
            print(f"Checking for {pkg}...")
            importlib.import_module(pkg)
            print(f"Successfully imported {pkg}")
        except ImportError:
            print(f"Missing package: {pkg}")
            missing.append(pkg)
        except Exception as e:
            print(f"Error importing {pkg}: {str(e)}")
            return False
    
    # Special handling for pyqtgraph
    print("Checking for pyqtgraph (installation only)...")
    try:
        import pkg_resources
        pkg_resources.get_distribution('pyqtgraph')
        print("pyqtgraph is installed (but not imported to avoid hanging)")
    except pkg_resources.DistributionNotFound:
        print("Missing package: pyqtgraph")
        missing.append("pyqtgraph")
    
    if missing:
        print(f"ERROR: Missing required packages: {', '.join(missing)}")
        print("Please install them using: pip install " + " ".join(missing))
        return False
    return True

def install_dependencies():
    try:
        print("Uninstalling conflicting packages...")
        subprocess.run(["pip", "uninstall", "pyqtgraph", "PyQt5", "-y"], check=True)
        print("Installing specific versions of packages...")
        subprocess.run(["pip", "install", "PyQt5==5.15.6", "pyqtgraph==0.12.3"], check=True)
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install dependencies: {str(e)}")
        print(traceback.format_exc())
        return False
    return True

def main():
    try:
        print("Checking dependencies...")
        if not check_dependencies():
            print("Attempting to install missing dependencies...")
            if not install_dependencies():
                input("Press Enter to exit...")
                return
            
        print("Starting application...")
        from app import launch
        print("Imported launch function")
        launch()
        print("Application launched")
    except Exception as e:
        print(f"ERROR: Failed to start application: {str(e)}")
        print(traceback.format_exc())
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
