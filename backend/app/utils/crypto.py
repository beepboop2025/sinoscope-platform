import hashlib


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256 (matching the existing Node.js implementation)."""
    return hashlib.sha256(key.encode()).hexdigest()
