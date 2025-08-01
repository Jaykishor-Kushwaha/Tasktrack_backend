import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import os

# Path to your service account key file
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'tasktrak-service-acc-key.json')

# Define the required scopes for Google Drive access
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Authenticate using the service account file
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Build the Drive API service
service = build('drive', 'v3', credentials=credentials)

def upload_to_drive(image_data, file_name, mime_type):
    # Decode the Base64 string to binary data
    image_data = base64.b64decode(image_data.split(',')[1])

    # Create a new file on Google Drive
    file_metadata = {'name': file_name}
    
    # Use MediaIoBaseUpload to upload binary data
    media = MediaIoBaseUpload(io.BytesIO(image_data), mimetype=mime_type)
    
    # Upload the file
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    # Make the file publicly accessible
    service.permissions().create(
        fileId=file.get('id'),
        body={'type': 'anyone', 'role': 'reader'},
        fields='id'
    ).execute()

    # Return the file's public URL
    return f"https://drive.google.com/uc?id={file.get('id')}"