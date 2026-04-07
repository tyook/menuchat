# backend/integrations/urls.py
from django.urls import path

from integrations.views import (
    POSConnectionDetailView,
    POSConnectInitiateView,
    POSSyncLogDetailView,
    POSSyncLogListView,
    POSVendorSelectView,
    RetryAllSyncView,
    RetryOrderSyncView,
    SquareOAuthCallbackView,
    ToastMenuSyncView,
)

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
    ),
    path(
        "restaurants/<slug:slug>/pos/select-vendor/",
        POSVendorSelectView.as_view(),
        name="pos-vendor-select",
    ),
    path(
        "restaurants/<slug:slug>/pos/connect/",
        POSConnectInitiateView.as_view(),
        name="pos-connect-initiate",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/",
        POSSyncLogListView.as_view(),
        name="pos-sync-logs",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry-all/",
        RetryAllSyncView.as_view(),
        name="pos-retry-all",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry/<uuid:order_id>/",
        RetryOrderSyncView.as_view(),
        name="pos-retry-order",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/<uuid:log_id>/",
        POSSyncLogDetailView.as_view(),
        name="pos-sync-log-detail",
    ),
    path(
        "restaurants/<slug:slug>/pos/toast/sync-menu/",
        ToastMenuSyncView.as_view(),
        name="toast-menu-sync",
    ),
    path(
        "integrations/oauth/square/callback/",
        SquareOAuthCallbackView.as_view(),
        name="square-oauth-callback",
    ),
]
