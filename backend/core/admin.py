from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (Badge, Category, Listing, Message, NeedRequest,
                     Notification, PointEntry, Redemption, Review,
                     Transaction, User, UserBadge, Wallet)


@admin.register(User)
class MoveMateUserAdmin(UserAdmin):
    list_display = ("username", "campus_email", "is_verified_student", "rating_avg", "school")
    fieldsets = UserAdmin.fieldsets + (
        ("MoveMate", {"fields": ("campus_email", "is_verified_student", "school",
                                 "avatar_emoji", "bio", "latitude", "longitude",
                                 "address_label", "rating_avg", "rating_count")}),
    )


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "mode", "price_cents", "status", "pickup_deadline")
    list_filter = ("mode", "status", "category", "condition")
    search_fields = ("title", "description")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("listing", "owner", "claimant", "state", "created_at")
    list_filter = ("state", "mode")


@admin.register(PointEntry)
class PointEntryAdmin(admin.ModelAdmin):
    list_display = ("wallet", "rule", "points", "status", "posts_at")
    list_filter = ("rule", "status")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "read_at", "emailed", "created_at")
    list_filter = ("kind", "emailed")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("transaction", "sender", "body", "created_at")
    search_fields = ("body",)


admin.site.register([Category, Wallet, Review, Redemption, Badge, UserBadge, NeedRequest])
admin.site.site_header = "Cuse-MoveMate admin"
