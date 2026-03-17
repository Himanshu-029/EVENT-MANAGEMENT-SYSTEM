from django.db import models
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
from django.core.files import File
from django.db.models.signals import post_save
from django.dispatch import receiver



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


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True, max_length=300)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"


# Auto create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()


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
    


# ---------OTP VERIFICATION-----------
    

import random
from django.utils import timezone
from datetime import timedelta

class OTPVerification(models.Model):
    OTP_TYPES = [
        ('email_verify', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('email_change', 'Email Change'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # OTP valid for 10 minutes
        return not self.is_used and (timezone.now() < self.created_at + timedelta(minutes=10))

    def __str__(self):
        return f"{self.user.username} - {self.otp_type} - {self.otp}"

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))