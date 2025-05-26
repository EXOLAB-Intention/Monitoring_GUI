from PyQt5.QtWidgets import QMessageBox,QMainWindow
import os
from datetime import datetime
from utils.hdf5_utils import save_metadata

class MainAppBack(QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

    def _show_error(self, message):
        """Display an error message"""
        QMessageBox.critical(self, "Error", message)
        print(f"ERROR: {message}")

    def _autosave(self):
        """Automatically save current work if modified"""
        if self.parent.modified and self.parent.current_subject_file:
            try:
                # Perform actual save operation
                self.parent.parent.main_bar.save_subject()

                # Update status bar with autosave info
                self.parent.statusBar().showMessage(f"Auto-saved to {os.path.basename(self.parent.current_subject_file)}", 3000)

                print(f"Auto-saved at {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"Error during auto-save: {str(e)}")

    def update_subject_metadata(self, metadata):
        """Update the subject metadata based on information provided"""
        if not self.parent.current_subject_file:
            print("Error: No subject file is currently open")
            return

        try:
            # Save metadata to the current file
            save_metadata(self.parent.current_subject_file, metadata)

            # Update UI components if needed
            self.parent.modified = True

            # Update status bar
            self.parent.statusBar().showMessage(f"Subject metadata updated for: {os.path.basename(self.parent.current_subject_file)}")

            # Additional processing if needed
            if 'Name' in metadata and 'Last Name' in metadata:
                subject_name = f"{metadata['Name']} {metadata['Last Name']}"
                print(f"Subject information updated for: {subject_name}")
                print(self.parent.current_subject_file)

            # The subject has been created, so we can enable relevant actions
            self.parent.main_bar.save_subject_action.setEnabled(True)
            self.parent.main_bar.save_subject_as_action.setEnabled(True)
            self.parent.main_bar.show_metadata_action.setEnabled(True)

        except Exception as e:
            self._show_error(f"Error updating subject metadata: {str(e)}")
