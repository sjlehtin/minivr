# coding=utf-8

import datetime

from django.core.urlresolvers import reverse
from django.db                import connection
from django.db.models         import F, Q, Min
from django.http              import HttpResponseRedirect
from django.shortcuts         import render_to_response, get_object_or_404
from django.template          import RequestContext

from minivr                          import findroute
from minivr.models                   import Service, Stop, Station, Connection
from minivr.templatetags.minivr_time import addminutes

def index(request):
    services = Service.objects.\
                   filter(free_seats__gt = 0).\
                   order_by('departure_time')
    last_reserved = int(request.GET.get('last_reserved', -1))
    return render_to_response(
        'index.html',
        {'services':services, 'last_reserved':last_reserved},
        context_instance = RequestContext(request))

def service_detail(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    stops = service.schedule.order_by('departure_time')
    return render_to_response('service_detail.html',
                              {'service':service, 'stops':stops})

def service_reserve(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    service.free_seats -= 1
    url = reverse('minivr.views.index') + '?last_reserved=' + service_id
    service.save()
    return HttpResponseRedirect(url)

def service_reserve_simple(request, service_id):
    """
    Reserve from route planning.
    """
    service = get_object_or_404(Service, id = service_id)
    service.free_seats -= 1
    service.save()
    return render_to_response('reserve_simple.html',
                              {'service':service})

def get_route(request):
    if not request.GET:
        return render_to_response('get_route.html')

    # Passed to the template even in the case of errors, so that it can fill in
    # the form with what the user previously input.
    vals = dict((k, unicode(v)) for (k,v) in request.GET.iteritems())
    last_reserved = int(request.GET.get('last_reserved', -1))

    error = False
    try:
        from_station_name = request.GET['from']
        to_station_name   = request.GET['to']
        time_type         = request.GET['type']

        if time_type == 'departure':
            time_type = findroute.DEPARTURE
        elif time_type == 'arrival':
            time_type = findroute.ARRIVAL

            # FIXME
            vals.update({'error': 'FIXME: käänteisiä ei osata vielä'})
            error = True
        else:
            raise ValueError

        # Minutes from midnight. This ensures that in the queries below, e.g.
        # 23:00 + 120 exceeds 21:00.
        time = int(request.GET['h']) * 60 + int(request.GET['m'])

        # This query is too complicated for me to be able to map it into
        # Django. Sorry, folks.
        #
        # Basically, we just want the (service_id,station_id) pairs
        # corresponding to the given "from" station in order of time, starting
        # from the given time.
        cursor = connection.cursor()
        cursor.execute(
            'SELECT service_id, station_id FROM'
            '  (SELECT 60 * extract(hour   from minivr_service.departure_time)'
            '           +   extract(minute from minivr_service.departure_time)'
            '           + minivr_stop.departure_time'
            '          AS final_t,'
            '          minivr_service.id AS service_id,'
            '          minivr_station.id AS station_id'
            '     FROM minivr_stop'
            '         INNER JOIN minivr_service'
            '                 ON (minivr_stop.service_id = minivr_service.id)'
            '         INNER JOIN minivr_station'
            '                 ON (minivr_stop.station_id = minivr_station.id)'
            '     WHERE UPPER(minivr_station.name::text) = UPPER(%s))'
            '  AS ts'
            '  WHERE ts.final_t >= %s'
            '  ORDER BY ts.final_t ASC'
            '  LIMIT 3',
            [from_station_name, time])

        from_stops = cursor.fetchall()

        if len(from_stops) == 0:
            raise Station.DoesNotExist

        to_station = Station.objects.get(name__iexact = to_station_name)

    except KeyError:
        vals.update({'error': 'Puutteellinen syöte.'})
        error = True
    except ValueError:
        vals.update({'error': 'Virheellinen syöte.'})
        error = True
    except Station.DoesNotExist:
        vals.update({'error': 'Asemaa ei löydy.'})
        error = True

    if error:
        return render_to_response('get_route.html', vals)

    from_stop_station_ids = [s[1] for s in from_stops]

    class StopNode(object):
        def __init__(self, stop):
            self.service_id             = stop.service.id
            self.station_id             = stop.station.id
            self.arrival_time           = stop.arrival_time
            self.departure_time         = stop.departure_time
            self.service_departure_time = stop.service.departure_time
            self.successors             = []

        def get_connections(self):
            return self.successors

        def __hash__(self):
            return hash((self.service_id, self.station_id))

        def __eq__(self, other):
            return isinstance(other, StopNode) and cmp(self, other) == 0

        def __cmp__(self, other):
            return cmp(( self.service_id,  self.station_id),
                       (other.service_id, other.station_id))

        def is_at_from(self):
            return self.station_id in from_stop_station_ids

    all_stops = Stop.objects.order_by('service__id', '-departure_time').select_related()
    nodes = dict(((stop.service.id, stop.station.id), StopNode(stop))
                 for stop in all_stops)

    # Populate nodes' successors
    for node in nodes.itervalues():

        # There are two classes of successors for each node.

        # Firstly, one can switch from one train to another departing one if
        # the time between the first one's arrival and the latter one's
        # departure is short enough.

        for (se_id,) in Stop.objects.\
                             filter(station__id = node.station_id).\
                             exclude(service__id = node.service_id).\
                             values_list('service_id'):

            next = nodes.get((se_id, node.station_id), None)
            if next == None or next.departure_time == None:
                continue

            assert next.station_id == node.station_id

            node_dt = node.service_departure_time
            next_dt = next.service_departure_time

            timediff = ((next_dt.hour   - node_dt.hour) * 60 + \
                        (next_dt.minute - node_dt.minute))

            # For the "from" station, there is no time limit, and the cost is
            # the difference between the departure times.
            if node.is_at_from():
                if timediff < 0:
                    timediff += 24*60
                node.successors.append((next, timediff))

            # Don't bother adding train-switch edges for nodes that lack an
            # arrival time: we can only enter them by switching trains in the
            # middle of the route, and there's no need to switch again
            # immediately thereafter.
            elif node.arrival_time != None:
                timediff += next.departure_time - node.arrival_time
                if timediff < 0:
                    timediff += 24*60

                if timediff >= findroute.TRAIN_SWITCH_TIME:
                    node.successors.append((next, timediff))

        # Secondly, one can continue in the same train, if it will ever depart.

        if node.departure_time == None:
            continue

        schedule = Service.objects.get(id = node.service_id).schedule

        next_time = schedule.filter(arrival_time__gt = node.departure_time).\
                             aggregate(m = Min('arrival_time'))['m']

        next_stop = schedule.filter(arrival_time = next_time).\
                             values_list('service_id', 'station_id')

        assert len(next_stop) == 1
        next = nodes[next_stop[0]]

        assert next.service_id == node.service_id

        # By default, use the difference between the arrival times, because we
        # need to include the wait time at a station.
        #
        # But if the arrival time is null, we're at the start of a service:
        # we've already handled the waiting as part of the train switch (which
        # may be the zero-cost start of the route), so use the departure time.
        timediff = next.arrival_time - \
                   (node.arrival_time or node.departure_time)

        node.successors.append((next, timediff))

    routes = []
    for from_stop in from_stops:
        route_nodes = findroute.get_route(
            nodes[from_stop], nodes.itervalues(),
            is_goal = lambda n: n.station_id == to_station.id)

        route = [Stop.objects.select_related().get(service = nn.service_id,
                                                   station = nn.station_id)
                 for nn in route_nodes]

        def collapse_route(stops):
            class RouteNode:
                def __init__(self, sstop, stime, estop, etime, cost):
                    self.start_stop = sstop
                    self.start_time = stime
                    self.end_stop   = estop
                    self.end_time   = etime
                    self.cost       = cost

                def __key(self):
                    return (self.start_stop, self.start_time,
                            self.end_stop,   self.end_time,
                            self.cost)

                def __cmp__(self, other):
                    return cmp(self.__key(), other.__key())

            route = []
            def route_append(start, end, cost):
                # For last nodes of a service, use arrival_time. If we have
                # only one node in the path, it may be None, in which case
                # use 0 instead.
                route.append(RouteNode(start,
                                       addminutes(
                                           start.service.departure_time,
                                           start.departure_time),
                                       end,
                                       addminutes(
                                           end.service.departure_time,
                                           (end.arrival_time if
                                            end.arrival_time else 0)),
                                       cost))

            # There may be an extra edge to the same station at the start of
            # the route.
            if len(stops) > 1:
                if stops[0].station == stops[1].station:
                    stops = stops[1:]

            start_stop = stops[0]
            prev_stop = start_stop
            total_cost = 0
            for ss in stops[1:]:
                if start_stop.service.id != ss.service.id:
                    route_append(start_stop, prev_stop, total_cost)

                    total_cost = 0
                    start_stop = ss
                    prev_stop = ss
                else:
                    conn = Connection.objects.\
                        get(out_of = prev_stop.station, to = ss.station)
                    # print "%s: %s -> %s: %d" % (ss.service,
                    #                             prev_stop.station,
                    #                             ss.station,
                    #                             conn.cost)
                    total_cost += conn.cost
                    prev_stop = ss
            else:
                route_append(start_stop, ss, total_cost)

            return route

        route = tuple(collapse_route(route))
        if not route in routes:
            routes.append(route)

    vals.update({'routes': routes, 'last_reserved': last_reserved})
    return render_to_response('get_route.html', vals,
                              context_instance = RequestContext(request))
