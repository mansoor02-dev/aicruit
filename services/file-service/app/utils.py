import os
from datetime import datetime

UPLOAD_FOLDER = "uploads"

def save_file(file, file_type):
    # Create directory if not exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{file_type}_{timestamp}_{file.filename}"

    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    file_url = f"http://localhost:8005/uploads/{filename}"
    return filename, file_url, file_path
