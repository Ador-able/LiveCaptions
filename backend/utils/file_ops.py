import os
import shutil
from fastapi import UploadFile

def save_upload_file(upload_file: UploadFile, destination_path: str):
    try:
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()

def ensure_directory(path: str):
    if not os.path.exists(path):
        os.makedirs(path)
