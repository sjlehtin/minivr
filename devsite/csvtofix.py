from datetime import datetime
import json
import random
from sys import stdin, stdout

random.seed(6)

fixtures = []

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
        connections[s] = set()
        stations[station] = s
        s += 1

    if train == prev_train:
        connections[stations[prev_station]].add(stations[station])

    if not train in trains:
        trains[train] = (t, random.choice([72, 84, 100, 120]))
        services[train] = []
        fixtures.append({'model': 'minivr.train', 'pk': t, 'fields':
                         {'name': train, 'seats': trains[train][1]}})
        t += 1

    services[train].append((stations[station], arrival, departure))

    prev_train = train
    prev_station = station

fixtures.append({'model': 'minivr.customertype', 'pk': 1, 'fields': {'name': 'aikuinen'}})

for name,id in stations.items():
    fixtures.append({'model': 'minivr.station', 'pk': id, 'fields': {'name': name}})

distances = {}
costs = {}
c = 0
for v in connections:
    for u in connections[v]:
        if not (u,v) in distances:
            distances[(u,v)] = int(random.normalvariate(50,10))
            costs    [(u,v)] = int(distances[(u,v)] * random.normalvariate(1, 0.2))

            distances[(v,u)] = distances[(u,v)]
            costs    [(v,u)] = costs    [(u,v)]

        fixtures.append({'model': 'minivr.connection', 'pk': c, 'fields':
                         {'out_of':   v,
                          'to':       u,
                          'distance': distances[(u,v)],
                          'cost':     costs    [(u,v)]}})
        c += 1

s = 0
st = 0
for train, service in services.items():
    dt = service[0][2]

    fixtures.append({'model': 'minivr.service', 'pk': s, 'fields':
                     {'train': trains[train][0],
                      'departure_time': dt,
                      'free_seats': random.randint(1, trains[train][1])}})

    dt = datetime.strptime(dt, '%H:%M')

    for (station,arrival,departure) in service:
        a = (datetime.strptime(arrival,   '%H:%M') - dt).seconds / 60 if arrival   else None
        d = (datetime.strptime(departure, '%H:%M') - dt).seconds / 60 if departure else None

        fixtures.append({'model': 'minivr.stop', 'pk': st, 'fields':
                         {'service': s,
                          'station': station,
                          'arrival_time': a,
                          'departure_time': d,
                          'year_min': 2010,
                          'year_max': 2011,
                          'month_min': 1,
                          'month_max': 12,
                          'weekday_min': 1,
                          'weekday_max': 7}})
        st += 1

    fixtures.append({'model': 'minivr.ticket', 'pk': s, 'fields':
                     {'service': s,
                      'customer_type': 1,
                      'price_per_cost': '%d.%d' % (round(random.randint(0,1)), random.randint(20,9999))}})
    s += 1

json.dump(fixtures, stdout, ensure_ascii = False, indent = 2)
