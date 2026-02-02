from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from django import forms
from django.apps import apps
from django.contrib import messages
from django.contrib.admin import AdminSite
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path


EXPORT_MODELS = [
    "panel.GlassCard",
    "panel.GlassLine",
    "panel.GlassAlias",
    "panel.GlassSize",
    "bot.User",
    "bot.Message",
    "bot.BlockedUser",
    "bot.SizeSearch",
]

IMPORT_ORDER = EXPORT_MODELS[:]  # порядок важен


class BackupImportForm(forms.Form):
    file = forms.FileField(label="JSON backup file", required=True)
    clear_before_import = forms.BooleanField(label="Clear before import", required=False, initial=True)


class BackupAdminSite(AdminSite):
    site_header = "Yur1on Platform Admin"
    site_title = "Yur1on Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("backup/", self.admin_view(self.backup_view), name="backup-tools"),
            path("backup/export/", self.admin_view(self.backup_export), name="backup-export"),
            path("backup/import/", self.admin_view(self.backup_import), name="backup-import"),
        ]
        return my_urls + urls

    def backup_view(self, request):
        context = dict(
            self.each_context(request),
            title="Backup / Restore",
            form=BackupImportForm(),
            export_models=EXPORT_MODELS,
        )
        return TemplateResponse(request, "admin/backup_tools.html", context)

    def _build_payload(self) -> dict:
        payload = {"exported_at": datetime.now().isoformat(), "models": {}}
        for label in EXPORT_MODELS:
            app_label, model_name = label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            payload["models"][label] = list(model.objects.all().order_by("pk").values())
        return payload

    def backup_export(self, request):
        payload = self._build_payload()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{ts}.json"

        content = json.dumps(payload, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
        resp = HttpResponse(content, content_type="application/json; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @transaction.atomic
    def backup_import(self, request):
        if request.method != "POST":
            messages.error(request, "Invalid request method.")
            return self.backup_view(request)

        form = BackupImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Форма некорректна. Проверь файл.")
            return self.backup_view(request)

        f = form.cleaned_data["file"]
        clear = form.cleaned_data["clear_before_import"]

        try:
            payload = json.loads(f.read().decode("utf-8"))
        except Exception:
            messages.error(request, "Не удалось прочитать JSON (проверь формат/кодировку).")
            return self.backup_view(request)

        models_data: Dict[str, List[dict]] = payload.get("models", {})

        if clear:
            for label in reversed(IMPORT_ORDER):
                app_label, model_name = label.split(".", 1)
                model = apps.get_model(app_label, model_name)
                model.objects.all().delete()

        total = 0
        for label in IMPORT_ORDER:
            rows = models_data.get(label, [])
            if not rows:
                continue

            app_label, model_name = label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            objs = [model(**row) for row in rows]
            model.objects.bulk_create(objs, ignore_conflicts=True)
            total += len(objs)

        messages.success(request, f"✅ Импорт завершён. Загружено строк: {total}")
        return self.backup_view(request)


admin_site = BackupAdminSite(name="admin")
