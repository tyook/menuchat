import pytest
from rest_framework import status

from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemModifierFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestPublicMenu:
    def test_get_menu_no_auth_required(self, api_client):
        restaurant = RestaurantFactory(slug="public-test")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version, name="Mains")
        item = MenuItemFactory(category=cat, name="Burger")
        MenuItemVariantFactory(menu_item=item, label="Regular", price="10.99")
        MenuItemModifierFactory(menu_item=item, name="Extra Cheese")

        response = api_client.get("/api/order/public-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["categories"]) == 1
        assert response.data["categories"][0]["name"] == "Mains"
        assert len(response.data["categories"][0]["items"]) == 1

    def test_inactive_items_excluded(self, api_client):
        restaurant = RestaurantFactory(slug="inactive-test")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        MenuItemFactory(category=cat, is_active=True)
        MenuItemFactory(category=cat, is_active=False)

        response = api_client.get("/api/order/inactive-test/menu/")
        assert len(response.data["categories"][0]["items"]) == 1

    def test_nonexistent_restaurant_returns_404(self, api_client):
        response = api_client.get("/api/order/nonexistent/menu/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPublicMenuPaymentModel:
    def test_menu_includes_payment_model(self, api_client):
        restaurant = RestaurantFactory(slug="menu-pm-test", payment_model="tab")
        MenuVersionFactory(restaurant=restaurant, is_active=True)
        response = api_client.get("/api/order/menu-pm-test/menu/")
        assert response.status_code == 200
        assert response.data["payment_model"] == "tab"

    def test_menu_default_payment_model_is_upfront(self, api_client):
        restaurant = RestaurantFactory(slug="menu-pm-default")
        MenuVersionFactory(restaurant=restaurant, is_active=True)
        response = api_client.get("/api/order/menu-pm-default/menu/")
        assert response.status_code == 200
        assert response.data["payment_model"] == "upfront"
