import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def pos_encryption_key(settings):
    """Provide a valid Fernet key for POS encryption in all integration tests."""
    settings.POS_ENCRYPTION_KEY = Fernet.generate_key().decode()
