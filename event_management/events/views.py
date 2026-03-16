from django.shortcuts import render, redirect, get_object_or_404
from .models import Event
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Event, Booking
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models import Sum
import qrcode
from io import BytesIO
from django.core.files import File
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime



def event_list(request):
    category = request.GET.get('category')
    query = request.GET.get('q')

    events = Event.objects.all()

    if category:
        events = events.filter(category=category)

    if query:
        events = events.filter(title__icontains=query)

    paginator = Paginator(events, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'events/event_list.html', {
        'page_obj': page_obj
    })

def event_detail(request, id):
    event = get_object_or_404(Event, id=id)
    total_bookings = Booking.objects.filter(event=event).count()
    seats_left = event.capacity - total_bookings

    user_booked = False
    if request.user.is_authenticated:
        user_booked = Booking.objects.filter(event=event, user=request.user).exists()

    context = {
        'event': event,
        'seats_left': seats_left,
        'user_booked': user_booked,
    }

    return render(request, 'events/event_detail.html', context)
@login_required
def create_event(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        location = request.POST.get('location')
        date = request.POST.get('date')
        capacity = request.POST.get('capacity')
        image = request.FILES.get('image')
        category = request.POST.get('category')
        event_date = request.POST.get('date')

        # Convert string to datetime object properly
        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")

        # Make it timezone aware
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/create_event.html')

        Event.objects.create(
            title=title,
            description=description,
            location=location,
            date=date,
            capacity=capacity,
            category=category,
            image=image,
            created_by=request.user
        )

        return redirect('event_list')

    return render(request, 'events/create_event.html')

@login_required
def edit_event(request, id):
    event = get_object_or_404(Event, id=id)

    if request.user != event.created_by and not request.user.is_superuser:
        return redirect('event_list')

    if request.method == 'POST':
        event.title = request.POST.get('title')
        event.description = request.POST.get('description')
        event.location = request.POST.get('location')
        event.date = request.POST.get('date')
        event.capacity = request.POST.get('capacity')
        event.category = request.POST.get('category')
        category = request.POST.get('category')
        event_date = request.POST.get('date')

        # Convert string to datetime object properly
        event_datetime = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")

        # Make it timezone aware
        event_datetime = timezone.make_aware(event_datetime)

        if event_datetime < timezone.now():
            messages.error(request, "Event date cannot be in the past.")
            return render(request, 'events/create_event.html')

        # Handle image update
        if request.FILES.get('image'):
            event.image = request.FILES.get('image')

        event.save()

        return redirect('event_detail', id=event.id)

    return render(request, 'events/edit_event.html', {'event': event})

@login_required
def delete_event(request, id):
    event = get_object_or_404(Event, id=id)

    if request.user != event.created_by:
        return redirect('event_list')

    if request.method == 'POST':
        event.delete()
        return redirect('event_list')

    return render(request, 'events/delete_event.html', {'event': event})

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

    if ticket_type == 'VIP':
        price = 1000
    else:
        price = 500

    booking = Booking.objects.create(
    event=event,
    user=request.user,
    ticket_type=ticket_type,
    price=price
)

    # Generate QR Code
    qr_data = f"Event: {event.title}\nUser: {request.user.username}\nTicket: {ticket_type}"
    qr = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    file_name = f"booking_{booking.id}.png"

    booking.qr_code.save(file_name, File(buffer), save=True)

    messages.success(request, f"Booking successful! Ticket: {ticket_type} | ₹{price}")
    return redirect('event_detail', id=id)

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user)
    return render(request, 'events/my_bookings.html', {'bookings': bookings})

@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect('event_list')

    total_events = Event.objects.count()
    total_bookings = Booking.objects.count()
    total_users = User.objects.count()
    total_revenue = Booking.objects.aggregate(total=Sum('price'))['total'] or 0

    events_with_counts = Event.objects.annotate(
        booking_count=Count('booking')
    ).order_by('-booking_count')

    top_event = events_with_counts.first()

    context = {
        'total_events': total_events,
        'total_bookings': total_bookings,
        'total_users': total_users,
        'top_event': top_event,
        'total_revenue': total_revenue,
    }

    return render(request, 'events/dashboard.html', context)

@login_required
def verify_ticket(request):
    if not request.user.is_superuser:
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

@login_required
def event_attendees(request, id):
    event = get_object_or_404(Event, id=id)

    # Allow creator OR superuser
    if request.user != event.created_by and not request.user.is_superuser:
        return redirect('event_detail', id=id)

    bookings = Booking.objects.filter(event=event)

    total_revenue = bookings.aggregate(total=Sum('price'))['total'] or 0

    context = {
        'event': event,
        'bookings': bookings,
        'total_revenue': total_revenue
    }

    return render(request, 'events/event_attendees.html', context)

@login_required
def cancel_booking(request, id):
    booking = get_object_or_404(Booking, id=id)

    if booking.user != request.user:
        return redirect('event_detail', id=booking.event.id)

    if request.method == 'POST':
        booking.delete()
        messages.success(request, "Booking cancelled successfully.")
        return redirect('event_detail', id=booking.event.id)

    return render(request, 'events/cancel_booking.html', {'booking': booking})


def home(request):
    events = Event.objects.all()
    return render(request,'events/home.html',{'events':events})
