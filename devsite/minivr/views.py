from django.shortcuts import render_to_response

from minivr.models import Vuoro

def index(request):
    vuorot = Vuoro.objects.all().\
                filter(paikkoja_vapaana__gt = 0).\
                order_by('aika')
    return render_to_response('minivr/index.html', {'vuorot':vuorot})
