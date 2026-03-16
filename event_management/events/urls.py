from django.urls import path
from . import views

urlpatterns = [
    path('', views.event_list, name='event_list'),
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
    path('', views.home, name='home'),

]