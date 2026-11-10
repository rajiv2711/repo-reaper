"""In-memory storage for users."""
import json

from app.models import User
from app.utils import data_dir


class UserRepository:
    """Stores users in a dict keyed by id."""

    def __init__(self):
        self.items = {}
        self.path = data_dir()

    def save(self, user):
        """Validate and store a user, then return it."""
        validate(user)
        self.items[user.entity_id] = user
        return user

    def dump(self):
        """Serialize all user names to JSON."""
        return json.dumps({key: user.name for key, user in self.items.items()})


def validate(user):
    """Raise TypeError if the object is not a User."""
    if not isinstance(user, User):
        raise TypeError("expected a User")
