from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Tuple

from django import forms
from django.contrib import admin, messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import GlassCard, GlassAlias, GlassLine, GlassSize


# ---------- Forms ----------

class CatalogImportForm(forms.Form):
    file = forms.FileField(label="JSON file", required=True)
    clear_before_import = forms.BooleanField(label="Clear catalog before import", required=False, initial=False)


# ---------- Inlines ----------

class GlassAliasInline(admin.TabularInline):
    model = GlassAlias
    extra = 0


class GlassLineInline(admin.TabularInline):
    model = GlassLine
    extra = 0


# ---------- Helpers ----------

EXPORT_MODELS = [
    "panel.GlassCard",
    "panel.GlassLine",
    "panel.GlassAlias",
    "panel.GlassSize",
]


def _export_payload() -> dict:
    """
    Экспорт каталога стекол в portable JSON.
    """
    payload = {
        "exported_at": datetime.now().isoformat(),
        "format": "yur1on-glass-catalog-v1",
        "models": {
            "panel.GlassCard": [],
            "panel.GlassLine": [],
            "panel.GlassAlias": [],
            "panel.GlassSize": [],
        },
    }

    payload["models"]["panel.GlassCard"] = list(GlassCard.objects.all().order_by("id").values())
    payload["models"]["panel.GlassLine"] = list(GlassLine.objects.all().order_by("id").values())
    payload["models"]["panel.GlassAlias"] = list(GlassAlias.objects.all().order_by("id").values())
    payload["models"]["panel.GlassSize"] = list(GlassSize.objects.all().order_by("id").values())

    return payload


def _safe_lower(s: str) -> str:
    return (s or "").strip().lower()


# ---------- Admin ----------

@admin.register(GlassCard)
class GlassCardAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "photo_filename", "import_export_link")
    search_fields = ("title", "brand", "note")
    inlines = [GlassAliasInline, GlassLineInline]

    change_list_template = "admin/panel/glasscard/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-export/",
                self.admin_site.admin_view(self.import_export_view),
                name="panel_glasscard_import_export",
            ),
            path(
                "import-export/export/",
                self.admin_site.admin_view(self.export_view),
                name="panel_glasscard_export",
            ),
            path(
                "import-export/import/",
                self.admin_site.admin_view(self.import_view),
                name="panel_glasscard_import",
            ),
        ]
        return custom + urls

    @admin.display(description="Import/Export")
    def import_export_link(self, obj: GlassCard):
        url = reverse("admin:panel_glasscard_import_export")
        return format_html('<a href="{}">⬇️⬆️ Import/Export</a>', url)

    # ---------- Views ----------

    def import_export_view(self, request: HttpRequest):
        """
        Главная страница: кнопки Export и форма Import.
        """
        context = dict(
            self.admin_site.each_context(request),
            title="Glass catalog — Import / Export (JSON)",
            form=CatalogImportForm(),
            counts={
                "cards": GlassCard.objects.count(),
                "aliases": GlassAlias.objects.count(),
                "lines": GlassLine.objects.count(),
                "sizes": GlassSize.objects.count(),
            },
        )
        return TemplateResponse(request, "admin/glass_catalog_import_export.html", context)

    def export_view(self, request: HttpRequest):
        payload = _export_payload()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"glass_catalog_{ts}.json"
        content = json.dumps(payload, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)

        resp = HttpResponse(content, content_type="application/json; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @transaction.atomic
    def import_view(self, request: HttpRequest):
        if request.method != "POST":
            return redirect("admin:panel_glasscard_import_export")

        form = CatalogImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Форма некорректна. Проверь файл.")
            return redirect("admin:panel_glasscard_import_export")

        clear = form.cleaned_data["clear_before_import"]
        f = form.cleaned_data["file"]

        try:
            payload = json.loads(f.read().decode("utf-8"))
        except Exception:
            messages.error(request, "Не удалось прочитать JSON (проверь формат/кодировку UTF-8).")
            return redirect("admin:panel_glasscard_import_export")

        models: Dict[str, List[dict]] = payload.get("models", {})

        # ✅ Clear (если включено)
        if clear:
            GlassAlias.objects.all().delete()
            GlassLine.objects.all().delete()
            GlassSize.objects.all().delete()
            GlassCard.objects.all().delete()

        # --- Import cards first ---
        cards_rows = models.get("panel.GlassCard", [])
        card_id_map: Dict[int, int] = {}  # old_id -> new_id

        created_cards = 0
        updated_cards = 0

        for row in cards_rows:
            old_id = row.get("id")
            title = row.get("title", "")
            brand = row.get("brand", "")
            note = row.get("note", "")
            photo_filename = row.get("photo_filename", "")

            # ✅ Стабильный ключ: (title, brand, photo_filename) — можно поменять под тебя
            obj, created = GlassCard.objects.update_or_create(
                title=title,
                brand=brand,
                photo_filename=photo_filename,
                defaults={"note": note},
            )
            if created:
                created_cards += 1
            else:
                updated_cards += 1

            if old_id is not None:
                card_id_map[int(old_id)] = obj.id

        # --- Import lines ---
        lines_rows = models.get("panel.GlassLine", [])
        created_lines = 0

        for row in lines_rows:
            old_card_id = row.get("card_id")
            new_card_id = card_id_map.get(int(old_card_id)) if old_card_id is not None else None
            if not new_card_id:
                continue

            sort_order = row.get("sort_order", 0)
            text = row.get("text", "")

            # чтобы обновлялось, делаем upsert по (card_id, sort_order, text)
            obj, created = GlassLine.objects.get_or_create(
                card_id=new_card_id,
                sort_order=sort_order,
                text=text,
            )
            if created:
                created_lines += 1

        # --- Import aliases ---
        aliases_rows = models.get("panel.GlassAlias", [])
        created_aliases = 0
        skipped_aliases = 0

        for row in aliases_rows:
            old_card_id = row.get("card_id")
            new_card_id = card_id_map.get(int(old_card_id)) if old_card_id is not None else None
            if not new_card_id:
                continue

            query = _safe_lower(row.get("query", ""))
            if not query:
                continue

            # ✅ ВАЖНО: алиасы должны быть уникальны по query.
            # Поэтому: если такой query уже есть — обновим привязку к card (чтобы не падало UNIQUE constraint)
            obj, created = GlassAlias.objects.update_or_create(
                query=query,
                defaults={"card_id": new_card_id},
            )
            if created:
                created_aliases += 1
            else:
                skipped_aliases += 1

        # --- Import sizes ---
        sizes_rows = models.get("panel.GlassSize", [])
        created_sizes = 0
        updated_sizes = 0

        for row in sizes_rows:
            model_name = row.get("model_name", "")
            height = row.get("height")
            width = row.get("width")
            photo_path = row.get("photo_path", "")

            obj, created = GlassSize.objects.update_or_create(
                model_name=model_name,
                height=height,
                width=width,
                defaults={"photo_path": photo_path},
            )
            if created:
                created_sizes += 1
            else:
                updated_sizes += 1

        messages.success(
            request,
            "✅ Импорт завершён: "
            f"cards +{created_cards} (upd {updated_cards}), "
            f"lines +{created_lines}, "
            f"aliases +{created_aliases} (updated {skipped_aliases}), "
            f"sizes +{created_sizes} (upd {updated_sizes})"
        )
        return redirect("admin:panel_glasscard_import_export")


@admin.register(GlassAlias)
class GlassAliasAdmin(admin.ModelAdmin):
    list_display = ("query", "card")
    search_fields = ("query", "card__title", "card__brand")
    list_select_related = ("card",)


@admin.register(GlassLine)
class GlassLineAdmin(admin.ModelAdmin):
    list_display = ("card", "sort_order", "text")
    search_fields = ("text", "card__title", "card__brand")
    list_select_related = ("card",)
    ordering = ("card_id", "sort_order", "id")


@admin.register(GlassSize)
class GlassSizeAdmin(admin.ModelAdmin):
    list_display = ("model_name", "height", "width", "photo_path")
    search_fields = ("model_name",)
    list_filter = ("height", "width")
    ordering = ("model_name",)
