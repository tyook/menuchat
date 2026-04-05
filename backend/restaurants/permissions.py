from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import BasePermission

from restaurants.models import Restaurant, RestaurantStaff, Subscription


class IsRestaurantOwnerOrStaff(BasePermission):
    """
    Allow access if user is the restaurant owner or has a staff role.
    """

    def has_object_permission(self, request, view, obj):
        if obj.owner == request.user:
            return True
        return RestaurantStaff.objects.filter(user=request.user, restaurant=obj).exists()


class HasActiveSubscription(BasePermission):
    """
    Denies access when the restaurant's subscription is inactive.

    Allows access for statuses: trialing, active.
    Allows past_due with a 3-day grace period from when the period ended.
    Returns 403 for canceled, incomplete, or past_due beyond the grace window.
    """

    message = "Your subscription is inactive. Please visit billing to reactivate."
    GRACE_PERIOD_DAYS = 3

    def has_permission(self, request, view):
        slug = view.kwargs.get("slug")
        if slug is None:
            return True

        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return True  # Let the view handle 404

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return False

        if subscription.status in (Subscription.Status.TRIALING, Subscription.Status.ACTIVE):
            return True

        if subscription.status == Subscription.Status.PAST_DUE:
            grace_deadline = (subscription.current_period_end or timezone.now()) + timedelta(
                days=self.GRACE_PERIOD_DAYS
            )
            if timezone.now() <= grace_deadline:
                return True

        return False
