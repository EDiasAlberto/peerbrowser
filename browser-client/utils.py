TRACKER_SERVER_URL = "http://trackers.ediasalberto.com"
MEDIA_DOWNLOAD_DIR = "./media/"

def generate_hash(filepath: str) -> str:
    return hashlib.md5(open(filepath, "rb").read()).hexdigest()
