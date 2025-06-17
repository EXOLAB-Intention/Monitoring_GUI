import h5py
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QTreeWidgetItem, QVBoxLayout
    )
from PyQt5.QtGui import QBrush, QColor
import numpy as np
import pyqtgraph as pg
import json


def load_metadata(subject_file):
    """Load metadata from an HDF5 file.
    Prioritizes reading participant_ prefixed attributes from root.
    Falls back to reading attributes from /metadata group for backward compatibility.
    """
    data = {}
    image_path = None # Initialize image_path

    if not os.path.exists(subject_file):
        print(f"File not found: {subject_file}")
        return data, image_path
    
    try:
        with h5py.File(subject_file, 'r') as f:
            root_attrs = dict(f.attrs)
            for key, value in root_attrs.items():
                # Store the key as is, e.g. "participant_name"
                data[key] = value 
                # If the key is specifically "participant_image_path", keep it for image_path
                if key == "participant_image_path":
                    image_path = value
            # Also handle the case where "image_path" is at the root and is not yet defined by "participant_image_path"
                if key == "image_path" and image_path is None:
                    image_path = value
            
            # After going through all attributes, if image_path has been found (either by "image_path" or "participant_image_path"),
            # make sure it is in 'data' under the standard key "participant_image_path".
            # This is useful if "image_path" was found but not "participant_image_path", 
            # or to ensure that the value of "participant_image_path" (if present) is prioritized and stored.
            if image_path is not None:
                data["participant_image_path"] = image_path

    except Exception as e:
        print(f"Error loading metadata from {subject_file}: {e}")
    
    return data, image_path


def save_metadata(subject_file, data: dict):
    """Save metadata to an HDF5 file.
    Detects if the file uses the new structure (participant_ attributes at root)
    or old structure (/metadata group) and saves accordingly.
    """
    try:
        with h5py.File(subject_file, 'a') as f:
            # Set subject_created attribute if it doesn't exist
            if "subject_created" not in f.attrs:
                f.attrs['subject_created'] = True

            image_path_value = None
            if "image_path" in data:
                image_path_value = data.pop("image_path") # Remove to avoid double writing by the loop

            for key, value in data.items():
                # Standardize key names for participant attributes
                # If the key is already prefixed (e.g. during loading/modification), do not re-prefix
                if key.startswith("participant_"):
                    attr_key = key
                else:
                    attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

                f.attrs[attr_key] = value

                # If the normalized key corresponds to participant_image_path, store its value
                # to ensure it is written under "image_path" if not already done.
                if attr_key == "participant_image_path" and image_path_value is None:
                    image_path_value = value

            # Save image_path at the root under the key "image_path" if it exists
            if image_path_value is not None:
                f.attrs["image_path"] = image_path_value

            f.attrs['last_modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return True
    except Exception as e:
        print(f"Error saving metadata to {subject_file}: {e}")
        return False


def save_to_default(data: dict, custom_filename: str = None):
    """Save metadata to a default HDF5 file if no file is specified,
    with participant metadata at the root and sensor group structure.
    If custom_filename is provided, it is used instead of generating one.
    """
    try:
        if custom_filename:
            output_filename = custom_filename
            # Ensure the directory for custom_filename exists if it includes a path
            output_dir = os.path.dirname(output_filename)
            if output_dir: # If there's a directory part
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Create a default filename based on the current date/time
            default_dir = os.path.join(os.path.expanduser("~"), "Documents", "Monitoring-Data")
            os.makedirs(default_dir, exist_ok=True)
            output_filename = os.path.join(
                default_dir, 
                f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.h5"
            )
        
        with h5py.File(output_filename, 'w') as f: # 'w' to create a new file
            # Basic attributes at the root
            f.attrs['file_creation_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.attrs['subject_created'] = True # Re-enabled for compatibility with load_existing_subject

            # Save participant information (data) as attributes at the root
            image_path_value = None
            if "image_path" in data:
                image_path_value = data.pop("image_path") # Remove to avoid double writing

            for key, value in data.items():
                # Standardize key names for participant attributes
                attr_key = f"participant_{key.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                f.attrs[attr_key] = value
                # If the normalized key corresponds to participant_image_path and image_path_value has not been set by data["image_path"]
                if attr_key == "participant_image_path" and image_path_value is None:
                    image_path_value = value
            
            # Save image_path at the root under the key "image_path" if it was found
            if image_path_value is not None:
                f.attrs["image_path"] = image_path_value
            
            # Create the group structure for sensor data
            sensor_group = f.create_group('Sensor')
            sensor_group.create_group('EMG')
            sensor_group.create_group('IMU')
            sensor_group.create_group('LABEL')
            sensor_group.create_group('Time')

        print(f"New HDF5 file created with participant metadata and sensor structure: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Error saving to default file: {e}")
        return None


def extract_group_data(file_path, group_name):
    """
    Returns a dictionary with data from the specified subgroup (e.g.: 'EMG', 'Time', etc.)
    Excludes empty datasets.
    """
    def read_group(group):
        result = {}
        for key, item in group.items():
            if isinstance(item, h5py.Dataset):
                if 0 in item.shape:
                    continue  # Skip empty datasets
                try:
                    result[key] = item[()]
                except Exception as e:
                    result[key] = f"Read error: {e}"
            elif isinstance(item, h5py.Group):
                child_data = read_group(item)
                if child_data:  # Skip empty groups
                    result[key] = child_data
        return result

    with h5py.File(file_path, "r") as f:
        sensor_group = f.get("Sensor")
        if sensor_group is None:
            raise ValueError("The 'Sensor' group is not found in the file.")

        target_group = sensor_group.get(group_name)
        if target_group is None:
            raise ValueError(f"The '{group_name}' group is not found in 'Sensor'.")

        return read_group(target_group)
    
def plot_sensor_data(self, sensor_name, data_array):
    """Plots sensor data on a graph."""
    plot_widget = pg.PlotWidget()
    plot_widget.setBackground('w')
    plot_widget.setTitle(sensor_name, color='k', size='14pt')
    plot_widget.plot(self.time_axis, data_array, pen=pg.mkPen(color='b', width=2))
    plot_widget.setLabel('left', sensor_name)
    plot_widget.setLabel('bottom', 'Time (s)')
    plot_widget.showGrid(x=True, y=True)
    self.middle_layout.addWidget(plot_widget)


def load_hdf5_and_populate_tree(self, file_path):
    """Loads an HDF5 file, updates the QTreeWidget, and automatically plots available sensors."""
    self.connected_systems.clear()
    self.middle_layout.setParent(None)  # Clears old graphs
    self.middle_layout = QVBoxLayout()
    self.middle_placeholder.setLayout(self.middle_layout)

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
                    self.loaded_data[dataset_upper] = obj[:]

        f.visititems(visitor)

    # Generates X from time_length and 40 ms between each sample
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
            sensor_item.setForeground(0, QBrush(QColor("black")))
            group_item.addChild(sensor_item)

            if dataset_name in self.loaded_data:
                plot_sensor_data(self, dataset_name, self.loaded_data[dataset_name])

        group_item.setExpanded(True)


def load_hdf5_data(file_path):

    loaded_data = {}
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
                    loaded_data[dataset_upper] = obj[:]

        f.visititems(visitor)

    if time_length is not None:
        time_axis = np.arange(time_length) * 0.040
    else:
        any_key = next(iter(loaded_data), None)
        if any_key:
            length = len(loaded_data[any_key])
            time_axis = np.arange(length) * 0.040
        else:
            time_axis = np.array([])

    return {
        "loaded_data": loaded_data,
        "data_structure": data_structure,
        "time_axis": time_axis
    }


def copy_all_data_preserve_root_metadata(source_path, dest_path):
    # Check if the source file exists
    if not os.path.exists(source_path):
        print(f"Error: The source file {source_path} does not exist.")
        return False

    # Check if the source file is a valid HDF5 file
    try:
        with h5py.File(source_path, 'r') as test_file:
            test_file.attrs.keys()
    except (OSError, h5py.errors.HDF5Error) as e:
        print(f"Error: The source file {source_path} is corrupted or invalid: {e}")
        return False

    # Create the destination file if it doesn't exist
    if not os.path.exists(dest_path):
        with h5py.File(dest_path, 'w') as _:
            pass

    try:
        with h5py.File(source_path, 'r') as src_file, h5py.File(dest_path, 'a') as dst_file:
            # Copy datasets/groups
            for name in src_file:
                if name in dst_file:
                    print(f"⚠️  '{name}' already exists in the destination file, it will not be overwritten.")
                    continue
                src_file.copy(name, dst_file)

            # Copy root attributes
            for key, value in src_file.attrs.items():
                dst_file.attrs[key] = value

        return True
    except Exception as e:
        print(f"Error while copying data: {e}")
        return False



def copy_only_root_metadata(source_path, dest_path):
    # Check if the source file exists
    if not os.path.exists(source_path):
        print(f"Error: The source file {source_path} does not exist.")
        return False

    # Check if the source file is a valid HDF5 file
    try:
        with h5py.File(source_path, 'r') as test_file:
            test_file.attrs.keys()
    except (OSError, h5py.errors.HDF5Error) as e:
        print(f"Error: The source file {source_path} is corrupted or invalid: {e}")
        return False

    try:
        # Create or open the destination file
        with h5py.File(source_path, 'r') as src_file, h5py.File(dest_path, 'w') as dst_file:
            # Copy only the root attributes
            for key, value in src_file.attrs.items():
                dst_file.attrs[key] = value
            print(f"✅ Root metadata successfully copied to {dest_path}.")
        return True
    except Exception as e:
        print(f"Error while copying metadata: {e}")
        return False

def inject_metadata_to_hdf(json_relative_path, hdf_path):
    base_dir = os.path.dirname(__file__)  # directory of here.py
    json_full_path = os.path.join(base_dir, '..', 'plots', json_relative_path)
    json_full_path = os.path.abspath(json_full_path)

    # Load the JSON
    with open(json_full_path, 'r') as f:
        metadata = json.load(f)

    # Inject into the HDF
    with h5py.File(hdf_path, 'a') as hdf:
        if "metadata" in hdf.attrs:
            del hdf.attrs["metadata"]
        hdf.attrs["metadata"] = json.dumps(metadata)

def delet_experimental(hdf_path):
    with h5py.File(hdf_path, 'r+') as f:  # read+write mode
        if len(f.attrs) > 0:  # there are attributes at the root
            f.attrs["experiment_protocol"] = ""  # modifies or creates the attribute
        else:
            f.attrs["experiment_protocol"] = None  # or deletes, but None is not necessarily valid


def load_sensor_config(file_path):
    with h5py.File(file_path, 'r') as f:
        root_attrs = dict(f.attrs)
        if root_attrs:
            print(f"Metadata at the root of '{file_path}':")
            for key, value in root_attrs.items():
                if key == "metadata":
                    return json.loads(value)