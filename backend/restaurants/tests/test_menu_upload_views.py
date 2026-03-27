import pytest
from decimal import Decimal
from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APIClient
from restaurants.models import MenuVersion, MenuCategory, MenuItem, MenuItemVariant
from restaurants.llm.schemas import ParsedMenu, ParsedMenuCategory, ParsedMenuItem, ParsedMenuVariant


@pytest.fixture
def owner(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    from restaurants.models import Restaurant
    return Restaurant.objects.create(name="Test Restaurant", slug="test-rest", owner=owner)


@pytest.fixture
def auth_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.mark.django_db
class TestMenuUploadParseView:
    def test_requires_auth(self, restaurant):
        client = APIClient()
        resp = client.post(f"/api/restaurants/{restaurant.slug}/menu/upload/parse/")
        assert resp.status_code == 401

    @patch("restaurants.views_menu_upload.MenuUploadService.parse_images")
    def test_parse_returns_menu(self, mock_parse, auth_client, restaurant):
        mock_parse.return_value = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile("menu.jpg", b"fake-image-data", content_type="image/jpeg")
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/upload/parse/",
            {"images": [image]},
            format="multipart",
        )
        assert resp.status_code == 200
        assert "categories" in resp.json()


@pytest.mark.django_db
class TestMenuUploadSaveView:
    def test_save_overwrite(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=True, source="manual"
        )
        data = {
            "menu": {
                "categories": [
                    {
                        "name": "Mains",
                        "items": [
                            {
                                "name": "Burger",
                                "description": "Beef",
                                "variants": [{"label": "Regular", "price": "12.00"}],
                            }
                        ],
                    }
                ]
            },
            "mode": "overwrite",
            "version_name": "New Menu",
        }
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/upload/save/",
            data,
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Menu"


@pytest.mark.django_db
class TestMenuVersionViews:
    def test_list_versions(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        resp = auth_client.get(f"/api/restaurants/{restaurant.slug}/menu/versions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_activate_version(self, auth_client, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="V2", is_active=False, source="manual"
        )
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v2.id}/activate/"
        )
        assert resp.status_code == 200
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True

    def test_rename_version(self, auth_client, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", source="manual"
        )
        resp = auth_client.patch(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert resp.status_code == 200
        v.refresh_from_db()
        assert v.name == "New Name"

    def test_delete_inactive_version(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="Active", is_active=True, source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=False, source="manual"
        )
        resp = auth_client.delete(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v2.id}/"
        )
        assert resp.status_code == 204

    def test_cannot_delete_active_version(self, auth_client, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Active", is_active=True, source="manual"
        )
        resp = auth_client.delete(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v.id}/"
        )
        assert resp.status_code == 400
