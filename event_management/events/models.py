from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import random


# ══════════════════════════════════════
# EVENT
# ══════════════════════════════════════
class Event(models.Model):
    PRESET_CATEGORIES = ['Tech', 'Music', 'Sports', 'Business']

    title       = models.CharField(max_length=200)
    description = models.TextField()
    location    = models.CharField(max_length=200)
    date        = models.DateTimeField()
    capacity    = models.IntegerField()
    created_by  = models.ForeignKey(User, on_delete=models.CASCADE)
    image       = models.ImageField(upload_to='event_images/', blank=True, null=True)
    category    = models.CharField(max_length=100)
    latitude  = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.title

    @property
    def total_booked(self):
        return self.booking_set.count()

    @property
    def seats_left(self):
        return self.capacity - self.total_booked

    @property
    def save_count(self):
        return self.savedevent_set.count()


# ══════════════════════════════════════
# TICKET TIER
# ══════════════════════════════════════
class TicketTier(models.Model):
    event    = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_tiers')
    name     = models.CharField(max_length=100)
    price    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    capacity = models.IntegerField(default=0)  # 0 = no tier limit

    def __str__(self):
        return f"{self.event.title} — {self.name} (Rs.{self.price})"

    @property
    def is_free(self):
        return self.price == 0

    @property
    def booked_count(self):
        return self.booking_set.count()

    @property
    def seats_left(self):
        if self.capacity == 0:
            return self.event.seats_left
        return max(0, self.capacity - self.booked_count)

    @property
    def is_sold_out(self):
        return self.seats_left == 0


# ══════════════════════════════════════
# BOOKING
# ══════════════════════════════════════
class Booking(models.Model):
    event       = models.ForeignKey(Event, on_delete=models.CASCADE)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    ticket_tier = models.ForeignKey(TicketTier, on_delete=models.SET_NULL, null=True, blank=True)
    ticket_type = models.CharField(max_length=100, default='General')
    price       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    booked_at   = models.DateTimeField(auto_now_add=True)
    qr_code     = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_used     = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} — {self.event.title} ({self.ticket_type})"


# ══════════════════════════════════════
# SAVED EVENT (Interested)
# ══════════════════════════════════════
class SavedEvent(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    event    = models.ForeignKey(Event, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'event']

    def __str__(self):
        return f"{self.user.username} saved {self.event.title}"


# ══════════════════════════════════════
# USER PROFILE
# ══════════════════════════════════════
class UserProfile(models.Model):
    user              = models.OneToOneField(User, on_delete=models.CASCADE)
    bio               = models.TextField(blank=True, null=True, max_length=300)
    mobile            = models.CharField(max_length=15, blank=True, null=True)
    profile_picture   = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location          = models.CharField(max_length=100, blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()


# ══════════════════════════════════════
# OTP VERIFICATION
# ══════════════════════════════════════
class OTPVerification(models.Model):
    OTP_TYPES = [
        ('email_verify',   'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('email_change',   'Email Change'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    otp        = models.CharField(max_length=6)
    otp_type   = models.CharField(max_length=20, choices=OTP_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and (
            timezone.now() < self.created_at + timedelta(minutes=10)
        )

    def __str__(self):
        return f"{self.user.username} - {self.otp_type} - {self.otp}"

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))