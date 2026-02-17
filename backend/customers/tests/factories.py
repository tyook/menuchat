import factory
from customers.models import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    name = factory.Faker("name")
    phone = "555-0100"
    auth_provider = "email"
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
