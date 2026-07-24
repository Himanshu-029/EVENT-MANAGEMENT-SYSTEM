from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from django.core.mail import send_mail, EmailMessage
import qrcode
import requests as req
from io import BytesIO
from django.core.files import File
import razorpay

from .models import (Event, Booking, TicketTier, UserProfile, OTPVerification,
                     SavedEvent, OrganizerPayout, TermsAcceptance, CommissionRecord,
                     EventModerator)


def geocode_location(location):
    try:
        r = req.get(
            'https://nominatim.openstreetmap.org/search',
            params={'format': 'json', 'q': location, 'limit': 1},
            headers={'User-Agent': 'EventHub/1.0 (giri.himanshu2911@gmail.com)'},
            timeout=5
        )
        data = r.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except:
        pass
    return None, None


# ══════════════════════════════════════
# HOME
# ══════════════════════════════════════
def home(request):
    events = Event.objects.all().order_by('-id')[:6]
    return render(request, 'events/home.html', {'events': events})


# ══════════════════════════════════════
# EVENT LIST
# ══════════════════════════════════════
def event_list(request):
    category = request.GET.get('category', '').strip()
    query    = request.GET.get('q', '').strip()
    events   = Event.objects.filter(status='active').order_by('-id')

    if category:
        events = events.filter(category__iexact=category)
    if query:
        events = events.filter(title__icontains=query)

    paginator = Paginator(events, 6)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'events/event_list.html', {
        'page_obj':          page_obj,
        'selected_category': category,
        'query':             query,
    })


# ══════════════════════════════════════
# EVENT DETAIL
# ══════════════════════════════════════
def event_detail(request, id):
    event        = get_object_or_404(Event, id=id)
    total_booked = Booking.objects.filter(event=event).count()
    seats_left   = event.capacity - total_booked
    ticket_tiers = event.ticket_tiers.all()

    user_booked = False
    is_saved    = False

    if request.user.is_authenticated:
        user_booked = Booking.objects.filter(event=event, user=request.user).exists()
        is_saved    = SavedEvent.objects.filter(event=event, user=request.user).exists()

    return render(request, 'events/event_detail.html', {
        'event':           event,
        'seats_left':      seats_left,
        'user_booked':     user_booked,
        'ticket_tiers':    ticket_tiers,
        'is_saved':        is_saved,
        'save_count':      event.save_count,
        
    })


# ══════════════════════════════════════
# TIER AVAILABILITY API (real-time JSON)
# ══════════════════════════════════════
def tier_availability(request, id):
    event = get_object_or_404(Event, id=id)
    data  = {
        'event_seats_left': event.seats_left,
        'tiers': [
            {
                'id':          tier.id,
                'name':        tier.name,
                'price':       str(tier.price),
                'capacity':    tier.capacity,
                'booked':      tier.booked_count,
                'seats_left':  tier.seats_left,
                'is_sold_out': tier.is_sold_out,
                'is_free':     tier.is_free,
            }
            for tier in event.ticket_tiers.all()
        ]
    }
    return JsonResponse(data)


# ══════════════════════════════════════
# TOGGLE SAVE EVENT (Interested)
# ══════════════════════════════════════
@login_required
def toggle_save_event(request, id):
    event = get_object_or_404(Event, id=id)
    saved_obj, created = SavedEvent.objects.get_or_create(
        user=request.user, event=event
    )
    if not created:
        saved_obj.delete()
        return JsonResponse({'saved': False, 'count': event.save_count})
    return JsonResponse({'saved': True, 'count': event.save_count})


# ══════════════════════════════════════
# SAVED EVENTS LIST
# ══════════════════════════════════════
@login_required
def saved_events(request):
    saved = SavedEvent.objects.filter(
        user=request.user
    ).order_by('-saved_at').select_related('event')
    return render(request, 'events/saved_events.html', {'saved': saved})


# ══════════════════════════════════════
# CREATE EVENT
# ══════════════════════════════════════
@login_required
def create_event(request):
    if request.method == 'POST':
        title       = request.POST.get('title')
        description = request.POST.get('description')
        location    = request.POST.get('location')
        capacity    = request.POST.get('capacity')
        image       = request.FILES.get('image')
        event_date  = request.POST.get('date')

        category_select = request.POST.get('category_select', '').strip()
        category_custom = request.POST.get('category_custom', '').strip()
        category = category_custom if category_select == 'Other' else category_select

        if not category:
            messages.error(request, "Please select or enter a category.")
            return render(request, 'events/create_event.html', {})

        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/create_event.html', {})

        event = Event.objects.create(
            title=title, description=description, location=location,
            date=event_datetime, capacity=capacity, category=category,
            image=image, created_by=request.user
        )

        tier_names      = request.POST.getlist('tier_name')
        tier_prices     = request.POST.getlist('tier_price')
        tier_capacities = request.POST.getlist('tier_capacity')

        for name, price, cap in zip(tier_names, tier_prices, tier_capacities):
            name = name.strip()
            if name:
                TicketTier.objects.create(
                    event=event,
                    name=name,
                    price=float(price) if price else 0,
                    capacity=int(cap) if cap else 0,
                )
        lat, lon = geocode_location(location)
        if lat and lon:
            event.latitude  = lat
            event.longitude = lon
            event.save()
        
        # T&C must be accepted before publishing
        terms_accepted = request.POST.get('terms_accepted')
        if not terms_accepted:
            messages.error(request, "You must accept the Terms & Conditions to publish your event.")
            event.delete()
            return render(request, 'events/create_event.html', {})

        event.is_published  = True
        event.terms_accepted = True
        event.save()

        # Save T&C acceptance record (immutable audit trail)
        TermsAcceptance.objects.create(
            event=event,
            accepted_by=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )

        # Save organizer payout details
        OrganizerPayout.objects.create(
            event=event,
            upi_id=request.POST.get('upi_id', '').strip(),
            account_holder_name=request.POST.get('account_holder_name', '').strip(),
            account_number=request.POST.get('account_number', '').strip(),
            ifsc_code=request.POST.get('ifsc_code', '').strip(),
            bank_name=request.POST.get('bank_name', '').strip(),
        )

        # Initialise (set up) commission record
        CommissionRecord.objects.create(event=event)

        messages.success(request, "Event published successfully! 🎉")
        return redirect('event_list')

    return render(request, 'events/create_event.html', {
        
    })


# ══════════════════════════════════════
# EDIT EVENT
# ══════════════════════════════════════
@login_required
def edit_event(request, id):
    event = get_object_or_404(Event, id=id)

    # Only creator, assigned moderator with edit rights, or super admin can edit
    is_moderator = EventModerator.objects.filter(
        event=event, user=request.user, can_edit=True
    ).exists()
    if request.user != event.created_by and not request.user.is_superuser and not is_moderator:
        messages.error(request, "You don't have permission to edit this event.")
        return redirect('event_list')

    if request.method == 'POST':
        event_date     = request.POST.get('date')
        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/edit_event.html', {
                'event': event,
                'ticket_tiers': event.ticket_tiers.all()
            })

        category_select = request.POST.get('category_select', '').strip()
        category_custom = request.POST.get('category_custom', '').strip()
        category = category_custom if category_select == 'Other' else category_select

        if not category:
            messages.error(request, "Please select or enter a category.")
            return render(request, 'events/edit_event.html', {
                'event': event,
                'ticket_tiers': event.ticket_tiers.all(),
                'ticket_tiers_json': list(event.ticket_tiers.values('name', 'price', 'capacity')),
            })

        event.title       = request.POST.get('title')
        event.description = request.POST.get('description')
        event.location    = request.POST.get('location')
        event.date        = event_datetime
        event.capacity    = request.POST.get('capacity')
        event.category    = category
        if request.FILES.get('image'):
            event.image = request.FILES.get('image')
        event.save()

        event.ticket_tiers.all().delete()
        tier_names      = request.POST.getlist('tier_name')
        tier_prices     = request.POST.getlist('tier_price')
        tier_capacities = request.POST.getlist('tier_capacity')

        for name, price, cap in zip(tier_names, tier_prices, tier_capacities):
            name = name.strip()
            if name:
                TicketTier.objects.create(
                    event=event,
                    name=name,
                    price=float(price) if price else 0,
                    capacity=int(cap) if cap else 0,
                )
        lat, lon = geocode_location(event.location)
        if lat and lon:
            event.latitude  = lat
            event.longitude = lon
            event.save()

        messages.success(request, "Event updated successfully! ✅")
        return redirect('event_detail', id=event.id)

    payout = OrganizerPayout.objects.filter(event=event).first()
    return render(request, 'events/edit_event.html', {
        'event':             event,
        'ticket_tiers':      event.ticket_tiers.all(),
        'ticket_tiers_json': list(event.ticket_tiers.values('name', 'price', 'capacity')),
        'payout':            payout,
    })


# ══════════════════════════════════════
# DELETE EVENT
# ══════════════════════════════════════
@login_required
def delete_event(request, id):
    event = get_object_or_404(Event, id=id)
    # Strictly (exclusively) only creator can delete — moderators cannot
    if request.user != event.created_by and not request.user.is_superuser:
        messages.error(request, "Only the event creator can delete this event.")
        return redirect('event_detail', id=id)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Event deleted successfully.")
        return redirect('event_list')
    return render(request, 'events/delete_event.html', {'event': event})


# ══════════════════════════════════════
# BOOK EVENT
# ══════════════════════════════════════
@login_required
def book_event(request, id):
    event = get_object_or_404(Event, id=id)

    if Booking.objects.filter(event=event, user=request.user).exists():
        messages.warning(request, "You have already booked this event.")
        return redirect('event_detail', id=id)

    if event.seats_left <= 0:
        messages.error(request, "Unable to book. Maximum audience reached.")
        return redirect('event_detail', id=id)

    tier_id = request.POST.get('tier_id')
    tier    = get_object_or_404(TicketTier, id=tier_id, event=event)

    if tier.is_sold_out:
        messages.error(request, f"Sorry! {tier.name} tickets are sold out.")
        return redirect('event_detail', id=id)

    # Paid tickets go through Razorpay — only free tickets book directly here
    if not tier.is_free:
        messages.error(request, "Please complete payment through Razorpay.")
        return redirect('event_detail', id=id)

    booking = Booking.objects.create(
        event=event, user=request.user,
        ticket_tier=tier, ticket_type=tier.name,
        price=0, payment_status='paid'
    )

    qr_data = (
        f"Event: {event.title}\n"
        f"User: {request.user.username}\n"
        f"Ticket: {tier.name}\n"
        f"Booking ID: {booking.id}"
    )
    qr     = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    qr_bytes = buffer.getvalue()  # Save bytes before seeking
    buffer.seek(0)
    booking.qr_code.save(f"booking_{booking.id}.png", File(buffer), save=True)

    # Send confirmation email with QR attached
    try:
        price_display = "Free" if tier.is_free else f"Rs.{tier.price}"
        email_msg = EmailMessage(
            subject=f"🎉 Booking Confirmed — {event.title}",
            body=f"""Hi {request.user.username}!

Your booking is confirmed! 🎊

─────────────────────────────
Event:     {event.title}
Date:      {event.date.strftime('%B %d, %Y · %I:%M %p')}
Location:  {event.location}
Ticket:    {tier.name}
Price:     {price_display}
Booking #: {booking.id}
─────────────────────────────

Your QR code is attached — show it at the entrance for entry.

See you there! 🚀

— The EventHub Team""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email_msg.attach(f"ticket_{booking.id}.png", qr_bytes, 'image/png')
        email_msg.send(fail_silently=True)
    except Exception:
        pass

    price_display = "Free 🎁" if tier.is_free else f"Rs.{tier.price}"
    messages.success(request, f"Booking confirmed! 🎉 {tier.name} | {price_display}")
    return redirect(f'/event/{id}/?booked=1')

# ══════════════════════════════════════
# CREATE RAZORPAY ORDER
# ══════════════════════════════════════
@login_required
def create_razorpay_order(request, id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    event   = get_object_or_404(Event, id=id)
    tier_id = request.POST.get('tier_id')
    tier    = get_object_or_404(TicketTier, id=tier_id, event=event)

    if Booking.objects.filter(event=event, user=request.user).exists():
        return JsonResponse({'error': 'Already booked'}, status=400)

    if tier.is_sold_out or event.seats_left <= 0:
        return JsonResponse({'error': 'Sold out'}, status=400)

    client       = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    amount_paise = int(float(tier.price) * 100)  # Razorpay needs paise (₹1 = 100 paise)

    order = client.order.create({
        'amount':          amount_paise,
        'currency':        'INR',
        'payment_capture': 1,
        'notes': {
            'event_id': str(event.id),
            'tier_id':  str(tier.id),
            'user_id':  str(request.user.id),
        }
    })

    return JsonResponse({
        'order_id':    order['id'],
        'amount':      amount_paise,
        'currency':    'INR',
        'key':         settings.RAZORPAY_KEY_ID,
        'event_title': event.title,
        'tier_name':   tier.name,
        'user_name':   request.user.get_full_name() or request.user.username,
        'user_email':  request.user.email,
        'tier_id':     tier.id,
    })


# ══════════════════════════════════════
# VERIFY RAZORPAY PAYMENT + CREATE BOOKING
# ══════════════════════════════════════
@login_required
def verify_payment(request, id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    event               = get_object_or_404(Event, id=id)
    razorpay_order_id   = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature  = request.POST.get('razorpay_signature')
    tier_id             = request.POST.get('tier_id')
    tier                = get_object_or_404(TicketTier, id=tier_id, event=event)

    # Verify cryptographic (encryption-based) signature from Razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })
    except Exception:
        messages.error(request, "Payment verification failed. Contact support.")
        return redirect('event_detail', id=id)

    if Booking.objects.filter(event=event, user=request.user).exists():
        messages.warning(request, "Already booked!")
        return redirect('event_detail', id=id)

    booking = Booking.objects.create(
        event=event, user=request.user,
        ticket_tier=tier, ticket_type=tier.name, price=tier.price,
        payment_status='paid',
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )

    # Generate QR code
    qr_data = (
        f"Event: {event.title}\n"
        f"User: {request.user.username}\n"
        f"Ticket: {tier.name}\n"
        f"Payment: {razorpay_payment_id}\n"
        f"Booking ID: {booking.id}"
    )
    qr     = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    qr_bytes = buffer.getvalue()
    buffer.seek(0)
    booking.qr_code.save(f"booking_{booking.id}.png", File(buffer), save=True)

    # Recalculate (update) commission after new payment
    commission, _ = CommissionRecord.objects.get_or_create(event=event)
    commission.recalculate()

    # Send confirmation email with QR attached
    try:
        email_msg = EmailMessage(
            subject=f"🎉 Booking Confirmed — {event.title}",
            body=f"""Hi {request.user.username}!

Payment successful & booking confirmed! 🎊

─────────────────────────────
Event:      {event.title}
Date:       {event.date.strftime('%B %d, %Y · %I:%M %p')}
Location:   {event.location}
Ticket:     {tier.name}
Price:      ₹{tier.price}
Payment ID: {razorpay_payment_id}
Booking #:  {booking.id}
─────────────────────────────

Your QR code is attached — show it at the entrance.

See you there! 🚀

— The EventHub Team""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email_msg.attach(f"ticket_{booking.id}.png", qr_bytes, 'image/png')
        email_msg.send(fail_silently=True)
    except Exception:
        pass

    messages.success(request, f"Payment successful! 🎉 {tier.name} | ₹{tier.price}")
    return redirect(f'/event/{id}/?booked=1')

# ══════════════════════════════════════
# MY BOOKINGS
# ══════════════════════════════════════
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    return render(request, 'events/my_bookings.html', {'bookings': bookings})


# ══════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════
@login_required
def dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Admins only.")
        return redirect('event_list')

    total_events   = Event.objects.count()
    total_bookings = Booking.objects.count()
    total_users    = User.objects.count()
    total_revenue  = Booking.objects.aggregate(total=Sum('price'))['total'] or 0
    top_event      = Event.objects.annotate(
        booking_count=Count('booking')
    ).order_by('-booking_count').first()

    platform_commission = CommissionRecord.objects.aggregate(
        total=Sum('commission_amount')
    )['total'] or 0

    return render(request, 'events/dashboard.html', {
        'total_events':        total_events,
        'total_bookings':      total_bookings,
        'total_users':         total_users,
        'top_event':           top_event,
        'total_revenue':       total_revenue,
        'platform_commission': platform_commission,
    })


# ══════════════════════════════════════
# VERIFY TICKET
# ══════════════════════════════════════
@login_required
def verify_ticket(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Admins only.")
        return redirect('event_list')

    result = None
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        try:
            booking = Booking.objects.get(id=booking_id)
            if booking.is_used:
                result = "Ticket already used."
            else:
                booking.is_used = True
                booking.save()
                result = "Valid ticket. Entry allowed."
        except Booking.DoesNotExist:
            result = "Invalid ticket."

    return render(request, 'events/verify_ticket.html', {'result': result})


# ══════════════════════════════════════
# EVENT ATTENDEES
# ══════════════════════════════════════
@login_required
def event_attendees(request, id):
    event = get_object_or_404(Event, id=id)
    can_view = EventModerator.objects.filter(
        event=event, user=request.user, can_view_attendees=True
    ).exists()
    if request.user != event.created_by and not request.user.is_superuser and not can_view:
        messages.error(request, "Access denied.")
        return redirect('event_detail', id=id)

    bookings      = Booking.objects.filter(event=event).order_by('-booked_at')
    total_revenue = bookings.aggregate(total=Sum('price'))['total'] or 0

    commission = CommissionRecord.objects.filter(event=event).first()
    if commission:
        commission.recalculate()

    return render(request, 'events/event_attendees.html', {
        'event':         event,
        'bookings':      bookings,
        'total_revenue': total_revenue,
        'commission':    commission,
    })


# ══════════════════════════════════════
# CANCEL BOOKING
# ══════════════════════════════════════
@login_required
def cancel_booking(request, id):
    booking = get_object_or_404(Booking, id=id)
    if booking.user != request.user:
        return redirect('event_detail', id=booking.event.id)
    if request.method == 'POST':
        event_id = booking.event.id
        booking.delete()
        messages.success(request, "Booking cancelled successfully.")
        return redirect('event_detail', id=event_id)
    return render(request, 'events/cancel_booking.html', {'booking': booking})


# ══════════════════════════════════════
# REGISTER
# ══════════════════════════════════════
def register(request):
    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        mobile    = request.POST.get('mobile', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not username or not email or not password1:
            messages.error(request, "All fields are required.")
            return render(request, 'registration/register.html')
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'registration/register.html')
        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'registration/register.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, 'registration/register.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, 'registration/register.html')

        user           = User.objects.create_user(username=username, email=email, password=password1)
        user.is_active = False
        user.save()

        profile        = user.userprofile
        profile.mobile = mobile
        profile.save()

        otp_code = OTPVerification.generate_otp()
        OTPVerification.objects.create(user=user, otp=otp_code, otp_type='email_verify')

        send_mail(
            subject='EventHub — Verify Your Email',
            message=f"Hi {username}!\n\nWelcome to EventHub! 🎉\n\nYour OTP is: {otp_code}\n\nValid for 10 minutes.\n\n— The EventHub Team",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['otp_user_id'] = user.id
        request.session['otp_type']    = 'email_verify'
        messages.success(request, f"OTP sent to {email}!")
        return redirect('verify_otp')

    return render(request, 'registration/register.html')


# ══════════════════════════════════════
# VERIFY OTP
# ══════════════════════════════════════
def verify_otp(request):
    user_id  = request.session.get('otp_user_id')
    otp_type = request.session.get('otp_type', 'email_verify')

    if not user_id:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        otp_obj = OTPVerification.objects.filter(
            user=user, otp_type=otp_type, is_used=False
        ).order_by('-created_at').first()

        if not otp_obj:
            messages.error(request, "No OTP found. Please request a new one.")
            return render(request, 'registration/verify_otp.html', {'otp_type': otp_type, 'email': user.email})
        if not otp_obj.is_valid():
            messages.error(request, "OTP has expired. Please request a new one.")
            return render(request, 'registration/verify_otp.html', {'otp_type': otp_type, 'email': user.email})
        if otp_obj.otp != entered_otp:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'registration/verify_otp.html', {'otp_type': otp_type, 'email': user.email})

        otp_obj.is_used = True
        otp_obj.save()

        if otp_type == 'email_verify':
            user.is_active = True
            user.save()
            user.userprofile.is_email_verified = True
            user.userprofile.save()
            del request.session['otp_user_id']
            del request.session['otp_type']
            messages.success(request, "Email verified! You can now login. 🎉")
            return redirect('login')
        elif otp_type == 'password_reset':
            request.session['otp_verified'] = True
            messages.success(request, "OTP verified! Set your new password.")
            return redirect('otp_set_password')

    return render(request, 'registration/verify_otp.html', {'otp_type': otp_type, 'email': user.email})


# ══════════════════════════════════════
# RESEND OTP
# ══════════════════════════════════════
def resend_otp(request):
    user_id  = request.session.get('otp_user_id')
    otp_type = request.session.get('otp_type', 'email_verify')

    if not user_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('register')

    user = get_object_or_404(User, id=user_id)
    OTPVerification.objects.filter(user=user, otp_type=otp_type, is_used=False).update(is_used=True)

    otp_code = OTPVerification.generate_otp()
    OTPVerification.objects.create(user=user, otp=otp_code, otp_type=otp_type)

    send_mail(
        subject='EventHub — Your New OTP',
        message=f"Hi {user.username}!\n\nYour new OTP is: {otp_code}\n\nValid for 10 minutes.\n\n— The EventHub Team",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    messages.success(request, f"New OTP sent to {user.email}!")
    return redirect('verify_otp')


# ══════════════════════════════════════
# FORGOT PASSWORD
# ══════════════════════════════════════
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return render(request, 'registration/forgot_password.html')

        OTPVerification.objects.filter(user=user, otp_type='password_reset', is_used=False).update(is_used=True)
        otp_code = OTPVerification.generate_otp()
        OTPVerification.objects.create(user=user, otp=otp_code, otp_type='password_reset')

        send_mail(
            subject='EventHub — Password Reset OTP',
            message=f"Hi {user.username}!\n\nYour password reset OTP is: {otp_code}\n\nValid for 10 minutes.\n\n— The EventHub Team",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['otp_user_id'] = user.id
        request.session['otp_type']    = 'password_reset'
        messages.success(request, f"OTP sent to {email}!")
        return redirect('verify_otp')

    return render(request, 'registration/forgot_password.html')


# ══════════════════════════════════════
# SET NEW PASSWORD
# ══════════════════════════════════════
def otp_set_password(request):
    user_id      = request.session.get('otp_user_id')
    otp_verified = request.session.get('otp_verified', False)

    if not user_id or not otp_verified:
        messages.error(request, "Unauthorized access.")
        return redirect('forgot_password')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'registration/otp_set_password.html')
        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'registration/otp_set_password.html')

        user.set_password(password1)
        user.save()
        del request.session['otp_user_id']
        del request.session['otp_type']
        del request.session['otp_verified']

        messages.success(request, "Password reset successfully! Please login. 🎉")
        return redirect('login')

    return render(request, 'registration/otp_set_password.html')


# ══════════════════════════════════════
# PROFILE
# ══════════════════════════════════════
@login_required
def profile(request):
    bookings       = Booking.objects.filter(user=request.user).order_by('-booked_at')
    total_spent    = bookings.aggregate(total=Sum('price'))['total'] or 0
    events_created = Event.objects.filter(created_by=request.user).count()
    profile, _     = UserProfile.objects.get_or_create(user=request.user)

    return render(request, 'events/profile.html', {
        'bookings':       bookings,
        'total_spent':    total_spent,
        'events_created': events_created,
        'total_bookings': bookings.count(),
        'profile':        profile,
    })


# ══════════════════════════════════════
# EDIT PROFILE
# ══════════════════════════════════════
@login_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '')
        last_name  = request.POST.get('last_name', '')
        new_email  = request.POST.get('email', '').strip()
        bio        = request.POST.get('bio', '')
        mobile     = request.POST.get('mobile', '')
        location   = request.POST.get('location', '')

        email_changed = new_email and new_email != request.user.email

        if email_changed:
            if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                messages.error(request, "This email is already used by another account.")
                return render(request, 'events/edit_profile.html', {'profile': profile})

            OTPVerification.objects.filter(
                user=request.user, otp_type='email_change', is_used=False
            ).update(is_used=True)

            otp_code = OTPVerification.generate_otp()
            OTPVerification.objects.create(user=request.user, otp=otp_code, otp_type='email_change')

            request.user.first_name = first_name
            request.user.last_name  = last_name
            request.user.save()
            profile.bio = bio; profile.mobile = mobile; profile.location = location
            if request.FILES.get('profile_picture'):
                profile.profile_picture = request.FILES['profile_picture']
            profile.save()

            send_mail(
                subject='EventHub — Verify Your New Email',
                message=f"Hi {request.user.username}!\n\nYour email change OTP is: {otp_code}\n\nValid for 10 minutes.\n\n— The EventHub Team",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[new_email],
                fail_silently=False,
            )

            request.session['otp_user_id']   = request.user.id
            request.session['otp_type']      = 'email_change'
            request.session['pending_email'] = new_email
            messages.success(request, f"OTP sent to {new_email} — verify to update email!")
            return redirect('verify_email_change')

        else:
            request.user.first_name = first_name
            request.user.last_name  = last_name
            if new_email:
                request.user.email = new_email
            request.user.save()
            profile.bio = bio; profile.mobile = mobile; profile.location = location
            if request.FILES.get('profile_picture'):
                profile.profile_picture = request.FILES['profile_picture']
            profile.save()
            messages.success(request, "Profile updated successfully! ✅")
            return redirect('profile')

    return render(request, 'events/edit_profile.html', {'profile': profile})


# ══════════════════════════════════════
# VERIFY EMAIL CHANGE
# ══════════════════════════════════════
@login_required
def verify_email_change(request):
    pending_email = request.session.get('pending_email')
    otp_type      = request.session.get('otp_type')

    if not pending_email or otp_type != 'email_change':
        messages.error(request, "No pending email change found.")
        return redirect('edit_profile')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        otp_obj = OTPVerification.objects.filter(
            user=request.user, otp_type='email_change', is_used=False
        ).order_by('-created_at').first()

        if not otp_obj:
            messages.error(request, "No OTP found. Please try again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})
        if not otp_obj.is_valid():
            messages.error(request, "OTP expired. Please update profile again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})
        if otp_obj.otp != entered_otp:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})

        otp_obj.is_used    = True
        otp_obj.save()
        request.user.email = pending_email
        request.user.save()

        del request.session['pending_email']
        del request.session['otp_type']
        request.session.pop('otp_user_id', None)

        messages.success(request, f"Email updated to {pending_email} successfully! ✅")
        return redirect('profile')

    return render(request, 'events/verify_email_change.html', {'email': pending_email})


# ══════════════════════════════════════
# CHANGE PASSWORD
# ══════════════════════════════════════
@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully!")
            return redirect('profile')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'events/change_password.html', {'form': form})


# ══════════════════════════════════════
# SUPER ADMIN DASHBOARD
# ══════════════════════════════════════
@login_required
def super_admin_dashboard(request):
    try:
        is_super = request.user.userprofile.is_super_admin
    except:
        is_super = False

    if not is_super and not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('event_list')

    all_users   = User.objects.select_related('userprofile').order_by('-date_joined')
    all_events  = Event.objects.all().order_by('-id')
    total_rev   = Booking.objects.aggregate(total=Sum('price'))['total'] or 0

    return render(request, 'events/super_admin_dashboard.html', {
        'all_users':  all_users,
        'all_events': all_events,
        'total_rev':  total_rev,
    })


# ══════════════════════════════════════
# TOGGLE VERIFIED ORGANIZER BADGE
# ══════════════════════════════════════
@login_required
def toggle_verified_organizer(request, user_id):
    try:
        is_super = request.user.userprofile.is_super_admin
    except:
        is_super = False

    if not is_super and not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('event_list')

    target_profile = get_object_or_404(UserProfile, user__id=user_id)
    target_profile.is_verified_organizer = not target_profile.is_verified_organizer
    target_profile.save()

    status = "granted ✅" if target_profile.is_verified_organizer else "revoked ❌"
    messages.success(request, f"Verified Organizer badge {status} for {target_profile.user.username}.")
    return redirect('super_admin_dashboard')


# ══════════════════════════════════════
# ASSIGN MODERATOR
# ══════════════════════════════════════
@login_required
def assign_moderator(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Only the creator can assign (delegate) moderators
    if request.user != event.created_by:
        messages.error(request, "Only the event creator can assign moderators.")
        return redirect('event_detail', id=event_id)

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        can_edit   = request.POST.get('can_edit') == 'on'
        can_checkin = request.POST.get('can_check_in') == 'on'

        try:
            mod_user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, f"User '{username}' not found.")
            return redirect('event_attendees', id=event_id)

        if mod_user == event.created_by:
            messages.error(request, "You are already the creator — no need to assign yourself!")
            return redirect('event_attendees', id=event_id)

        EventModerator.objects.update_or_create(
            event=event, user=mod_user,
            defaults={
                'assigned_by':        request.user,
                'can_edit':           can_edit,
                'can_view_attendees': True,
                'can_check_in':       can_checkin,
            }
        )
        messages.success(request, f"@{username} is now a moderator for this event! 🎉")
        return redirect('event_attendees', id=event_id)

    return redirect('event_attendees', id=event_id)