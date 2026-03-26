from rest_framework import serializers
from restaurants.models import Payout


class PayoutListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id", "amount", "currency", "status", "orders_count",
            "fee_amount", "period_start", "period_end", "created_at",
        ]


class PayoutDetailSerializer(serializers.ModelSerializer):
    orders = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id", "stripe_transfer_id", "stripe_payout_id",
            "amount", "currency", "status", "fee_amount", "fee_rate",
            "fee_fixed", "orders_count", "period_start", "period_end",
            "created_at", "orders",
        ]

    def get_orders(self, obj):
        from orders.serializers import OrderResponseSerializer

        return OrderResponseSerializer(obj.orders.all(), many=True).data
