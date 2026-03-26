from django.core.mail import send_mail
from django.conf import settings


def send_payout_completed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} deposited — {restaurant.name}",
        message=(
            f"Your daily payout of ${amount} has been deposited to your bank account.\n\n"
            f"View details in your Stripe Dashboard."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )


def send_payout_failed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} failed — {restaurant.name}",
        message=(
            f"Your payout of ${amount} failed. Please check your bank details "
            f"in the Stripe Dashboard and contact support if the issue persists."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )
