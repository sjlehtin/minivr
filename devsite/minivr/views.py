from django.core.urlresolvers import reverse
from django.db.models         import Min
from django.http              import HttpResponseRedirect
from django.shortcuts         import render_to_response, get_object_or_404
from django.template          import RequestContext

from minivr.models import Service

def index(request, last_reserved = None):
    services = Service.objects.\
                   filter(free_seats__gt = 0).\
                   order_by('departure_time')
    if last_reserved:
        last_reserved = int(last_reserved)
    return render_to_response(
        'minivr/index.html',
        {'services':services, 'last_reserved':last_reserved},
        context_instance = RequestContext(request))

def service_detail(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    stops = service.schedule.order_by('departure_time')
    return render_to_response('minivr/service_detail.html',
                              {'service':service, 'stops':stops})

def service_reserve(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    service.free_seats -= 1
    url = reverse('minivr.views.index', args = (service_id,))
    service.save()
    return HttpResponseRedirect(url)
