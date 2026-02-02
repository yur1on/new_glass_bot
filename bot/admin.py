from datetime import timedelta

from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from .models import User, Message, BlockedUser, SizeSearch


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "name", "city", "phone_number")
    search_fields = ("chat_id", "name", "city", "phone_number")
    list_filter = ("city",)
    ordering = ("chat_id",)


@admin.register(Message)
class MessageAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("chat_id", "short_text", "timestamp")
    search_fields = ("chat_id", "message_text")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)

    @admin.display(description="Message")
    def short_text(self, obj):
        return (obj.message_text or "")[:80]


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ("user_id",)
    search_fields = ("user_id",)
    ordering = ("user_id",)


@admin.register(SizeSearch)
class SizeSearchAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("chat_id", "height", "width", "found_count", "source", "timestamp", "stats_link")
    list_filter = ("source", "timestamp")
    search_fields = ("chat_id",)
    ordering = ("-timestamp",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "stats/",
                self.admin_site.admin_view(self.stats_view),
                name="size-search-stats",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Analytics")
    def stats_link(self, obj):
        url = reverse("admin:size-search-stats")
        return format_html('<a href="{}">📊 Stats</a>', url)

    def stats_view(self, request):
        last_7_days = timezone.now() - timedelta(days=7)
        last_30_days = timezone.now() - timedelta(days=30)

        context = dict(
            self.admin_site.each_context(request),

            total_users=User.objects.count(),
            total_size_searches=SizeSearch.objects.count(),
            searches_7_days=SizeSearch.objects.filter(timestamp__gte=last_7_days).count(),
            searches_30_days=SizeSearch.objects.filter(timestamp__gte=last_30_days).count(),

            sources=(
                SizeSearch.objects
                .values("source")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")
            ),

            top_sizes=(
                SizeSearch.objects
                .values("height", "width")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")[:15]
            ),
        )

        return render(request, "admin/size_search_stats.html", context)
