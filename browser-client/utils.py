import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

TRACKER_SERVER_URL = os.getenv("TRACKER_SERVER_URL", "http://localhost:8000")
MEDIA_DOWNLOAD_DIR = "./media/"
TEMPFILE_LOC = "./tempfile"

def generate_hash(filepath: str) -> str:
    return hashlib.md5(open(filepath, "rb").read()).hexdigest()
