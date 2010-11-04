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

WANTED_ROUTE_COUNT = 3

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
            search_forwards = True
        elif time_type == 'arrival':
            search_forwards = False
        else:
            raise ValueError

        # Minutes from midnight. This ensures that in the queries below, e.g.
        # 23:00 + 120 exceeds 21:00.
        time = int(request.GET['h']) * 60 + int(request.GET['m'])

        # This query is too complicated for me to be able to map it into
        # Django. Sorry, folks.
        #
        # Basically, we just want the (service_id,station_id) pairs
        # corresponding to the given "from" station in order of time, near
        # to the given time. (Either before or after depending on the sort
        # order.)
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
            '  ORDER BY ts.t - (24*60) * floor(ts.t / (24*60)) %s')

        if not search_forwards:
            (from_station_name, to_station_name) = \
                (to_station_name, from_station_name)

            query = query.replace('stop.departure_time', 'stop.arrival_time')

        cursor = connection.cursor()
        cursor.execute(query % "DESC", [time, from_station_name])

        # Drop t here instead of in the query, so that we can write just the
        # Kleene star instead of all the minivr_stop column names.
        from_stops_before = [Stop(*s[1:]) for s in cursor.fetchall()]

        if len(from_stops_before) == 0:
            raise Station.DoesNotExist

        # Same thing again, but now grab ones immediately after instead of
        # before the given time.
        cursor = connection.cursor()
        cursor.execute(query % "ASC", [time, from_station_name])
        from_stops_after = [Stop(*s[1:]) for s in cursor.fetchall()]

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

        def get_connections(self, from_stop):
            if self.successors == None:
                self.__compute_successors(from_stop)
            return self.successors

        def __compute_successors(self, from_stop):
            self.successors = []

            # There are two classes of successors for each node.

            # Firstly, one can switch from one train to another departing
            # (arriving) one if the time between the first one's arrival
            # (departure) and the latter one's departure (arrival) is short
            # enough.
            stops = Stop.objects.select_related().\
                                 exclude(service = self.service_id).\
                                 filter (station = self.station_id)

            if search_forwards:
                stops = stops.filter(departure_time__isnull = False)
            else:
                stops = stops.filter(arrival_time__isnull = False)

            for stop in stops:
                key = (stop.service, self.station_id)
                next = get_or_add(key, stop)

                assert next.station_id == self.station_id

                if search_forwards:
                    prev_dt = self.service_departure_time
                    next_dt = next.service_departure_time
                else:
                    prev_dt = next.service_departure_time
                    next_dt = self.service_departure_time

                timediff = (next_dt.hour   - prev_dt.hour) * 60 + \
                           (next_dt.minute - prev_dt.minute)

                # For the "from" stop, there is no time limit, and the cost is
                # the difference between the departure (arrival) times.
                if self.station_id == from_stop.station_id and \
                   self.service_id == from_stop.service_id:

                    if search_forwards:
                        timediff += next.departure_time - self.departure_time
                    else:
                        timediff += self.arrival_time - next.arrival_time

                    timediff %= 24*60
                    self.successors.append((next, timediff))

                # Don't bother adding train-switch edges for non-"from" nodes
                # that lack an arrival (departure) time: we can only enter them
                # by switching trains in the middle of the route, and there's
                # no need to switch again immediately thereafter.
                elif (self.arrival_time if search_forwards
                                        else self.departure_time) != None:
                    if search_forwards:
                        timediff += next.departure_time - self.arrival_time
                    else:
                        timediff += self.departure_time - next.arrival_time

                    timediff %= 24*60
                    if timediff >= findroute.TRAIN_SWITCH_TIME:
                        self.successors.append((next, timediff))

            # Secondly, one can continue in the same train, if it will ever
            # depart (arrive).

            if search_forwards:
                if self.departure_time == None:
                    return

                next_stop =\
                    Stop.objects.select_related().\
                         filter(service = self.service_id,
                                arrival_time__gt = self.departure_time).\
                         order_by('arrival_time')[0]
            else:
                if self.arrival_time == None:
                    return

                next_stop =\
                    Stop.objects.select_related().\
                         filter(service = self.service_id,
                                departure_time__isnull = False,
                                departure_time__lt = self.arrival_time).\
                         order_by('-departure_time')[0]

            key = (self.service_id, next_stop.station)
            next = get_or_add(key, next_stop)

            assert next.service_id == self.service_id

            # By default, use the difference between the arrival (departure)
            # times, because we need to include the wait time at a station.
            #
            # But if the arrival (departure) time is null, we're at the start
            # (end) of a service: we've already handled the waiting as part of
            # the train switch (which may be the zero-cost start of the route),
            # so use the departure (arrival) time.
            if search_forwards:
                timediff = next.arrival_time - \
                           (self.arrival_time or self.departure_time)
            else:
                timediff = (self.departure_time or self.arrival_time) - \
                           next.departure_time

            self.successors.append((next, timediff))

    routes = []

    def get_route(from_node, from_stop):
        route_nodes = findroute.get_route(
                          from_node,
                          lambda n: n.station_id == to_station.id,
                          from_stop)

        if not route_nodes:
            return False

        route = [Stop.objects.select_related().get(service = nn.service_id,
                                                   station = nn.station_id)
                 for nn in route_nodes]

        if not search_forwards:
            route.reverse()

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

            # There may be extra edges to the same station at the start (end)
            # of the route.
            if search_forwards:
                while len(stops) > 1 and stops[0].station == stops[1].station:
                    stops = stops[1:]
            else:
                while len(stops) > 1 and \
                      stops[-1].station == stops[-2].station:
                    stops = stops[:-1]

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
            return True
        return False

    used_from_nodes = set()

    def get_routes(from_stops):
        count = 0
        for stop in from_stops:

            key = (stop.service_id, stop.station_id)
            node = get_or_add(key, stop)

            if node in used_from_nodes:
                continue
            used_from_nodes.add(node)

            if get_route(node, stop):
                count += 1
                if count == WANTED_ROUTE_COUNT:
                    break

    get_routes(from_stops_before)

    # from_stops_before is in descending order, but we want all our routes in
    # ascending order.
    routes.reverse()

    get_routes(from_stops_after)

    vals.update({'routes': routes, 'last_reserved': last_reserved})
    return render_to_response('get_route.html', vals,
                              context_instance = RequestContext(request))
