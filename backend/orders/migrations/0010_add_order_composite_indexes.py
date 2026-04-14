from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_add_tab_payment_model"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["restaurant", "-created_at"],
                name="orders_rest_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["restaurant", "status", "confirmed_at"],
                name="orders_rest_status_conf_idx",
            ),
        ),
    ]
