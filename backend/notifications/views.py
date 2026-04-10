from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeviceToken
from .serializers import DeviceTokenSerializer


class DeviceRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]
        platform = serializer.validated_data["platform"]
        order_id = serializer.validated_data.get("order_id")

        defaults = {
            "platform": platform,
            "is_active": True,
        }

        if request.user.is_authenticated:
            defaults["user"] = request.user
        elif order_id:
            from orders.models import Order
            defaults["order"] = Order.objects.get(id=order_id)

        device_token, created = DeviceToken.objects.update_or_create(
            token=token_value,
            defaults=defaults,
        )

        return Response(
            {"status": "registered"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
