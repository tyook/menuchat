from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import services
from accounts.serializers import LoginSerializer, RegisterSerializer, UserProfileSerializer


class CSRFTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return ensure_csrf_cookie(view)

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from accounts.tasks import send_welcome_email_task
        send_welcome_email_task.delay(str(user.id))
        response = Response(
            {"user": services.user_to_dict(user)},
            status=status.HTTP_201_CREATED,
        )
        return services.set_auth_cookies(response, user)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Google token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = services.authenticate_google(token)
        services.link_order_to_user(request.data.get("link_order_id"), user)
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class AppleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Apple token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = services.authenticate_apple(
            token, name=request.data.get("name", "")
        )
        services.link_order_to_user(request.data.get("link_order_id"), user)
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return csrf_exempt(view)

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh.get("user_id")
            from accounts.models import User

            user = User.objects.get(id=user_id)
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        response = Response({"user": services.user_to_dict(user)})
        return services.set_auth_cookies(response, user)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        response = Response({"detail": "Logged out."})
        return services.clear_auth_cookies(response)


class WsTokenView(APIView):
    """Return the current access token so the frontend can pass it to WebSocket."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.COOKIES.get("access_token", "")
        if not token:
            return Response(
                {"detail": "No access token cookie."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"token": token})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.user_to_dict(request.user))

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(services.user_to_dict(request.user))


class OrderHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.get_order_history(request.user))


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        return Response(services.get_order_detail(request.user, order_id))


class PaymentMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.list_payment_methods(request.user))


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pm_id):
        services.detach_payment_method(request.user, pm_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
