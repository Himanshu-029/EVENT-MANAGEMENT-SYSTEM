from django.shortcuts import render, redirect, get_object_or_404
from .models import Event, Booking
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Sum
import qrcode
from io import BytesIO
from django.core.files import File
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .models import Event, Booking, UserProfile
from django.core.mail import send_mail
from django.conf import settings
from .models import Event, Booking, UserProfile, OTPVerification


# ══════════════════════════════════════
# HOME
# ══════════════════════════════════════
def home(request):
    events = Event.objects.all().order_by('-id')[:6]
    return render(request, 'events/home.html', {
        'events': events,
    })


# ══════════════════════════════════════
# EVENT LIST
# ══════════════════════════════════════
def event_list(request):
    category = request.GET.get('category', '').strip()
    query = request.GET.get('q', '').strip()

    events = Event.objects.all().order_by('-id')

    if category:
        events = events.filter(category=category)

    if query:
        events = events.filter(title__icontains=query)

    paginator = Paginator(events, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'events/event_list.html', {
        'page_obj': page_obj,
        'selected_category': category,
        'query': query,
    })


# ══════════════════════════════════════
# EVENT DETAIL
# ══════════════════════════════════════
def event_detail(request, id):
    event = get_object_or_404(Event, id=id)
    total_bookings = Booking.objects.filter(event=event).count()
    seats_left = event.capacity - total_bookings

    user_booked = False
    if request.user.is_authenticated:
        user_booked = Booking.objects.filter(
            event=event,
            user=request.user
        ).exists()

    context = {
        'event': event,
        'seats_left': seats_left,
        'user_booked': user_booked,
    }
    return render(request, 'events/event_detail.html', context)


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
        category    = request.POST.get('category')
        image       = request.FILES.get('image')
        event_date  = request.POST.get('date')

        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/create_event.html')

        Event.objects.create(
            title=title,
            description=description,
            location=location,
            date=event_datetime,
            capacity=capacity,
            category=category,
            image=image,
            created_by=request.user
        )
        messages.success(request, "Event created successfully!")
        return redirect('event_list')

    return render(request, 'events/create_event.html')


# ══════════════════════════════════════
# EDIT EVENT
# ══════════════════════════════════════
@login_required
def edit_event(request, id):
    event = get_object_or_404(Event, id=id)

    if request.user != event.created_by and not request.user.is_superuser:
        return redirect('event_list')

    if request.method == 'POST':
        event_date = request.POST.get('date')

        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/edit_event.html', {'event': event})

        event.title       = request.POST.get('title')
        event.description = request.POST.get('description')
        event.location    = request.POST.get('location')
        event.date        = event_datetime
        event.capacity    = request.POST.get('capacity')
        event.category    = request.POST.get('category')

        if request.FILES.get('image'):
            event.image = request.FILES.get('image')

        event.save()
        messages.success(request, "Event updated successfully!")
        return redirect('event_detail', id=event.id)

    return render(request, 'events/edit_event.html', {'event': event})


# ══════════════════════════════════════
# DELETE EVENT
# ══════════════════════════════════════
@login_required
def delete_event(request, id):
    event = get_object_or_404(Event, id=id)

    if request.user != event.created_by and not request.user.is_superuser:
        return redirect('event_list')

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

    total_bookings = Booking.objects.filter(event=event).count()
    if total_bookings >= event.capacity:
        messages.error(request, "Unable to book. Maximum audience reached.")
        return redirect('event_detail', id=id)

    ticket_type = request.POST.get('ticket_type')
    price = 1000 if ticket_type == 'VIP' else 500

    booking = Booking.objects.create(
        event=event,
        user=request.user,
        ticket_type=ticket_type,
        price=price
    )

    qr_data = (
        f"Event: {event.title}\n"
        f"User: {request.user.username}\n"
        f"Ticket: {ticket_type}\n"
        f"Booking ID: {booking.id}"
    )
    qr = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    file_name = f"booking_{booking.id}.png"
    booking.qr_code.save(file_name, File(buffer), save=True)

    messages.success(
        request,
        f"Booking successful! Ticket: {ticket_type} | Rs.{price}"
    )
    return redirect('event_detail', id=id)


# ══════════════════════════════════════
# MY BOOKINGS
# ══════════════════════════════════════
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(
        user=request.user
    ).order_by('-booked_at')
    return render(request, 'events/my_bookings.html', {
        'bookings': bookings
    })


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
    total_revenue  = Booking.objects.aggregate(
        total=Sum('price')
    )['total'] or 0

    events_with_counts = Event.objects.annotate(
        booking_count=Count('booking')
    ).order_by('-booking_count')

    top_event = events_with_counts.first()

    context = {
        'total_events':   total_events,
        'total_bookings': total_bookings,
        'total_users':    total_users,
        'top_event':      top_event,
        'total_revenue':  total_revenue,
    }
    return render(request, 'events/dashboard.html', context)


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

    return render(request, 'events/verify_ticket.html', {
        'result': result
    })


# ══════════════════════════════════════
# EVENT ATTENDEES
# ══════════════════════════════════════
@login_required
def event_attendees(request, id):
    event = get_object_or_404(Event, id=id)

    if request.user != event.created_by and not request.user.is_superuser:
        return redirect('event_detail', id=id)

    bookings = Booking.objects.filter(event=event).order_by('-booked_at')
    total_revenue = bookings.aggregate(
        total=Sum('price')
    )['total'] or 0

    context = {
        'event':         event,
        'bookings':      bookings,
        'total_revenue': total_revenue,
    }
    return render(request, 'events/event_attendees.html', context)


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

    return render(request, 'events/cancel_booking.html', {
        'booking': booking
    })


# ══════════════════════════════════════
# REGISTER — sends email OTP
# ══════════════════════════════════════
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        mobile   = request.POST.get('mobile', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # Validations
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

        # Create inactive user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
        )
        user.is_active = False  # inactive until email verified
        user.save()

        # Save mobile to profile
        profile = user.userprofile
        profile.mobile = mobile
        profile.save()

        # Generate & send OTP
        otp_code = OTPVerification.generate_otp()
        OTPVerification.objects.create(
            user=user,
            otp=otp_code,
            otp_type='email_verify'
        )

        send_mail(
            subject='EventHub — Verify Your Email',
            message=f'''Hi {username}!

Welcome to EventHub! 🎉

Your email verification OTP is:

    {otp_code}

This OTP is valid for 10 minutes.

If you did not register on EventHub, please ignore this email.

— The EventHub Team''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        # Store user id in session for OTP page
        request.session['otp_user_id'] = user.id
        request.session['otp_type'] = 'email_verify'

        messages.success(request, f"OTP sent to {email}!")
        return redirect('verify_otp')

    return render(request, 'registration/register.html')


# ══════════════════════════════════════
# VERIFY OTP — email verification
# ══════════════════════════════════════
def verify_otp(request):
    user_id = request.session.get('otp_user_id')
    otp_type = request.session.get('otp_type', 'email_verify')

    if not user_id:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()

        # Get latest unused OTP
        otp_obj = OTPVerification.objects.filter(
            user=user,
            otp_type=otp_type,
            is_used=False
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

        # Mark OTP as used
        otp_obj.is_used = True
        otp_obj.save()

        if otp_type == 'email_verify':
            # Activate user
            user.is_active = True
            user.save()
            profile = user.userprofile
            profile.is_email_verified = True
            profile.save()
            # Clear session
            del request.session['otp_user_id']
            del request.session['otp_type']
            messages.success(request, "Email verified! You can now login. 🎉")
            return redirect('login')

        elif otp_type == 'password_reset':
            # Allow password reset
            request.session['otp_verified'] = True
            messages.success(request, "OTP verified! Set your new password.")
            return redirect('otp_set_password')

    return render(request, 'registration/verify_otp.html', {
        'otp_type': otp_type,
        'email': user.email
    })


# ══════════════════════════════════════
# RESEND OTP
# ══════════════════════════════════════
def resend_otp(request):
    user_id = request.session.get('otp_user_id')
    otp_type = request.session.get('otp_type', 'email_verify')

    if not user_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('register')

    user = get_object_or_404(User, id=user_id)

    # Invalidate old OTPs
    OTPVerification.objects.filter(
        user=user,
        otp_type=otp_type,
        is_used=False
    ).update(is_used=True)

    # Generate new OTP
    otp_code = OTPVerification.generate_otp()
    OTPVerification.objects.create(
        user=user,
        otp=otp_code,
        otp_type=otp_type
    )

    subject = 'EventHub — Your New OTP'
    message = f'''Hi {user.username}!

Your new OTP is:

    {otp_code}

This OTP is valid for 10 minutes.

— The EventHub Team'''

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    messages.success(request, f"New OTP sent to {user.email}!")
    return redirect('verify_otp')


# ══════════════════════════════════════
# FORGOT PASSWORD — send OTP
# ══════════════════════════════════════
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return render(request, 'registration/forgot_password.html')

        # Invalidate old reset OTPs
        OTPVerification.objects.filter(
            user=user,
            otp_type='password_reset',
            is_used=False
        ).update(is_used=True)

        # Generate OTP
        otp_code = OTPVerification.generate_otp()
        OTPVerification.objects.create(
            user=user,
            otp=otp_code,
            otp_type='password_reset'
        )

        send_mail(
            subject='EventHub — Password Reset OTP',
            message=f'''Hi {user.username}!

Your password reset OTP is:

    {otp_code}

This OTP is valid for 10 minutes.
If you did not request a password reset, please ignore this email.

— The EventHub Team''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['otp_user_id'] = user.id
        request.session['otp_type'] = 'password_reset'

        messages.success(request, f"OTP sent to {email}!")
        return redirect('verify_otp')

    return render(request, 'registration/forgot_password.html')


# ══════════════════════════════════════
# SET NEW PASSWORD after OTP verified
# ══════════════════════════════════════
def otp_set_password(request):
    user_id = request.session.get('otp_user_id')
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

        # Clear session
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
    bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    total_spent = bookings.aggregate(total=Sum('price'))['total'] or 0
    events_created = Event.objects.filter(created_by=request.user).count()

    # Get or create profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    context = {
        'bookings': bookings,
        'total_spent': total_spent,
        'events_created': events_created,
        'total_bookings': bookings.count(),
        'profile': profile,
    }
    return render(request, 'events/profile.html', context)


@login_required
def edit_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        first_name  = request.POST.get('first_name', '')
        last_name   = request.POST.get('last_name', '')
        new_email   = request.POST.get('email', '').strip()
        bio         = request.POST.get('bio', '')
        mobile      = request.POST.get('mobile', '')
        location    = request.POST.get('location', '')

        current_email = request.user.email
        email_changed = new_email and new_email != current_email

        if email_changed:
            # Check email not taken by another user
            if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                messages.error(request, "This email is already used by another account.")
                return render(request, 'events/edit_profile.html', {'profile': profile})

            # Invalidate old email_change OTPs
            OTPVerification.objects.filter(
                user=request.user,
                otp_type='email_change',
                is_used=False
            ).update(is_used=True)

            # Generate OTP
            otp_code = OTPVerification.generate_otp()
            OTPVerification.objects.create(
                user=request.user,
                otp=otp_code,
                otp_type='email_change'
            )

            # Save other fields first (not email)
            request.user.first_name = first_name
            request.user.last_name  = last_name
            request.user.save()
            profile.bio      = bio
            profile.mobile   = mobile
            profile.location = location
            if request.FILES.get('profile_picture'):
                profile.profile_picture = request.FILES.get('profile_picture')
            profile.save()

            # Send OTP to NEW email
            send_mail(
                subject='EventHub — Verify Your New Email',
                message=f'''Hi {request.user.username}!

You requested to change your email address on EventHub.

Your verification OTP is:

    {otp_code}

This OTP is valid for 10 minutes.
If you did not request this change, please ignore this email.

— The EventHub Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[new_email],
                fail_silently=False,
            )

            # Store in session
            request.session['otp_user_id']   = request.user.id
            request.session['otp_type']      = 'email_change'
            request.session['pending_email'] = new_email

            messages.success(request, f"OTP sent to {new_email} — please verify to update your email!")
            return redirect('verify_email_change')

        else:
            # No email change — update everything directly
            request.user.first_name = first_name
            request.user.last_name  = last_name
            if new_email:
                request.user.email  = new_email
            request.user.save()

            profile.bio      = bio
            profile.mobile   = mobile
            profile.location = location
            if request.FILES.get('profile_picture'):
                profile.profile_picture = request.FILES.get('profile_picture')
            profile.save()

            messages.success(request, "Profile updated successfully! ✅")
            return redirect('profile')

    return render(request, 'events/edit_profile.html', {'profile': profile})


# ══════════════════════════════════════
# VERIFY EMAIL CHANGE OTP
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
            user=request.user,
            otp_type='email_change',
            is_used=False
        ).order_by('-created_at').first()

        if not otp_obj:
            messages.error(request, "No OTP found. Please try again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})

        if not otp_obj.is_valid():
            messages.error(request, "OTP has expired. Please update profile again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})

        if otp_obj.otp != entered_otp:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'events/verify_email_change.html', {'email': pending_email})

        # Mark OTP used and update email
        otp_obj.is_used = True
        otp_obj.save()

        request.user.email = pending_email
        request.user.save()

        # Clear session
        del request.session['pending_email']
        del request.session['otp_type']
        if 'otp_user_id' in request.session:
            del request.session['otp_user_id']

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