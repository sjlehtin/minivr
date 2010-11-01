from django.db.models import Min
from django.shortcuts import render_to_response

from minivr.models import Service

def index(request):
    services = Service.objects.all().\
                   filter(free_seats__gt = 0).\
                   annotate(departure_time = Min('schedule__time')).\
                   order_by('departure_time')
    return render_to_response('minivr/index.html', {'services':services})
