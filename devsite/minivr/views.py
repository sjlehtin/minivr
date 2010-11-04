# coding=utf-8

from decimal import Decimal

from django.core.urlresolvers import reverse
from django.db                import connection
from django.db.models         import F, Q, Min
from django.http              import HttpResponseRedirect
from django.shortcuts         import render_to_response, get_object_or_404
from django.template          import RequestContext

from minivr                          import findroute
from minivr.models                   import Ticket, Service, Stop, Station,\
                                            Connection
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
        # corresponding to the given "from" station in order of time, near to
        # the given time. (Either before or after depending on the sort order.)
        query = (
            'SELECT * FROM'
            '  (SELECT'
            '     (60 * extract(hour   from minivr_service.departure_time)'
            '       +   extract(minute from minivr_service.departure_time)'
            '       + minivr_stop.departure_time'
            '       - %%s)'
            '     AS t,'
            '     minivr_stop.*'
            '     FROM minivr_stop'
            '         INNER JOIN minivr_service'
            '                 ON (minivr_stop.service_id = minivr_service.id)'
            '         INNER JOIN minivr_station'
            '                 ON (minivr_stop.station_id = minivr_station.id)'
            '     WHERE UPPER(minivr_station.name::text) = UPPER(%%s)'
            '       AND minivr_stop.departure_time IS NOT NULL)'
            '  AS ts'
            #           Positive remainder of ts.t / (24*60)
            '  ORDER BY ts.t - (24*60) * floor(ts.t / (24*60)) %s'
            '  LIMIT 3')

        cursor = connection.cursor()
        cursor.execute(query % "DESC", [time, from_station_name])

        # Drop t here instead of in the query, so that we can write just the
        # Kleene star instead of all the minivr_stop column names.
        from_stops = [Stop(*s[1:]) for s in reversed(cursor.fetchall())]

        if len(from_stops) == 0:
            raise Station.DoesNotExist

        # Same thing again, but now grab ones immediately after instead of
        # before the given time.
        cursor = connection.cursor()
        cursor.execute(query % "ASC", [time, from_station_name])
        from_stops.extend(Stop(*s[1:]) for s in cursor.fetchall())

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

    nodes = {}
    def get_or_add(key, stop):
        node = nodes.get(key, None)
        if node == None:
            node = StopNode(stop)
            nodes[key] = node
        return node

    from_stop = None

    class StopNode(object):
        def __init__(self, stop):
            self.service_id             = stop.service_id
            self.station_id             = stop.station_id
            self.arrival_time           = stop.arrival_time
            self.departure_time         = stop.departure_time
            self.service_departure_time = stop.service.departure_time
            self.successors             = None

        def __hash__(self):
            return hash((self.service_id, self.station_id))

        def __eq__(self, other):
            return isinstance(other, StopNode) and cmp(self, other) == 0

        def __cmp__(self, other):
            return cmp(( self.service_id,  self.station_id),
                       (other.service_id, other.station_id))

        def get_connections(self):
            if self.successors == None:
                self.__compute_successors()
            return self.successors

        def __compute_successors(self):
            self.successors = []

            # There are two classes of successors for each node.

            # Firstly, one can switch from one train to another departing one
            # if the time between the first one's arrival and the latter one's
            # departure is short enough.
            for stop in Stop.objects.select_related().\
                             filter(station = self.station_id,
                                    departure_time__isnull = False).\
                             exclude(service = self.service_id):

                key = (stop.service, self.station_id)
                next = get_or_add(key, stop)

                assert next.station_id == self.station_id

                self_dt = self.service_departure_time
                next_dt = next.service_departure_time

                timediff = ((next_dt.hour   - self_dt.hour) * 60 + \
                            (next_dt.minute - self_dt.minute)) + \
                           next.departure_time

                # For the "from" stop, there is no time limit, and the cost is
                # the difference between the departure times.
                assert from_stop != None

                if self.station_id == from_stop.station_id and \
                   self.service_id == from_stop.service_id:
                    timediff -= self.departure_time
                    timediff %= 24*60
                    self.successors.append((next, timediff))

                # Don't bother adding train-switch edges for nodes that lack an
                # arrival time: we can only enter them by switching trains in
                # the middle of the route, and there's no need to switch again
                # immediately thereafter.
                elif self.arrival_time != None:
                    timediff -= self.arrival_time
                    timediff %= 24*60
                    if timediff >= findroute.TRAIN_SWITCH_TIME:
                        self.successors.append((next, timediff))

            # Secondly, one can continue in the same train, if it will ever
            # depart.

            if self.departure_time == None:
                return

            next_stop = Stop.objects.select_related().\
                             filter(service = self.service_id,
                                    arrival_time__gt = self.departure_time).\
                             order_by('arrival_time')[0]

            key = (self.service_id, next_stop.station)
            next = get_or_add(key, next_stop)

            assert next.service_id == self.service_id

            # By default, use the difference between the arrival times, because
            # we need to include the wait time at a station.
            #
            # But if the arrival time is null, we're at the start of a service:
            # we've already handled the waiting as part of the train switch
            # (which may be the zero-cost start of the route), so use the
            # departure time.
            timediff = next.arrival_time - \
                       (self.arrival_time or self.departure_time)

            self.successors.append((next, timediff))

    routes = []
    for from_stop in from_stops:
        key = (from_stop.service_id, from_stop.station_id)
        route_nodes = findroute.get_route(
                          get_or_add(key, from_stop),
                          lambda n: n.station_id == to_station.id)

        route = [Stop.objects.select_related().get(service = nn.service_id,
                                                   station = nn.station_id)
                 for nn in route_nodes]

        def collapse_route(stops):
            class RouteNode:
                def __init__(self, sstop, stime, estop, etime, price):
                    self.start_stop = sstop
                    self.start_time = stime
                    self.end_stop   = estop
                    self.end_time   = etime
                    self.price      = price

                def __key(self):
                    return (self.start_stop, self.start_time,
                            self.end_stop,   self.end_time,
                            self.price)

                def __cmp__(self, other):
                    return cmp(self.__key(), other.__key())

            route = []
            def route_append(start, end, cost):

                if cost == 0:
                    price = 0
                else:
                    assert start.service_id == end.service_id
                    price_per_cost =\
                        Ticket.objects.get(service = start.service_id,
                                           customer_type = 1).price_per_cost
                    price = (cost * price_per_cost).quantize(Decimal('1.00'))

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
                                       price))

            # There may be extra edges to the same station at the start of the
            # route.
            while len(stops) > 1 and stops[0].station == stops[1].station:
                stops = stops[1:]

            start_stop = stops[0]
            prev_stop = start_stop
            service_cost = 0
            for ss in stops[1:]:
                if start_stop.service_id != ss.service_id:
                    route_append(start_stop, prev_stop, service_cost)

                    service_cost = 0
                    start_stop = ss
                    prev_stop = ss
                else:
                    conn = Connection.objects.\
                        get(out_of = prev_stop.station, to = ss.station)
                    # print "%s: %s -> %s: %d" % (ss.service,
                    #                             prev_stop.station,
                    #                             ss.station,
                    #                             conn.cost)
                    service_cost += conn.cost
                    prev_stop = ss
            else:
                route_append(start_stop, prev_stop, service_cost)

            return route

        route = tuple(collapse_route(route))
        if not route in routes:
            routes.append(route)

    vals.update({'routes': routes, 'last_reserved': last_reserved})
    return render_to_response('get_route.html', vals,
                              context_instance = RequestContext(request))
