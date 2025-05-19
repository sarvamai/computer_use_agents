import os
from azure_storage import AzureBlobStorage
from dotenv import load_dotenv

load_dotenv()

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
os.environ["AZURE_STORAGE_ACCOUNT_NAME"] = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
os.environ["AZURE_STORAGE_ACCOUNT_KEY"] = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

# Initialize client
azure_storage = AzureBlobStorage()

# Create a container
azure_storage.create_container("agent-trajectories")

# Upload a file
result = azure_storage.upload_blob_from_file(
    container_name="agent-trajectories",
    blob_name="branch_123/trajectory.json",
    file_path="./agent_storage/branch_123/trajectory.json"
)

print(f"File uploaded to: {result['url']}")