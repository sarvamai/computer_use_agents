# Azure Blob Storage Integration

This module provides functionality to interact with Azure Blob Storage for uploading, downloading, and managing blob files.

## Setup

1. Install the required package:
   ```bash
   pip install azure-storage-blob
   ```

2. Configure your Azure Storage credentials by adding the following to your `.env` file:
   ```
   AZURE_STORAGE_CONNECTION_STRING="your_connection_string_here"
   # OR
   AZURE_STORAGE_ACCOUNT_NAME="your_account_name"
   AZURE_STORAGE_ACCOUNT_KEY="your_account_key"
   ```

## Quick Start

```python
from utils.azure_storage import AzureBlobStorage

# Initialize with connection string from environment variables
azure_storage = AzureBlobStorage()

# Or provide connection string directly
azure_storage = AzureBlobStorage(connection_string="your_connection_string")

# Create a container
azure_storage.create_container("my-container")

# Upload a file
result = azure_storage.upload_blob_from_file(
    container_name="my-container",
    blob_name="example.txt",
    file_path="path/to/local/file.txt"
)

# Get the URL of the uploaded blob
blob_url = result["url"]
print(f"File uploaded to: {blob_url}")
```

## Features

### Upload

- Upload from file path: `upload_blob_from_file()`
- Upload from data in memory: `upload_blob_from_data()`

### Download

- Download blob to file: `download_blob(download_path="path/to/save.txt")`
- Download blob to memory: `blob_data = download_blob()`

### Management

- List blobs in a container: `list_blobs()`
- Delete a blob: `delete_blob()`
- Get a blob URL with SAS token: `get_blob_url_with_sas()`

## Working with Agent Trajectories

To upload agent trajectory data and screenshots to Azure Blob Storage:

```python
from utils.azure_storage import AzureBlobStorage

def upload_trajectory(storage_folder, branch_id, container_name="agent-trajectories"):
    """
    Upload an agent branch's trajectory data to Azure Blob Storage
    
    Args:
        storage_folder: Base storage folder path
        branch_id: ID of the branch to upload
        container_name: Azure container name
    """
    azure = AzureBlobStorage()
    
    # Create container if it doesn't exist
    azure.create_container(container_name)
    
    # Path to branch folder
    branch_folder = os.path.join(storage_folder, branch_id)
    
    # Upload trajectory.json
    trajectory_path = os.path.join(branch_folder, "trajectory.json")
    if os.path.exists(trajectory_path):
        result = azure.upload_blob_from_file(
            container_name=container_name,
            blob_name=f"{branch_id}/trajectory.json",
            file_path=trajectory_path
        )
    
    # Upload screenshots
    for filename in os.listdir(branch_folder):
        if filename.startswith("screenshot_") and filename.endswith(".png"):
            screenshot_path = os.path.join(branch_folder, filename)
            azure.upload_blob_from_file(
                container_name=container_name,
                blob_name=f"{branch_id}/{filename}",
                file_path=screenshot_path,
                content_type="image/png"
            )
```

## Generating SAS URLs

For temporary access to blobs:

```python
# Generate a read-only URL that expires in 2 hours
sas_url = azure_storage.get_blob_url_with_sas(
    container_name="my-container",
    blob_name="example.txt",
    expiry_hours=2,
    permissions="r"
)
```
