from typing import Optional, Tuple, List

from django.db.models import Prefetch

from panel.models import GlassAlias, GlassLine


def normalize_query(q: str) -> str:
    return (q or "").strip().lower()


def find_card_by_query(user_query: str) -> Optional[Tuple[List[str], str]]:
    """
    Возвращает:
      - lines: список строк для ответа
      - photo_filename: имя файла фото (может быть пустым)
    """
    q = normalize_query(user_query)
    if not q:
        return None

    alias = (
        GlassAlias.objects
        .select_related("card")
        .prefetch_related(Prefetch("card__lines", queryset=GlassLine.objects.order_by("sort_order", "id")))
        .filter(query=q)
        .first()
    )
    if not alias:
        return None

    card = alias.card
    lines = [ln.text for ln in card.lines.all()]
    photo = (card.photo_filename or "").strip()
    return lines, photo
