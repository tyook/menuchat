import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from restaurants.models import MenuItem, MenuItemModifier, MenuItemVariant, Restaurant


class Tab(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSING = "closing", "Closing"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="tabs"
    )
    table_identifier = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "table_identifier"],
                condition=models.Q(status="open"),
                name="unique_open_tab_per_table",
            )
        ]

    def __str__(self):
        return f"Tab {self.table_identifier} ({self.status}) - {self.restaurant.name}"

    @property
    def subtotal(self):
        if hasattr(self, "orders") and self.orders.exists():
            return sum(order.subtotal for order in self.orders.all())
        return Decimal("0.00")

    @property
    def tax_amount(self):
        if hasattr(self, "orders") and self.orders.exists():
            return sum(order.tax_amount for order in self.orders.all())
        return Decimal("0.00")

    @property
    def total(self):
        if hasattr(self, "orders") and self.orders.exists():
            return sum(order.total_price for order in self.orders.all())
        return Decimal("0.00")

    @property
    def amount_paid(self):
        if hasattr(self, "payments") and self.payments.exists():
            return sum(p.amount for p in self.payments.filter(payment_status="paid"))
        return Decimal("0.00")

    @property
    def amount_remaining(self):
        return self.total - self.amount_paid


class TabPayment(models.Model):
    class Type(models.TextChoices):
        FULL = "full", "Full"
        SPLIT_EVEN = "split_even", "Split Even"
        PAY_BY_ITEM = "pay_by_item", "Pay By Item"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tab = models.ForeignKey(Tab, on_delete=models.CASCADE, related_name="payments")
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")],
        default="pending",
    )
    items = models.ManyToManyField("OrderItem", blank=True, related_name="tab_payments")
    split_count = models.PositiveIntegerField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TabPayment {self.type} ${self.amount} ({self.payment_status})"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="orders")
    table_identifier = models.CharField(max_length=50, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    customer_phone = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    raw_input = models.TextField()
    parsed_json = models.JSONField(default=dict, blank=True)
    language_detected = models.CharField(max_length=10, blank=True, default="")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=0,
        help_text="Tax rate snapshot at time of order (percentage)",
    )
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment fields
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("pos_collected", "POS Collected"),
            ("deferred", "Deferred"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
        ],
        default="pending",
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )
    stripe_payment_method_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    class PayoutStatus(models.TextChoices):
        PENDING = "pending"
        TRANSFERRED = "transferred"
        PAID_OUT = "paid_out"
        FAILED = "failed"

    payout_status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )
    payout = models.ForeignKey(
        "restaurants.Payout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    tab = models.ForeignKey(
        Tab, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )

    customer_allergies = models.JSONField(default=list, blank=True, help_text="Snapshot of customer allergies at time of order")

    # POS Integration
    external_order_id = models.CharField(max_length=255, blank=True, null=True, help_text="Order ID in external POS system")
    pos_sync_status = models.CharField(
        max_length=20,
        choices=[
            ("not_applicable", "Not Applicable"),
            ("pending", "Pending"),
            ("synced", "Synced"),
            ("retrying", "Retrying"),
            ("failed", "Failed"),
            ("manually_resolved", "Manually Resolved"),
        ],
        default="not_applicable",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        table = f" (Table {self.table_identifier})" if self.table_identifier else ""
        return f"Order {self.id}{table} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    variant = models.ForeignKey(MenuItemVariant, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    special_requests = models.TextField(blank=True, default="")
    modifiers = models.ManyToManyField(MenuItemModifier, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} ({self.variant.label})"
