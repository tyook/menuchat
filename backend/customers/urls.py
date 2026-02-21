from django.urls import path

from customers.views import (
    AppleAuthView,
    CustomerLoginView,
    CustomerOrderDetailView,
    CustomerOrderHistoryView,
    CustomerProfileView,
    CustomerRegisterView,
    CustomerTokenRefreshView,
    GoogleAuthView,
    PaymentMethodDetailView,
    PaymentMethodsView,
)

urlpatterns = [
    path("auth/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("auth/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("auth/google/", GoogleAuthView.as_view(), name="customer-google-auth"),
    path("auth/apple/", AppleAuthView.as_view(), name="customer-apple-auth"),
    path("auth/refresh/", CustomerTokenRefreshView.as_view(), name="customer-token-refresh"),
    path("profile/", CustomerProfileView.as_view(), name="customer-profile"),
    path("orders/", CustomerOrderHistoryView.as_view(), name="customer-orders"),
    path("orders/<uuid:order_id>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),
    path("payment-methods/", PaymentMethodsView.as_view(), name="customer-payment-methods"),
    path("payment-methods/<str:pm_id>/", PaymentMethodDetailView.as_view(), name="customer-payment-method-detail"),
]
