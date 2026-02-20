import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Customer(models.Model):
    class AuthProvider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, blank=True, default="")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, default="")
    auth_provider = models.CharField(max_length=10, choices=AuthProvider.choices, default=AuthProvider.EMAIL)
    auth_provider_id = models.CharField(max_length=255, blank=True, default="")
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    dietary_preferences = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(max_length=10, blank=True, default="en-US")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def get_or_create_stripe_customer(self):
        """Get existing or create new Stripe Customer. Returns stripe_customer_id."""
        if self.stripe_customer_id:
            return self.stripe_customer_id

        import stripe
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe_customer = stripe.Customer.create(
            email=self.email,
            name=self.name,
            metadata={"customer_id": str(self.id)},
        )
        self.stripe_customer_id = stripe_customer.id
        self.save(update_fields=["stripe_customer_id"])
        return self.stripe_customer_id

    def __str__(self):
        return f"{self.name} ({self.email})"
