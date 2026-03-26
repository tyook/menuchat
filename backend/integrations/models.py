import uuid
from django.db import models
from restaurants.models import Restaurant


class POSConnection(models.Model):
    class POSType(models.TextChoices):
        SQUARE = "square", "Square"
        TOAST = "toast", "Toast"
        MIDDLEWARE = "middleware", "Middleware"
        NONE = "none", "None"

    class PaymentMode(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        POS_COLLECTED = "pos_collected", "POS Collected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.OneToOneField(Restaurant, on_delete=models.CASCADE, related_name="pos_connection")
    pos_type = models.CharField(max_length=20, choices=POSType.choices, default=POSType.NONE)
    is_active = models.BooleanField(default=True)
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices, default=PaymentMode.STRIPE)
    oauth_access_token = models.TextField(blank=True, default="")
    oauth_refresh_token = models.TextField(blank=True, default="")
    oauth_token_expires_at = models.DateTimeField(null=True, blank=True)
    external_location_id = models.CharField(max_length=255, blank=True, null=True)
    middleware_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.restaurant.name} - {self.get_pos_type_display()}"


class POSSyncLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"
        MANUALLY_RESOLVED = "manually_resolved", "Manually Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="pos_sync_logs")
    pos_connection = models.ForeignKey(POSConnection, on_delete=models.CASCADE, related_name="sync_logs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    external_order_id = models.CharField(max_length=255, blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sync({self.order_id}, {self.status})"
