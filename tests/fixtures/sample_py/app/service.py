"""Business logic for creating users."""
import os

from .models import User
from .repository import UserRepository
from app.utils import normalize, validate


class UserService:
    """Creates users and stores them in a repository."""

    def __init__(self, repo=None):
        self.repo = repo or UserRepository()

    def create(self, entity_id, name):
        """Validate, build and save a new user."""
        if not validate(name):
            raise ValueError("empty name")
        user = User(entity_id, normalize(name))
        self.log("create " + user.label())
        return self.repo.save(user)

    def log(self, message):
        """Print a message when APP_DEBUG is set."""
        if os.environ.get("APP_DEBUG"):
            print(message)
