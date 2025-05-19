"""
Azure Blob Storage utility functions for uploading, downloading, and managing blobs.
Based on Microsoft's documentation: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-upload-python
"""

import os
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_blob_sas, BlobSasPermissions


class AzureBlobStorage:
    def __init__(self, connection_string=None, account_name=None, account_key=None):
        """
        Initialize Azure Blob Storage client using either a connection string or account credentials.
        
        Args:
            connection_string (str, optional): Azure Storage connection string
            account_name (str, optional): Azure Storage account name
            account_key (str, optional): Azure Storage account key
        """
        self.connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.account_name = account_name or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key = account_key or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        
        if not (self.connection_string or (self.account_name and self.account_key)):
            raise ValueError(
                "Either a connection string or account name/key pair must be provided or set as environment variables"
            )
            
        if self.connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        else:
            # Create using account name and key (SAS URLs could also be used)
            # This is just a placeholder - actual implementation would need endpoint URL too
            raise NotImplementedError("Account name/key authentication not fully implemented")
    
    def create_container(self, container_name):
        """
        Create a container in the Azure Blob Storage account.
        
        Args:
            container_name (str): Name of the container to create
            
        Returns:
            ContainerClient: Azure Container client object
        """
        container_client = self.blob_service_client.get_container_client(container_name)
        try:
            container_client.create_container()
            print(f"Container '{container_name}' created successfully.")
        except Exception as e:
            if "ContainerAlreadyExists" in str(e):
                print(f"Container '{container_name}' already exists.")
            else:
                raise
        return container_client
    
    def upload_blob_from_file(self, container_name, blob_name, file_path, content_type=None):
        """
        Upload a file to Azure Blob Storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name to give the blob in storage
            file_path (str): Path to the file to upload
            content_type (str, optional): Content type of the file
            
        Returns:
            dict: Information about the uploaded blob
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        with open(file_path, "rb") as data:
            if content_type:
                blob_client.upload_blob(data, overwrite=True, content_type=content_type)
            else:
                blob_client.upload_blob(data, overwrite=True)
        
        print(f"File {file_path} uploaded to container {container_name} as {blob_name}")
        return {
            "container": container_name,
            "blob_name": blob_name,
            "size": os.path.getsize(file_path),
            "url": blob_client.url
        }
    
    def upload_blob_from_data(self, container_name, blob_name, data, content_type=None):
        """
        Upload data to Azure Blob Storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name to give the blob in storage
            data (bytes or IO stream): Data to upload
            content_type (str, optional): Content type of the data
            
        Returns:
            dict: Information about the uploaded blob
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        if content_type:
            blob_client.upload_blob(data, overwrite=True, content_type=content_type)
        else:
            blob_client.upload_blob(data, overwrite=True)
        
        print(f"Data uploaded to container {container_name} as {blob_name}")
        return {
            "container": container_name,
            "blob_name": blob_name,
            "url": blob_client.url
        }
    
    def download_blob(self, container_name, blob_name, download_path=None):
        """
        Download a blob from Azure Blob Storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob to download
            download_path (str, optional): Path where to save the downloaded file
            
        Returns:
            bytes or str: If download_path is provided, returns the path to the downloaded file,
                          otherwise returns the blob data
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        if download_path:
            with open(download_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            print(f"Blob {blob_name} downloaded to {download_path}")
            return download_path
        else:
            blob_data = blob_client.download_blob().readall()
            print(f"Blob {blob_name} downloaded")
            return blob_data
    
    def list_blobs(self, container_name, name_starts_with=None):
        """
        List blobs in a container.
        
        Args:
            container_name (str): Name of the container
            name_starts_with (str, optional): Filter to list only blobs whose names begin with this
            
        Returns:
            list: List of blob objects
        """
        container_client = self.blob_service_client.get_container_client(container_name)
        blobs = list(container_client.list_blobs(name_starts_with=name_starts_with))
        return blobs
    
    def delete_blob(self, container_name, blob_name):
        """
        Delete a blob from Azure Blob Storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob to delete
            
        Returns:
            bool: True if deletion was successful
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        blob_client.delete_blob()
        print(f"Blob {blob_name} deleted from container {container_name}")
        return True
    
    def get_blob_url_with_sas(self, container_name, blob_name, expiry_hours=1, permissions="r"):
        """
        Get a URL with SAS token for a blob.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob
            expiry_hours (int, optional): Hours until the SAS token expires
            permissions (str, optional): Permissions for the SAS token (e.g., "r" for read)
            
        Returns:
            str: URL with SAS token
        """
        if not self.account_name or not self.account_key:
            raise ValueError("Account name and key are required for SAS token generation")
            
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        # Create SAS token with specified permissions
        sas_permissions = BlobSasPermissions(read='r' in permissions,
                                           add='a' in permissions,
                                           create='c' in permissions,
                                           write='w' in permissions,
                                           delete='d' in permissions)
        
        # Set expiry time
        expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=sas_permissions,
            expiry=expiry
        )
        
        # Return the blob URL with the SAS token
        return f"{blob_client.url}?{sas_token}"


# Example usage
def example_upload(connection_string, container_name):
    """
    Example of how to use the AzureBlobStorage class to upload a file.
    
    Args:
        connection_string (str): Azure Storage connection string
        container_name (str): Name of container to use
    """
    # Initialize the storage client
    azure_storage = AzureBlobStorage(connection_string=connection_string)
    
    # Create a container if it doesn't exist
    azure_storage.create_container(container_name)
    
    # Upload a file
    local_file_path = "example.txt"
    blob_name = f"example_{uuid.uuid4()}.txt"
    
    # Create a sample file
    with open(local_file_path, "w") as f:
        f.write("This is a test file for Azure Blob Storage upload.")
    
    # Upload the file
    upload_result = azure_storage.upload_blob_from_file(
        container_name, 
        blob_name, 
        local_file_path
    )
    
    print(f"Upload complete. Blob URL: {upload_result['url']}")
    
    # Clean up
    os.remove(local_file_path)
