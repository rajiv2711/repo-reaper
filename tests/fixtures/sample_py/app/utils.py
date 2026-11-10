"""Small helpers shared across the app."""
import os


def normalize(name):
    """Strip and lowercase a name."""
    return name.strip().lower()


def validate(name):
    """Return True if the name is non-empty after normalizing."""
    return bool(normalize(name))


def data_dir():
    """Return the data directory from the environment."""
    return os.environ.get("APP_DATA", "/tmp/app")
