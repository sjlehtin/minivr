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

s1 = Stop(service = ht, station = helsinki, departure_time = time(19,03),
          month_min = 5, month_max = 11, weekday_min = 1, weekday_max = 7,
          year_min = 2010)
s2 = Stop(service = ht, station = turku,    arrival_time   = time(21,00),
          month_min = 1, month_max =  6, weekday_min = 1, weekday_max = 5,
          year_min = 2010, year_max = 2010)
s1.save()
s2.save()

ticket = Ticket(service = ht, price = Decimal('12.49'))
ticket.save()
