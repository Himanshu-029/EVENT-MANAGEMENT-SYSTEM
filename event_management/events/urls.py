from django.urls import path
from . import views

urlpatterns = [
    # ── HOME ──
    path('', views.home, name='home'),

    # ── EVENTS ──
    path('events/', views.event_list, name='event_list'),
    path('event/<int:id>/', views.event_detail, name='event_detail'),
    path('create/', views.create_event, name='create_event'),
    path('event/<int:id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:id>/delete/', views.delete_event, name='delete_event'),
    path('event/<int:id>/book/', views.book_event, name='book_event'),
    path('event/<int:id>/attendees/', views.event_attendees, name='event_attendees'),
    path('event/<int:id>/availability/', views.tier_availability, name='tier_availability'),
    path('event/<int:id>/save/', views.toggle_save_event, name='toggle_save_event'),

    # ── BOOKINGS ──
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('saved-events/', views.saved_events, name='saved_events'),

    # ── ADMIN ──
    path('dashboard/', views.dashboard, name='dashboard'),
    path('verify-ticket/', views.verify_ticket, name='verify_ticket'),

    # ── AUTH ──
    path('accounts/register/', views.register, name='register'),
    path('accounts/verify-otp/', views.verify_otp, name='verify_otp'),
    path('accounts/resend-otp/', views.resend_otp, name='resend_otp'),
    path('accounts/forgot-password/', views.forgot_password, name='forgot_password'),
    path('accounts/set-password/', views.otp_set_password, name='otp_set_password'),

    # ── PROFILE ──
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/edit-profile/', views.edit_profile, name='edit_profile'),
    path('accounts/change-password/', views.change_password, name='change_password'),
    path('accounts/verify-email-change/', views.verify_email_change, name='verify_email_change'),

    # --- Admin ---
    path('super-admin/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('super-admin/toggle-verified/<int:user_id>/', views.toggle_verified_organizer, name='toggle_verified_organizer'),
    path('event/<int:event_id>/assign-moderator/', views.assign_moderator, name='assign_moderator'),

    # --- Razor Pay ---
    path('event/<int:id>/create-order/', views.create_razorpay_order, name='create_razorpay_order'),
    path('event/<int:id>/verify-payment/', views.verify_payment, name='verify_payment'),

    path('event/<int:id>/finish/', views.finish_event, name='finish_event'),
    path('finished-events/', views.finished_events, name='finished_events'),
    path('admin/cleanup/', views.trigger_cleanup, name='trigger_cleanup'),

]