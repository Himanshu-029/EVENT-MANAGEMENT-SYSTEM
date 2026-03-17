from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('events/', views.event_list, name='event_list'),
    path('event/<int:id>/', views.event_detail, name='event_detail'),
    path('create/', views.create_event, name='create_event'),
    path('event/<int:id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:id>/delete/', views.delete_event, name='delete_event'),
    path('event/<int:id>/book/', views.book_event, name='book_event'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('verify-ticket/', views.verify_ticket, name='verify_ticket'),
    path('event/<int:id>/attendees/', views.event_attendees, name='event_attendees'),
    path('booking/<int:id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('accounts/register/', views.register, name='register'),
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/edit-profile/', views.edit_profile, name='edit_profile'),
    path('accounts/change-password/', views.change_password, name='change_password'),
    path('accounts/register/', views.register, name='register'),
    path('accounts/verify-otp/', views.verify_otp, name='verify_otp'),
    path('accounts/resend-otp/', views.resend_otp, name='resend_otp'),
    path('accounts/forgot-password/', views.forgot_password, name='forgot_password'),
    path('accounts/set-password/', views.otp_set_password, name='otp_set_password'),
    path('accounts/verify-email-change/', views.verify_email_change, name='verify_email_change'),

]