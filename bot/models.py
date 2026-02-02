from django.db import models


class User(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    name = models.TextField(null=True, blank=True)
    city = models.TextField(null=True, blank=True)
    phone_number = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return f"{self.chat_id} | {self.name or ''}".strip()


class Message(models.Model):
    chat_id = models.BigIntegerField()
    message_text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"

    def __str__(self) -> str:
        return f"{self.chat_id}: {self.message_text[:40]}"


class BlockedUser(models.Model):
    user_id = models.BigIntegerField(primary_key=True)

    class Meta:
        db_table = "blocked_users"

    def __str__(self) -> str:
        return str(self.user_id)


class SizeSearch(models.Model):
    chat_id = models.BigIntegerField()
    height = models.FloatField()
    width = models.FloatField()
    found_count = models.IntegerField()
    source = models.TextField(default="unknown")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "size_searches"

    def __str__(self) -> str:
        return f"{self.chat_id}: {self.height}x{self.width} -> {self.found_count} ({self.source})"
