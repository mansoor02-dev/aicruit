import os
import requests
import tempfile
from typing import Optional


def download_file_from_url(url: str, temp_dir: Optional[str] = None) -> str:
    """
    Download a file from URL and save to temporary location
    
    Args:
        url: URL of the file to download (can be absolute or relative)
        temp_dir: Optional temporary directory path
    
    Returns:
        str: Path to downloaded file
    """
    try:
        # Handle relative URLs - if it starts with /static, prepend file service URL
        if url.startswith('/static/'):
            file_service_url = os.getenv("FILE_SERVICE_URL", "http://aicruit_file_service:8005")
            url = f"{file_service_url}{url}"
        elif url.startswith('/'):
            # Other relative URLs
            file_service_url = os.getenv("FILE_SERVICE_URL", "http://aicruit_file_service:8005")
            url = f"{file_service_url}{url}"
        
        # Create temp directory if not provided
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()
        
        os.makedirs(temp_dir, exist_ok=True)
        
        # Get file extension from URL
        file_extension = os.path.splitext(url)[1] or '.pdf'
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension,
            dir=temp_dir
        )
        temp_path = temp_file.name
        temp_file.close()
        
        # Download file
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Save to temp file
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        return temp_path
    
    except Exception as e:
        raise Exception(f"Failed to download file from URL: {str(e)}")

