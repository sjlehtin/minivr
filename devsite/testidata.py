from datetime import time
from decimal import Decimal

import os, sys
sys.path.append(os.getcwd() + "/..")
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from minivr.models import *

Lippu.objects.all().delete()
Vuoro.objects.all().delete()
Asema.objects.all().delete()
Juna.objects.all().delete()
Stoppi.objects.all().delete()

helsinki = Asema(nimi = 'Helsinki')
turku    = Asema(nimi = 'Turku')
helsinki.save()
turku.save()
helsinki.yhteydet.add(turku)

pendolino = Juna(tyyppi = 'Pendolino', paikkoja = 100)
pendolino.save()

ht = Vuoro(juna = pendolino, paikkoja_vapaana = 50)
ht.save()

s1 = Stoppi(vuoro = ht, asema = helsinki, aika = time(19,03))
s2 = Stoppi(vuoro = ht, asema = turku,    aika = time(21,00))
s1.save()
s2.save()

lippu = Lippu(vuoro = ht, hinta = Decimal('12.49'))
lippu.save()
