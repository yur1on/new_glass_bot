# premium/admin.py
from django.contrib import admin
from .models import PremiumPlan, PremiumSubscription, StarsPayment


@admin.register(PremiumPlan)
class PremiumPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "duration_days", "price_stars", "is_active", "created_at")
    list_filter = ("is_active", "duration_days")
    search_fields = ("code", "title")
    ordering = ("price_stars",)


@admin.register(PremiumSubscription)
class PremiumSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "active_until", "is_active", "updated_at")
    search_fields = ("chat_id",)
    ordering = ("-updated_at",)

    @admin.display(boolean=True)
    def is_active(self, obj: PremiumSubscription):
        return obj.is_active


@admin.register(StarsPayment)
class StarsPaymentAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "plan", "total_amount", "currency", "created_at")
    list_filter = ("currency", "created_at", "plan")
    search_fields = ("chat_id", "invoice_payload", "telegram_payment_charge_id")
    ordering = ("-created_at",)
