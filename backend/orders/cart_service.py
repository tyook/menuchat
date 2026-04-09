"""
Service layer for cart management.

Handles cart resolution (by user or session key), item CRUD,
and validation against the restaurant's active menu.
"""

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from orders.models import Cart, CartItem
from restaurants.models import MenuItem, MenuItemModifier, MenuItemVariant, Restaurant


class CartService:

    @staticmethod
    def get_or_create_cart(
        restaurant: Restaurant,
        user=None,
        session_key: str = "",
        table_identifier: str = "",
    ) -> Cart:
        """Resolve an existing cart or create a new one."""
        if user and user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(
                restaurant=restaurant,
                user=user,
                defaults={"table_identifier": table_identifier},
            )
        elif session_key:
            cart, _ = Cart.objects.get_or_create(
                restaurant=restaurant,
                session_key=session_key,
                defaults={"table_identifier": table_identifier},
            )
        else:
            raise ValidationError("Either authentication or a session key is required.")
        return cart

    @staticmethod
    def get_cart(restaurant: Restaurant, user=None, session_key: str = "") -> Cart:
        """Fetch an existing cart or raise NotFound."""
        filters = {"restaurant": restaurant}
        if user and user.is_authenticated:
            filters["user"] = user
        elif session_key:
            filters["session_key"] = session_key
        else:
            raise ValidationError("Either authentication or a session key is required.")

        try:
            return Cart.objects.prefetch_related(
                "items__menu_item", "items__variant", "items__modifiers"
            ).get(**filters)
        except Cart.DoesNotExist:
            raise NotFound("Cart not found.")

    @staticmethod
    def _validate_menu_item(restaurant: Restaurant, menu_item_id: int, variant_id: int):
        """Validate that the item and variant belong to the restaurant's active menu."""
        try:
            item = MenuItem.objects.select_related("category__version").get(
                id=menu_item_id,
                is_active=True,
                category__version__restaurant=restaurant,
                category__version__is_active=True,
            )
        except MenuItem.DoesNotExist:
            raise ValidationError(f"Menu item {menu_item_id} not found in this restaurant's active menu.")

        try:
            variant = MenuItemVariant.objects.get(id=variant_id, menu_item=item)
        except MenuItemVariant.DoesNotExist:
            raise ValidationError(f"Variant {variant_id} not found for menu item {menu_item_id}.")

        return item, variant

    @classmethod
    @transaction.atomic
    def add_item(
        cls,
        cart: Cart,
        menu_item_id: int,
        variant_id: int,
        quantity: int = 1,
        modifier_ids: list[int] | None = None,
        special_requests: str = "",
    ) -> CartItem:
        """Add an item to the cart, or increment quantity if it already exists."""
        item, variant = cls._validate_menu_item(cart.restaurant, menu_item_id, variant_id)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=item,
            variant=variant,
            defaults={"quantity": quantity, "special_requests": special_requests},
        )

        if not created:
            cart_item.quantity += quantity
            if special_requests:
                cart_item.special_requests = special_requests
            cart_item.save()

        if modifier_ids:
            modifiers = MenuItemModifier.objects.filter(id__in=modifier_ids, menu_item=item)
            cart_item.modifiers.set(modifiers)

        return cart_item

    @staticmethod
    def update_item_quantity(cart: Cart, cart_item_id: int, quantity: int) -> CartItem:
        """Update the quantity of a cart item."""
        try:
            cart_item = CartItem.objects.get(id=cart_item_id, cart=cart)
        except CartItem.DoesNotExist:
            raise NotFound("Cart item not found.")

        cart_item.quantity = quantity
        cart_item.save(update_fields=["quantity"])
        return cart_item

    @staticmethod
    def remove_item(cart: Cart, cart_item_id: int) -> None:
        """Remove an item from the cart."""
        deleted, _ = CartItem.objects.filter(id=cart_item_id, cart=cart).delete()
        if not deleted:
            raise NotFound("Cart item not found.")

    @staticmethod
    def clear_cart(cart: Cart) -> None:
        """Remove all items from the cart."""
        cart.items.all().delete()
