from rest_framework import serializers

from orders.models import Order, OrderItem, Tab, TabPayment


class ParseInputSerializer(serializers.Serializer):
    raw_input = serializers.CharField(max_length=2000)
    table_identifier = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)


class ConfirmOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    modifier_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    special_requests = serializers.CharField(required=False, default="", allow_blank=True)


class ConfirmOrderSerializer(serializers.Serializer):
    items = ConfirmOrderItemSerializer(many=True)
    raw_input = serializers.CharField(allow_blank=True, default="")
    table_identifier = serializers.CharField(required=False, default="", allow_blank=True)
    language = serializers.CharField(required=False, default="en")
    customer_name = serializers.CharField(max_length=255, required=False, default="")
    customer_email = serializers.EmailField(required=False, default="", allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, default="", allow_blank=True)
    payment_method_id = serializers.CharField(required=False, default="", allow_blank=True)
    save_card = serializers.BooleanField(required=False, default=False)
    return_url = serializers.URLField(required=False, default="")
    allergies = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class OrderItemResponseSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="menu_item.name")
    variant_label = serializers.CharField(source="variant.label")
    variant_price = serializers.DecimalField(source="variant.price", max_digits=8, decimal_places=2)
    line_total = serializers.SerializerMethodField()

    def get_line_total(self, obj):
        base = obj.variant.price * obj.quantity
        modifier_total = sum(m.price_adjustment for m in obj.modifiers.all()) * obj.quantity
        return f"{base + modifier_total:.2f}"

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "name",
            "variant_label",
            "variant_price",
            "quantity",
            "special_requests",
            "line_total",
        ]


class OrderResponseSerializer(serializers.ModelSerializer):
    items = OrderItemResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "table_identifier",
            "customer_name",
            "customer_email",
            "customer_phone",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "total_price",
            "payment_status",
            "stripe_payment_intent_id",
            "created_at",
            "items",
            "customer_allergies",
        ]


class TabOrderSerializer(serializers.Serializer):
    """Lightweight order representation for tab view."""
    id = serializers.UUIDField()
    status = serializers.CharField()
    items = OrderItemResponseSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    created_at = serializers.DateTimeField()


class TabResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    table_identifier = serializers.CharField()
    status = serializers.CharField()
    orders = TabOrderSerializer(many=True)
    subtotal = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    opened_at = serializers.DateTimeField()

    def get_subtotal(self, tab):
        return f"{tab.subtotal:.2f}"

    def get_tax_amount(self, tab):
        return f"{tab.tax_amount:.2f}"

    def get_total(self, tab):
        return f"{tab.total:.2f}"

    def get_amount_paid(self, tab):
        return f"{tab.amount_paid:.2f}"

    def get_amount_remaining(self, tab):
        return f"{tab.amount_remaining:.2f}"


class TabPaymentRequestSerializer(serializers.Serializer):
    tab_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=TabPayment.Type.choices)
    split_count = serializers.IntegerField(required=False, min_value=2)
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, data):
        if data["type"] == "split_even" and not data.get("split_count"):
            raise serializers.ValidationError({"split_count": "Required for split_even."})
        if data["type"] == "pay_by_item" and not data.get("item_ids"):
            raise serializers.ValidationError({"item_ids": "Required for pay_by_item."})
        return data
