# premium/models.py
from django.db import models
from django.utils import timezone


class PremiumPlan(models.Model):
    """
    Тариф премиума. Можно сделать несколько (например 7/30/90 дней).
    """
    code = models.SlugField(unique=True)  # например: "premium_30"
    title = models.CharField(max_length=120, default="Premium")
    duration_days = models.PositiveIntegerField(default=30)
    price_stars = models.PositiveIntegerField(default=100)  # сколько Stars

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("price_stars",)

    def __str__(self) -> str:
        return f"{self.title} ({self.duration_days}d) - {self.price_stars}⭐"


class PremiumSubscription(models.Model):
    """
    Текущий премиум статус пользователя.
    """
    chat_id = models.BigIntegerField(db_index=True, unique=True)
    active_until = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.chat_id} -> {self.active_until}"

    @property
    def is_active(self) -> bool:
        return bool(self.active_until and self.active_until >= timezone.now())


class StarsPayment(models.Model):
    """
    Логи платежей Stars.
    """
    chat_id = models.BigIntegerField(db_index=True)

    plan = models.ForeignKey(PremiumPlan, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_payload = models.CharField(max_length=255, unique=True)

    currency = models.CharField(max_length=8, default="XTR")
    total_amount = models.PositiveIntegerField(default=0)  # в Stars для XTR

    telegram_payment_charge_id = models.CharField(max_length=255, blank=True, default="")
    provider_payment_charge_id = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.chat_id} {self.total_amount}{self.currency} {self.created_at:%Y-%m-%d}"
