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

    STATUS_ACTIVE   = 'active'
    STATUS_FINISHED = 'finished'
    STATUS_CHOICES  = [
        ('active',   'Active'),
        ('finished', 'Finished'),
    ]

    title        = models.CharField(max_length=200)
    description  = models.TextField()
    location     = models.CharField(max_length=200)
    date         = models.DateTimeField()
    capacity     = models.IntegerField()
    created_by   = models.ForeignKey(User, on_delete=models.CASCADE)
    image        = models.ImageField(upload_to='event_images/', blank=True, null=True)
    category     = models.CharField(max_length=100)
    latitude     = models.FloatField(null=True, blank=True)
    longitude    = models.FloatField(null=True, blank=True)

    # Publishing & lifecycle
    is_published     = models.BooleanField(default=False)
    terms_accepted   = models.BooleanField(default=False)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    finished_at      = models.DateTimeField(null=True, blank=True)
    cleanup_after    = models.DateTimeField(null=True, blank=True)  # auto-delete date (7 days post finish)

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

    @property
    def total_revenue(self):
        from django.db.models import Sum
        result = self.booking_set.aggregate(total=Sum('price'))['total']
        return result or 0

    @property
    def platform_fee(self):
        """Auto commission (fee/charge): 5% up to ₹1L, 10% above."""
        rev = self.total_revenue
        if rev <= 0:
            return 0
        return rev * 10 / 100 if rev > 100000 else rev * 5 / 100

    @property
    def organizer_payout(self):
        """What the organizer receives after platform fee deduction."""
        return self.total_revenue - self.platform_fee

    @property
    def is_free_event(self):
        return all(tier.is_free for tier in self.ticket_tiers.all())


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
    PAYMENT_STATUS = [
        ('pending',   'Pending'),
        ('paid',      'Paid'),
        ('failed',    'Failed'),
        ('refunded',  'Refunded'),
    ]

    event            = models.ForeignKey(Event, on_delete=models.CASCADE)
    user             = models.ForeignKey(User, on_delete=models.CASCADE)
    ticket_tier      = models.ForeignKey(TicketTier, on_delete=models.SET_NULL, null=True, blank=True)
    ticket_type      = models.CharField(max_length=100, default='General')
    price            = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    booked_at        = models.DateTimeField(auto_now_add=True)
    qr_code          = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_used          = models.BooleanField(default=False)

    # Razorpay payment fields
    payment_status   = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    razorpay_order_id   = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

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
# WAITLIST
# ══════════════════════════════════════
class Waitlist(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    event    = models.ForeignKey(Event, on_delete=models.CASCADE)
    joined_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'event']

    def __str__(self):
        return f"{self.user.username} waiting for {self.event.title}"




# ══════════════════════════════════════
# ORGANIZER PAYOUT DETAILS
# ══════════════════════════════════════
class OrganizerPayout(models.Model):
    """Stores sensitive (confidential/private) banking details per event."""
    event               = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='payout_details')
    upi_id              = models.CharField(max_length=100, blank=True)
    account_holder_name = models.CharField(max_length=200, blank=True)
    account_number      = models.CharField(max_length=20, blank=True)
    ifsc_code           = models.CharField(max_length=11, blank=True)
    bank_name           = models.CharField(max_length=100, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payout — {self.event.title}"


# ══════════════════════════════════════
# COMMISSION RECORD
# ══════════════════════════════════════
class CommissionRecord(models.Model):
    """Tracks (records/monitors) platform fee per event automatically."""
    event            = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='commission')
    total_revenue    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate  = models.DecimalField(max_digits=5, decimal_places=2, default=5)  # percentage
    commission_amount= models.DecimalField(max_digits=12, decimal_places=2, default=0)
    organizer_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    calculated_at    = models.DateTimeField(auto_now=True)
    is_settled       = models.BooleanField(default=False)

    def recalculate(self):
        """Recompute (recalculate/refresh) commission based on latest revenue."""
        rev = self.event.total_revenue
        rate = 10 if rev > 100000 else 5
        fee  = rev * rate / 100
        self.total_revenue    = rev
        self.commission_rate  = rate
        self.commission_amount= fee
        self.organizer_payout = rev - fee
        self.save()

    def __str__(self):
        return f"Commission — {self.event.title} ({self.commission_rate}%)"


# ══════════════════════════════════════
# TERMS ACCEPTANCE
# ══════════════════════════════════════
class TermsAcceptance(models.Model):
    """Immutable (permanent/unchangeable) record of T&C acceptance per event."""
    event       = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='terms_record')
    accepted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"T&C — {self.event.title} by {self.accepted_by.username}"


# ══════════════════════════════════════
# EVENT MODERATOR
# ══════════════════════════════════════
class EventModerator(models.Model):
    """Assigns auxiliary (helper/secondary) moderators to an event."""
    PERMISSION_CHOICES = [
        ('view_attendees', 'View Attendees'),
        ('edit_event',     'Edit Event'),
        ('check_in',       'Check In Attendees'),
    ]

    event       = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='moderators')
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_moderators')
    can_edit        = models.BooleanField(default=False)
    can_view_attendees = models.BooleanField(default=True)
    can_check_in    = models.BooleanField(default=True)
    assigned_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'user']

    def __str__(self):
        return f"{self.user.username} → moderator of {self.event.title}"


# ══════════════════════════════════════
# EVENT REPORT (post-event)
# ══════════════════════════════════════
class EventReport(models.Model):
    """Auto-generated (automatically created) report after event finishes."""
    event             = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='report')
    generated_at      = models.DateTimeField(auto_now_add=True)
    total_tickets_sold= models.IntegerField(default=0)
    total_revenue     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    organizer_payout  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    report_file       = models.FileField(upload_to='event_reports/', blank=True, null=True)
    email_sent        = models.BooleanField(default=False)

    def __str__(self):
        return f"Report — {self.event.title}"


# ══════════════════════════════════════
# USER PROFILE
# ══════════════════════════════════════
class UserProfile(models.Model):
    user                 = models.OneToOneField(User, on_delete=models.CASCADE)
    bio                  = models.TextField(blank=True, null=True, max_length=300)
    mobile               = models.CharField(max_length=15, blank=True, null=True)
    profile_picture      = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location             = models.CharField(max_length=100, blank=True, null=True)
    is_email_verified    = models.BooleanField(default=False)
    # New fields
    is_verified_organizer = models.BooleanField(default=False)  # Super Admin grants this badge
    is_super_admin        = models.BooleanField(default=False)  # Platform-wide admin

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