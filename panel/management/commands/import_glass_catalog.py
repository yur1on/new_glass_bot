from django.core.management.base import BaseCommand
from django.db import transaction

from panel.models import GlassCard, GlassAlias, GlassLine, GlassSize


def normalize(q: str) -> str:
    return (q or "").strip().lower()


class Command(BaseCommand):
    help = "Import glass catalog from baza.py / baza2.py into DB (cards + aliases + lines + sizes)"

    @transaction.atomic
    def handle(self, *args, **options):
        # импортируем данные
        from bot.data_sources.baza import (
            glass_data, glass_data2, glass_data3, glass_data4,
            glass_data5, glass_data6, glass_data7
        )
        from bot.data_sources.baza2 import glass_data9

        # 0) очищаем старое (идемпотентный импорт)
        GlassAlias.objects.all().delete()
        GlassLine.objects.all().delete()
        GlassCard.objects.all().delete()

        datasets = [glass_data, glass_data2, glass_data3, glass_data4, glass_data5, glass_data6, glass_data7]

        # Группировка: одинаковые lines + photo => одна карточка
        # key = (tuple(lines), photo)
        card_map: dict[tuple[tuple[str, ...], str], GlassCard] = {}

        def split_items(items):
            """
            items: список строк. В конце может быть 'xxx.png' (но не обязательно).
            Возвращает (lines, photo_filename)
            """
            photo = ""
            lines = []
            for x in (items or []):
                if isinstance(x, str) and x.lower().endswith(".png"):
                    photo = x.strip()
                else:
                    if x is None:
                        continue
                    s = str(x).strip()
                    if s:
                        lines.append(s)
            return tuple(lines), photo

        created_cards = 0
        created_aliases = 0
        created_lines = 0
        alias_conflicts = 0
        alias_duplicates = 0

        # 1) импорт "каталога"
        for dataset in datasets:
            for model, items in dataset:
                alias = normalize(model)
                if not alias:
                    continue

                lines_key, photo = split_items(items)
                key = (lines_key, photo)

                card = card_map.get(key)
                if not card:
                    # создаем новую карточку
                    title = f"Card #{len(card_map) + 1}"
                    card = GlassCard.objects.create(
                        title=title,
                        photo_filename=photo or "",
                    )
                    created_cards += 1

                    # строки ответа
                    for idx, line in enumerate(lines_key):
                        GlassLine.objects.create(card=card, text=line, sort_order=idx)
                        created_lines += 1

                    card_map[key] = card

                # алиас уникален по query:
                # если уже существует — не падаем, а считаем конфликт/дубликат
                obj, created = GlassAlias.objects.get_or_create(
                    query=alias,
                    defaults={"card": card}
                )
                if created:
                    created_aliases += 1
                else:
                    # алиас уже был создан ранее
                    alias_duplicates += 1
                    if obj.card_id != card.id:
                        # тот же алиас указывает на другую карточку — конфликт данных
                        alias_conflicts += 1
                        # мы НЕ меняем привязку (оставляем первую)
                        # если хочешь "последний победил", то раскомментируй:
                        # obj.card = card
                        # obj.save(update_fields=["card"])

        # 2) импорт размеров (baza2 / glass_data9)
        # (перезаливаем полностью — проще и чище)
        GlassSize.objects.all().delete()
        created_sizes = 0
        skipped_sizes = 0

        for row in glass_data9:
            try:
                model_name = str(row.get("model", "")).strip()
                height = str(row.get("height", "")).replace(",", ".").strip()
                width = str(row.get("width", "")).replace(",", ".").strip()
                photo_path = str(row.get("photo_path", "")).strip()

                if not model_name or not height or not width:
                    skipped_sizes += 1
                    continue

                GlassSize.objects.create(
                    model_name=model_name,
                    height=height,
                    width=width,
                    photo_path=photo_path,
                )
                created_sizes += 1
            except Exception:
                skipped_sizes += 1
                continue

        self.stdout.write(self.style.SUCCESS(
            "Import finished successfully."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Cards created: {created_cards}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Lines created: {created_lines}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Aliases created: {created_aliases}"
        ))
        self.stdout.write(self.style.WARNING(
            f"Alias duplicates skipped: {alias_duplicates}"
        ))
        self.stdout.write(self.style.WARNING(
            f"Alias conflicts (same query, different card): {alias_conflicts}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Sizes created: {created_sizes} (skipped: {skipped_sizes})"
        ))
