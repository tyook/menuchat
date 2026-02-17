from datetime import timedelta
from rest_framework_simplejwt.tokens import Token


class CustomerAccessToken(Token):
    token_type = "access"
    lifetime = timedelta(hours=12)

    @classmethod
    def for_customer(cls, customer):
        token = cls()
        token["customer_id"] = str(customer.id)
        token["token_type"] = "customer_access"
        return token


class CustomerRefreshToken(Token):
    token_type = "refresh"
    lifetime = timedelta(days=7)
    access_token_class = CustomerAccessToken

    @classmethod
    def for_customer(cls, customer):
        token = cls()
        token["customer_id"] = str(customer.id)
        token["token_type"] = "customer_refresh"
        return token

    @property
    def access_token(self):
        access = CustomerAccessToken()
        access.set_exp(from_time=self.current_time)
        access["customer_id"] = self["customer_id"]
        access["token_type"] = "customer_access"
        return access
