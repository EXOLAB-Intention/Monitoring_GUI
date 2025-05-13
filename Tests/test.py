import h5py

def read_metadata(subject_file):
    try:
        with h5py.File(subject_file, 'r') as f:
            if 'metadata' in f:
                metadata = f['metadata']
                data = {}

                # Read all attributes from the metadata group
                for key, value in metadata.attrs.items():
                    data[key] = value

                # Read the last modified timestamp from the file attributes
                if 'last_modified' in f.attrs:
                    data['last_modified'] = f.attrs['last_modified']

                return data
            else:
                print("No metadata found in the file.")
                return None
    except Exception as e:
        print(f"Error reading metadata: {e}")
        return None

# Example usage
subject_file = "C:/Users/samio/Documents/BUT/BUT2/stage/travail/Monitoring_GUI/h.h5"  # Replace with the path to your HDF5 file
metadata = read_metadata(subject_file)

if metadata:
    print("Metadata:")
    for key, value in metadata.items():
        print(f"{key}: {value}")
else:
    print("Failed to read metadata.")
