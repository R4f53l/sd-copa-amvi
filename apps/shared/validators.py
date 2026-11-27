"""Small validation helpers shared by the bounded contexts."""

import uuid


def is_uuid(value):
    """True if ``value`` is a valid UUID string (e.g. a primary key)."""
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True
