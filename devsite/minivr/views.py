from django.db.models import Min
from django.shortcuts import render_to_response, get_object_or_404

from minivr.models import Service

def index(request):
    services = Service.objects.\
                   filter(free_seats__gt = 0).\
                   annotate(departure_time = Min('schedule__departure_time')).\
                   order_by('departure_time')
    return render_to_response('minivr/index.html', {'services':services})

def service_detail(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    stops = service.schedule.order_by('departure_time')
    return render_to_response('minivr/service_detail.html',
                              {'service':service, 'stops':stops})
