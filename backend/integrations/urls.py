# backend/integrations/urls.py
from django.urls import path

from integrations.views import (
    POSConnectionDetailView,
    POSSyncLogDetailView,
    POSSyncLogListView,
    RetryAllSyncView,
    RetryOrderSyncView,
)

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
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
]
