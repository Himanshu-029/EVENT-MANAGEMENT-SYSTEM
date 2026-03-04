from django.contrib import admin
from .models import Event

admin.site.register(Event)

from .models import Booking
admin.site.register(Booking)