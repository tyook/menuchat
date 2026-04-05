from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_merge_20260327_0809"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
