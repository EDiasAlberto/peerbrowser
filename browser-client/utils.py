def generate_hash(filepath: str) -> str:
    return hashlib.md5(open(filepath, "rb").read()).hexdigest()
