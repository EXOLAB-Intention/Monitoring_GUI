import h5py
import os
from datetime import datetime

def load_metadata(subject_file):
    """Load metadata from an HDF5 file"""
    data = {}
    image_path = None

    if not os.path.exists(subject_file):
        print(f"File not found: {subject_file}")
        return data, image_path
    
    try:
        with h5py.File(subject_file, 'r') as f:
            if 'metadata' in f:
                metadata = f['metadata']
                for key in metadata.attrs:
                    data[key] = metadata.attrs[key]
                
                # Get image path if it exists
                if 'image_path' in metadata.attrs:
                    image_path = metadata.attrs['image_path']
    except Exception as e:
        print(f"Error loading metadata: {e}")
    
    return data, image_path

def save_metadata(subject_file, data: dict):
    """Save metadata to an HDF5 file"""
    try:
        with h5py.File(subject_file, 'a') as f:
            if 'metadata' in f:
                metadata = f['metadata']
            else:
                metadata = f.create_group('metadata')
            
            # Save all data as attributes
            for key, value in data.items():
                metadata.attrs[key] = value
            
            # Update last modified timestamp
            f.attrs['last_modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return True
    except Exception as e:
        print(f"Error saving metadata: {e}")
        return False

def save_to_default(data: dict):
    """Save metadata to a default HDF5 file if no file is specified"""
    try:
        # Create a default filename based on the current date/time
        default_dir = os.path.join(os.path.expanduser("~"), "Documents", "Monitoring-Data")
        os.makedirs(default_dir, exist_ok=True)
        
        default_filename = os.path.join(
            default_dir, 
            f"subject_{datetime.now().strftime('%Y%m%d_%H%M%S')}.h5"
        )
        
        # Create a new file with basic structure
        with h5py.File(default_filename, 'w') as f:
            f.attrs['subject_created'] = True
            f.attrs['creation_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata = f.create_group('metadata')
            f.create_group('trials')
            
            # Save provided metadata
            for key, value in data.items():
                metadata.attrs[key] = value
        
        print(f"Data saved to default file: {default_filename}")
        return default_filename
    except Exception as e:
        print(f"Error saving to default file: {e}")
        return None
