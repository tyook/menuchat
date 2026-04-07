import logging
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from integrations.adapters.base import BasePOSAdapter, PushResult
from integrations.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

TOAST_API_BASE_URL = "https://ws-sandbox-api.eng.toasttab.com"

# Substrings that must never appear in log output.
_SECRET_KEYS = ("clientSecret", "clientId", "accessToken", "token")


def _scrub_secrets(text: str) -> str:
    """Remove credential values from error text before logging."""
    for secret_attr in (
        getattr(settings, "POS_TOAST_CLIENT_SECRET", ""),
        getattr(settings, "POS_TOAST_CLIENT_ID", ""),
    ):
        if secret_attr:
            text = text.replace(secret_attr, "***")
    return text


class ToastAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = _scrub_secrets(message)
        super().__init__(f"Toast API error {status_code}: {self.message}")


class ToastAdapter(BasePOSAdapter):
    """Adapter for Toast POS integration.

    Uses Toast's machine client authentication (client credentials flow).
    The restaurant GUID is stored in ``connection.external_location_id``.
    """

    def _get_base_url(self) -> str:
        return getattr(settings, "POS_TOAST_API_BASE_URL", TOAST_API_BASE_URL)

    def _get_restaurant_guid(self) -> str:
        return self.connection.external_location_id or ""

    def _get_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Toast-Restaurant-External-ID": self._get_restaurant_guid(),
            "Content-Type": "application/json",
        }

    def _authenticate(self) -> str:
        """Authenticate with Toast API using client credentials.

        Returns the access token string.
        """
        url = f"{self._get_base_url()}/authentication/v1/authentication/login"
        payload = {
            "clientId": settings.POS_TOAST_CLIENT_ID,
            "clientSecret": settings.POS_TOAST_CLIENT_SECRET,
            "userAccessType": "TOAST_MACHINE_CLIENT",
        }
        start = time.monotonic()
        try:
            resp = requests.post(url, json=payload, timeout=30)
        except requests.RequestException:
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "Toast auth request failed",
                extra={
                    "event": "toast_auth_error",
                    "latency_ms": latency_ms,
                    "pos_type": "toast",
                    "restaurant_id": self._get_restaurant_guid(),
                },
            )
            raise
        latency_ms = round((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            logger.warning(
                "Toast auth failed",
                extra={
                    "event": "toast_auth_error",
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "pos_type": "toast",
                    "restaurant_id": self._get_restaurant_guid(),
                },
            )
            raise ToastAPIError(resp.status_code, resp.text)

        logger.info(
            "Toast auth success",
            extra={
                "event": "toast_auth_success",
                "latency_ms": latency_ms,
                "pos_type": "toast",
                "restaurant_id": self._get_restaurant_guid(),
            },
        )

        data = resp.json()
        token = data["token"]["accessToken"]
        expires_in = data["token"].get("expiresIn", 3600)

        self.connection.oauth_access_token = encrypt_token(token)
        self.connection.oauth_token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        self.connection.save(update_fields=["oauth_access_token", "oauth_token_expires_at"])
        return token

    def _get_valid_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        if (
            self.connection.oauth_access_token
            and self.connection.oauth_token_expires_at
            and self.connection.oauth_token_expires_at > timezone.now()
        ):
            return decrypt_token(self.connection.oauth_access_token)
        return self._authenticate()

    def _request(
        self, method: str, path: str, *, json: dict | None = None, retry_on_401: bool = True
    ) -> requests.Response:
        """Make an authenticated request to the Toast API with 401 retry."""
        token = self._get_valid_token()
        url = f"{self._get_base_url()}{path}"

        start = time.monotonic()
        try:
            resp = requests.request(method, url, headers=self._get_headers(token), json=json, timeout=30)
        except requests.RequestException:
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "Toast API request failed",
                extra={
                    "event": "toast_api_error",
                    "latency_ms": latency_ms,
                    "pos_type": "toast",
                    "restaurant_id": self._get_restaurant_guid(),
                },
            )
            raise

        if resp.status_code == 401 and retry_on_401:
            token = self._authenticate()
            start = time.monotonic()
            resp = requests.request(method, url, headers=self._get_headers(token), json=json, timeout=30)

        latency_ms = round((time.monotonic() - start) * 1000)
        extra = {
            "event": "toast_api_call",
            "method": method,
            "path": path.split("?")[0],
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "pos_type": "toast",
            "restaurant_id": self._get_restaurant_guid(),
        }

        if resp.status_code >= 400:
            extra["event"] = "toast_api_error"
            logger.warning("Toast API error", extra=extra)
            raise ToastAPIError(resp.status_code, resp.text)

        logger.info("Toast API call", extra=extra)
        return resp

    def get_menu_items(self) -> list[dict]:
        """Fetch current menu items from Toast, grouped by menu group.

        Returns a list of group dicts, each containing a name and items list:
        [{"group_name": "Appetizers", "items": [{"toast_guid": ..., "name": ..., ...}]}]
        """
        guid = self._get_restaurant_guid()
        resp = self._request("GET", f"/menus/v2/menus?restaurantGuid={guid}")
        menus = resp.json()

        groups = []
        for menu in menus:
            for group in menu.get("groups", []):
                group_items = []
                for item in group.get("items", []):
                    group_items.append(
                        {
                            "toast_guid": item.get("guid"),
                            "name": item.get("name", ""),
                            "price": item.get("price", 0),
                            "description": item.get("description", ""),
                        }
                    )
                if group_items:
                    groups.append(
                        {
                            "group_name": group.get("name", "Menu"),
                            "items": group_items,
                        }
                    )
        return groups

    def push_order(self, order) -> PushResult:
        guid = self._get_restaurant_guid()

        checks = []
        selections = []
        for item in order.items.select_related("variant", "menu_item").prefetch_related("modifiers"):
            selection = {
                "itemGroup": {"guid": None},
                "item": {"name": item.menu_item.name},
                "quantity": item.quantity,
                "price": float(item.variant.price),
                "modifiers": [
                    {
                        "modifier": {"name": mod.name},
                        "price": float(mod.price_adjustment),
                    }
                    for mod in item.modifiers.all()
                ],
            }
            selections.append(selection)

        check = {
            "selections": selections,
            "amount": float(order.total_price),
            "totalAmount": float(order.total_price),
            "taxAmount": float(order.tax_amount),
        }

        if self.connection.payment_mode == "stripe" and order.payment_status == "paid":
            check["payments"] = [
                {
                    "type": "OTHER",
                    "amount": float(order.total_price),
                    "tipAmount": 0,
                    "paymentStatus": "CAPTURED",
                }
            ]

        checks.append(check)

        payload = {
            "entityType": "Restaurant",
            "externalId": str(order.id),
            "revenueCenter": {"guid": None},
            "diningOption": {"behavior": "TAKE_OUT"},
            "checks": checks,
        }

        try:
            resp = self._request("POST", f"/orders/v2/orders?restaurantGuid={guid}", json=payload)
        except ToastAPIError as e:
            logger.warning(
                "Toast order push failed",
                extra={
                    "event": "toast_order_push_failed",
                    "order_id": str(order.id),
                    "restaurant_id": guid,
                    "status_code": e.status_code,
                    "pos_type": "toast",
                    "error": e.message,
                },
            )
            return PushResult(success=False, error_message=e.message)

        data = resp.json()
        external_id = data.get("guid", "")
        logger.info(
            "Toast order pushed",
            extra={
                "event": "toast_order_pushed",
                "order_id": str(order.id),
                "restaurant_id": guid,
                "pos_type": "toast",
            },
        )
        return PushResult(success=True, external_order_id=external_id)

    def get_order_status(self, external_order_id: str) -> str:
        guid = self._get_restaurant_guid()
        try:
            resp = self._request(
                "GET",
                f"/orders/v2/orders/{external_order_id}?restaurantGuid={guid}",
            )
            data = resp.json()
            return data.get("status", "unknown")
        except (ToastAPIError, Exception):
            return "unknown"

    def cancel_order(self, external_order_id: str) -> bool:
        guid = self._get_restaurant_guid()
        try:
            self._request(
                "PATCH",
                f"/orders/v2/orders/{external_order_id}?restaurantGuid={guid}",
                json={"status": "CANCELLED"},
            )
            return True
        except (ToastAPIError, Exception):
            logger.error(
                "Failed to cancel Toast order",
                extra={
                    "event": "toast_cancel_failed",
                    "order_id": external_order_id,
                    "restaurant_id": guid,
                    "pos_type": "toast",
                },
            )
            return False

    def validate_connection(self) -> bool:
        try:
            self._get_valid_token()
            return True
        except Exception:
            return False

    def refresh_tokens(self) -> bool:
        """Toast uses short-lived machine tokens; re-authenticate."""
        try:
            self._authenticate()
            return True
        except Exception:
            logger.error(
                "Failed to refresh Toast token",
                extra={
                    "event": "toast_token_refresh_failed",
                    "restaurant_id": self._get_restaurant_guid(),
                    "pos_type": "toast",
                },
            )
            return False
