from datetime import datetime
import json
import random
from sys import stdin, stdout

random.seed(6)

fstations = []
ftrains = []
fservices = []
fstops = []
ftickets = []

stations = {}
connections = {}
services = {}
trains = {}
prev_train = None
prev_station = None
s = 0
t = 0

for line in stdin:
    (train,station,arrival,departure) = line.strip().split(',')

    if not station in stations:
        connections[station] = set()
        stations[station] = s
        s += 1

    if train == prev_train:
        connections[prev_station].add(station)
        connections[station].add(prev_station)

    if not train in trains:
        trains[train] = (t, random.choice([72, 84, 100, 120]))
        services[train] = []
        ftrains.append({'model': 'minivr.train', 'pk': t, 'fields':
                        {'name': train, 'seats': trains[train][1]}})
        t += 1

    services[train].append((stations[station], arrival, departure))

    prev_train = train
    prev_station = station

for v in connections:
    fstations.append({'model': 'minivr.station', 'pk': stations[v], 'fields':
                      {'name': v, 'connections': [stations[u] for u in connections[v]]}})

s = 0
st = 0
for train, service in services.items():
    dt = service[0][2]

    fservices.append({'model': 'minivr.service', 'pk': s, 'fields':
                      {'train': trains[train][0],
                       'departure_time': dt,
                       'free_seats': random.randint(1, trains[train][1])}})

    dt = datetime.strptime(dt, '%H:%M')

    for (station,arrival,departure) in service:
        a = (datetime.strptime(arrival,   '%H:%M') - dt).seconds / 60 if arrival   else None
        d = (datetime.strptime(departure, '%H:%M') - dt).seconds / 60 if departure else None

        fstops.append({'model': 'minivr.stop', 'pk': st, 'fields':
                       {'service': s,
                        'station': station,
                        'arrival_time': a,
                        'departure_time': d,
                        'year_min': None,
                        'year_max': None,
                        'month_min': 1,
                        'month_max': 12,
                        'weekday_min': 1,
                        'weekday_max': 7}})
        st += 1

    ftickets.append({'model': 'minivr.ticket', 'pk': s, 'fields':
                     {'service': s,
                      'price': '%d.%d0' % (round(random.normalvariate(10,2)), random.randint(0,9))}})
    s += 1

fixtures = fstations + ftrains + fservices + fstops + ftickets
json.dump(fixtures, stdout, ensure_ascii = False, indent = 2)
