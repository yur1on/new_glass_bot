from django.core.management.base import BaseCommand
from bot.services.bot_runtime import build_runtime


class Command(BaseCommand):
    help = "Run Telegram bot (aiogram) inside Django project"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting bot..."))
        runner = build_runtime()
        runner()
