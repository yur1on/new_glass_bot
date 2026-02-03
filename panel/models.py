from django.db import models


class GlassCard(models.Model):
    """
    Одна карточка: список взаимозаменяемых моделей + фото.
    """
    title = models.CharField(max_length=255, unique=True)  # например "Samsung A50 group"
    brand = models.CharField(max_length=100, blank=True, default="")
    note = models.TextField(blank=True, default="")
    photo_filename = models.CharField(max_length=255, blank=True, default="")  # "samsung a50.png"

    class Meta:
        ordering = ("title",)

    def __str__(self):
        return self.title


class GlassAlias(models.Model):
    """
    Алиас/ключ запроса: то, что вводит пользователь.
    """
    query = models.CharField(max_length=255, unique=True, db_index=True)  # "a50", "samsung a505"
    card = models.ForeignKey(GlassCard, on_delete=models.CASCADE, related_name="aliases")

    class Meta:
        ordering = ("query",)

    def __str__(self):
        return self.query


class GlassLine(models.Model):
    """
    Строки ответа в карточке.
    """
    card = models.ForeignKey(GlassCard, on_delete=models.CASCADE, related_name="lines")
    text = models.CharField(max_length=500)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.card.title}: {self.text[:50]}"


class GlassSize(models.Model):
    model_name = models.CharField(max_length=255)
    height = models.DecimalField(max_digits=7, decimal_places=2, db_index=True)
    width = models.DecimalField(max_digits=7, decimal_places=2, db_index=True)
    photo_path = models.CharField(max_length=1024, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["height", "width"])]

    def __str__(self):
        return f"{self.model_name} {self.height}x{self.width}"
