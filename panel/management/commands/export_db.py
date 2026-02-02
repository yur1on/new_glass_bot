from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder


EXPORT_MODELS = [
    # panel (каталог)
    "panel.GlassCard",
    "panel.GlassLine",
    "panel.GlassAlias",
    "panel.GlassSize",
    # bot (пользователи/аналитика)
    "bot.User",
    "bot.Message",
    "bot.BlockedUser",
    "bot.SizeSearch",
]


class Command(BaseCommand):
    help = "Export selected DB models to portable JSON (for moving from sqlite -> postgres)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="data",
            help="Output directory (default: data)"
        )
        parser.add_argument(
            "--filename",
            default="",
            help="Optional output filename. If not set, auto backup_YYYYmmdd_HHMMSS.json"
        )

    def handle(self, *args, **options):
        out_dir = Path(options["out"]).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = options["filename"].strip()
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backup_{ts}.json"

        out_path = out_dir / filename

        payload = {"exported_at": datetime.now().isoformat(), "models": {}}

        total = 0
        for label in EXPORT_MODELS:
            app_label, model_name = label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            qs = model.objects.all().order_by("pk")
            rows = list(qs.values())
            payload["models"][label] = rows
            total += len(rows)

            self.stdout.write(f"{label}: {len(rows)}")

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"✅ Exported {total} rows to {out_path}"))
