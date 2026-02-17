from django.contrib import admin
from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "auth_provider", "created_at"]
    search_fields = ["email", "name"]
    readonly_fields = ["id", "created_at", "updated_at"]
