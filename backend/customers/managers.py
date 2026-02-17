from django.contrib.auth.hashers import make_password, check_password


class CustomerManager:
    """
    Not a Django model manager — just a helper for password operations
    since Customer is not an AbstractUser.
    """

    @staticmethod
    def hash_password(raw_password: str) -> str:
        return make_password(raw_password)

    @staticmethod
    def check_password(raw_password: str, hashed: str) -> bool:
        return check_password(raw_password, hashed)
