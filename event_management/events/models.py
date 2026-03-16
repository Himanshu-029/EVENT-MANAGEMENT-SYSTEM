from django.db import models
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
from django.core.files import File


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    date = models.DateTimeField()
    capacity = models.IntegerField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='event_images/', blank=True, null=True)

    CATEGORY_CHOICES = [
        ('Tech', 'Tech'),
        ('Music', 'Music'),
        ('Sports', 'Sports'),
        ('Business', 'Business'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Tech')

    def __str__(self):
        return self.title
    
class Booking(models.Model):
    TICKET_CHOICES = [
        ('Regular', 'Regular'),
        ('VIP', 'VIP'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticket_type = models.CharField(max_length=20, choices=TICKET_CHOICES, default='Regular')
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    booked_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.ticket_type})"