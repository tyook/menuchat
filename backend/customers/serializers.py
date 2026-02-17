from rest_framework import serializers
from customers.models import Customer
from customers.authentication import CustomerRefreshToken


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20, required=False, default="")
    link_order_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        if Customer.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A customer with this email already exists.")
        return value.lower()

    def create(self, validated_data):
        link_order_id = validated_data.pop("link_order_id", None)
        password = validated_data.pop("password")
        customer = Customer(**validated_data)
        customer.set_password(password)
        customer.save()

        # Link order if provided
        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

        return customer

    def to_representation(self, instance):
        refresh = CustomerRefreshToken.for_customer(instance)
        return {
            "customer": {
                "id": str(instance.id),
                "email": instance.email,
                "name": instance.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        customer = Customer.objects.filter(email__iexact=data["email"]).first()
        if not customer or not customer.password or not customer.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["customer"] = customer
        return data


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "email", "name", "phone",
            "dietary_preferences", "allergies", "preferred_language",
            "auth_provider", "created_at",
        ]
        read_only_fields = ["id", "email", "auth_provider", "created_at"]
