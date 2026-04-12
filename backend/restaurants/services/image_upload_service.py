"""
ImageUploadService — uploads images to Firebase Storage and returns public URLs.
"""

import logging
import uuid

import firebase_admin
from firebase_admin import credentials, storage
from django.conf import settings

logger = logging.getLogger(__name__)


def _ensure_firebase_initialized():
    """Initialize Firebase if not already done (notifications module may have done it)."""
    if not firebase_admin._apps:
        if settings.FIREBASE_CREDENTIALS:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
        else:
            raise RuntimeError("FIREBASE_CREDENTIALS not configured.")


class ImageUploadService:
    @staticmethod
    def upload_menu_item_image(
        restaurant_slug: str,
        image_file,
    ) -> str:
        """
        Upload a menu item image to Firebase Storage.

        Args:
            restaurant_slug: Used to namespace the file path.
            image_file: Django UploadedFile (has .read(), .content_type, .name).

        Returns:
            The public URL of the uploaded image.

        Raises:
            RuntimeError: If Firebase Storage is not configured.
        """
        bucket_name = settings.FIREBASE_STORAGE_BUCKET
        if not bucket_name:
            raise RuntimeError(
                "FIREBASE_STORAGE_BUCKET is not configured. "
                "Set it in your environment variables."
            )

        _ensure_firebase_initialized()

        ext = image_file.name.rsplit(".", 1)[-1].lower() if "." in image_file.name else "jpg"
        filename = f"{uuid.uuid4().hex}.{ext}"
        blob_path = f"menu-images/{restaurant_slug}/{filename}"

        bucket = storage.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Ensure file position is at the start
        image_file.seek(0)

        blob.upload_from_file(
            image_file,
            content_type=image_file.content_type or "image/jpeg",
        )
        blob.make_public()

        return blob.public_url
