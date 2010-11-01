from django.db.models import Min
from django.shortcuts import render_to_response

from minivr.models import Vuoro

def index(request):
    vuorot = Vuoro.objects.all().\
                filter(paikkoja_vapaana__gt = 0).\
                annotate(lahtoaika = Min('aikataulu__aika')).\
                order_by('lahtoaika')
    return render_to_response('minivr/index.html', {'vuorot':vuorot})
