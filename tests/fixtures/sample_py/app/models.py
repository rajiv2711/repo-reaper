"""Domain models: a base entity and a user."""


class Entity:
    """Base class for anything with an id."""

    def __init__(self, entity_id):
        self.entity_id = entity_id

    def describe(self):
        """Return a short text description."""
        return f"{type(self).__name__}#{self.entity_id}"


class User(Entity):
    """A user with a name."""

    def __init__(self, entity_id, name):
        super().__init__(entity_id)
        self.name = name

    def label(self):
        """Return the user's display label."""
        return self.describe() + ":" + self.name
