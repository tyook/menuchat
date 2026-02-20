import pytest

from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestCustomerModel:
    def test_create_customer(self):
        customer = CustomerFactory(email="alice@example.com", name="Alice")
        assert customer.email == "alice@example.com"
        assert customer.name == "Alice"
        assert customer.id is not None

    def test_password_hashing(self):
        customer = CustomerFactory()
        assert customer.check_password("testpass123")
        assert not customer.check_password("wrongpass")

    def test_str(self):
        customer = CustomerFactory(name="Bob", email="bob@example.com")
        assert str(customer) == "Bob (bob@example.com)"

    def test_default_fields(self):
        customer = CustomerFactory()
        assert customer.dietary_preferences == []
        assert customer.allergies == []
        assert customer.preferred_language == "en-US"
        assert customer.auth_provider == "email"
