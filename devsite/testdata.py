from datetime import time
from decimal import Decimal

import os, sys
sys.path.append(os.getcwd() + "/..")
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from minivr.models import *

Ticket.objects.all().delete()
Service.objects.all().delete()
Station.objects.all().delete()
Train.objects.all().delete()
Stop.objects.all().delete()

helsinki = Station(name = 'Helsinki')
turku    = Station(name = 'Turku')
helsinki.save()
turku.save()
helsinki.connections.add(turku)

pendolino = Train(name = 'Pendolino', seats = 100)
pendolino.save()

ht = Service(train = pendolino, free_seats = 50)
ht.save()

s1 = Stop(service = ht, station = helsinki, time = time(19,03))
s2 = Stop(service = ht, station = turku,    time = time(21,00))
s1.save()
s2.save()

ticket = Ticket(service = ht, price = Decimal('12.49'))
ticket.save()
