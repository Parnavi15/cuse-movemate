from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("listings", views.ListingViewSet, basename="listing")
router.register("transactions", views.TransactionViewSet, basename="transaction")

urlpatterns = [
    # auth + verified student identity
    path("auth/register/", views.register),
    path("auth/login/", views.login),
    path("auth/logout/", views.logout),
    path("auth/me/", views.me),
    path("auth/verify/request/", views.verify_request),
    path("auth/verify/confirm/", views.verify_confirm),

    # catalog + search
    path("categories/", views.categories),
    path("match/", views.smart_match),
    path("needs/", views.my_needs),

    # reviews
    path("reviews/", views.create_review),
    path("users/<int:user_id>/reviews/", views.user_reviews),

    # notifications
    path("notifications/", views.notifications),
    path("notifications/read-all/", views.notifications_read_all),
    path("notifications/<int:pk>/read/", views.notification_read),

    # wallet
    path("wallet/", views.wallet),
    path("wallet/ledger/", views.wallet_ledger),
    path("wallet/impact/", views.wallet_impact),
    path("wallet/redeem/", views.wallet_redeem),
    path("wallet/settle/", views.wallet_settle),

    # community
    path("leaderboard/", views.leaderboard),
    path("uploads/photo/", views.upload_photo),
    path("geo/reverse/", views.geo_reverse),
    path("geo/search/", views.geo_search),
    path("config/", views.config),
    path("stats/", views.campus_stats),

    path("", include(router.urls)),
]
