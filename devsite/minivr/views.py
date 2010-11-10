# coding=utf-8

from datetime import date, datetime
from decimal  import Decimal

from django.core.urlresolvers import reverse
from django.db                import connection
from django.db.models         import F, Q, Min
from django.http              import HttpResponseRedirect
from django.shortcuts         import render_to_response, get_object_or_404
from django.template          import RequestContext

from minivr                          import findroute
from minivr.models                   import Ticket, CustomerType, \
                                            Service, Stop, Station, Connection
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

def list_stations(request):
    stations = Station.objects.order_by('name')
    L = []
    for letter in sorted(set([x.name[0] for x in stations])):
        SL = [x for x in stations if x.name.startswith(letter)]
        L.append((letter, list(sorted(SL))))

    return render_to_response(
            'list_stations.html',
            {'stations':stations, 'stations_by_initial':L})

def get_route(request):
    # Passed to the template even in the case of errors, so that it can fill in
    # the form with what the user previously input.
    vals = dict(filter(lambda (k,v): v != '', request.GET.iteritems()))

    vals['customer_types'] = CustomerType.objects.all()

    now = datetime.now()
    vals.setdefault('h',  now.hour)
    vals.setdefault('m',  now.minute)
    vals.setdefault('y',  now.year)
    vals.setdefault('mo', now.month)
    vals.setdefault('d',  now.day)

    vals.setdefault('margin', 5)

    if not request.GET:
        return render_to_response('get_route.html', vals)

    error = False
    try:
        # Do this first because it needs to be an int for the template to work.
        customer_type_id = vals['customer']
        vals['customer'] = int(customer_type_id)

        from_station_name = vals['from']
        to_station_name   = vals['to']
        time_type         = vals['type']

        if time_type == 'departure':
            search_forwards = True
        elif time_type == 'arrival':
            search_forwards = False
        else:
            raise ValueError

        switch_margin = int(vals['margin'])

        wanted_hour = int(vals['h'])
        if not 0 <= wanted_hour < 24:
            raise ValueError

        wanted_minute = int(vals['m'])
        if not 0 <= wanted_minute < 60:
            raise ValueError

        wanted_year  = int(vals['y'])
        wanted_month = int(vals['mo'])
        wanted_day   = int(vals['d'])

        wanted_weekday = \
            date(wanted_year, wanted_month, wanted_day).isoweekday()

        # Minutes from midnight. This ensures that in the queries below, e.g.
        # 23:00 + 120 exceeds 21:00.
        wanted_time = wanted_hour * 60 + wanted_minute

        # This query is too complicated for me to be able to map it into
        # Django. Sorry, folks.
        #
        # Basically, we just want the valid (service_id,station_id) pairs
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
            '       AND minivr_service.free_seats > 0'

            #       FIXME: this doesn't take into account the fact that the
            #       time may wrap into another date. That's not as trivial to
            #       handle as it may seem.
            '       AND (minivr_stop.year_min IS NULL '
            '            OR minivr_stop.year_min <= %%s)'
            '       AND (minivr_stop.year_max IS NULL '
            '            OR minivr_stop.year_max >= %%s)'
            '       AND minivr_stop.month_min <= %%s'
            '       AND minivr_stop.month_max >= %%s'
            '       AND minivr_stop.weekday_min <= %%s'
            '       AND minivr_stop.weekday_max >= %%s'
            '       AND minivr_stop.departure_time IS NOT NULL)'
            '  AS ts'
            #           Positive remainder of ts.t / (24*60)
            '  ORDER BY ts.t - (24*60) * floor(ts.t / (24*60)) %s')

        if not search_forwards:
            (from_station_name, to_station_name) = \
                (to_station_name, from_station_name)

            query = query.replace('stop.departure_time', 'stop.arrival_time')

        params = [wanted_time, from_station_name,
                  wanted_year, wanted_year,
                  wanted_month, wanted_month,
                  wanted_weekday, wanted_weekday]

        # Just to get a better error message...
        Station.objects.get(name__iexact = from_station_name)

        cursor = connection.cursor()
        cursor.execute(query % "DESC", params)

        # Drop t here instead of in the query, so that we can write just the
        # Kleene star instead of all the minivr_stop column names.
        from_stops_before = [Stop(*s[1:]) for s in cursor.fetchall()]

        if len(from_stops_before) == 0:
            raise Stop.DoesNotExist

        # Same thing again, but now grab ones immediately after instead of
        # before the given time.
        cursor = connection.cursor()
        cursor.execute(query % "ASC", params)
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
    except Stop.DoesNotExist:
        vals.update({'error': 'Mikään vuoro ei pysähdy annetulla asemalla '
                              'annettuna päivänä.'})
        error = True

    if error:
        return render_to_response('get_route.html', vals)

    nodes = {}
    def get_and_cache_node(key, stop):
        node = nodes.get(key, None)
        if node == None:
            node = StopNode(stop)
            nodes[key] = node
        return node

    # FIXME: like the raw SQL query above, this doesn't handle everything.
    stop_enabled_on_wanted_date = \
        Q(year_min__isnull = True) | \
        Q(year_min__lte    = wanted_year,
          year_max__gte    = wanted_year,
          month_min__lte   = wanted_month,
          month_max__gte   = wanted_month,
          weekday_min__lte = wanted_weekday,
          weekday_max__gte = wanted_weekday)

    class StopNode(object):
        def __init__(self, stop):
            self.service_id             = stop.service_id
            self.station_id             = stop.station_id
            self.arrival_time           = stop.arrival_time
            self.departure_time         = stop.departure_time
            self.service_departure_time = stop.service.departure_time
            self.successors             = None
            self.from_node              = None
            self.previous               = None

        def __hash__(self):
            return hash((self.service_id, self.station_id))

        def __eq__(self, other):
            return isinstance(other, StopNode) and cmp(self, other) == 0

        def __ne__(self, other):
            return not self == other

        def __cmp__(self, other):
            return cmp(( self.service_id,  self.station_id),
                       (other.service_id, other.station_id))

        def get_connections(self, from_node):
            new_from = False
            if self.from_node != from_node:
                self.from_node = from_node
                new_from = True

            if self.successors == None:
                self.__compute_successors()

            # If we got a new from_node and whether we are a from_node changed,
            # recompute the switch_successors only, since they're the only ones
            # that care about it.
            elif new_from and (self == self.from_node) != (self == from_node):
                self.__compute_switch_successors()

            return self.successors

        def __compute_successors(self):
            self.successors = []

            # There are two classes of successors for each node.
            self.__compute_switch_successors()
            self.__compute_continue_successors()

        def __compute_switch_successors(self):
            # Firstly, one can switch from one train to another available
            # departing (arriving) one if the time between the first one's
            # arrival (departure) and the latter one's departure (arrival) is
            # short enough.
            #
            # This is only a possible action if we're not at the starting
            # point.
            if self == self.from_node:
                return

            stops = Stop.objects.select_related().\
                         exclude(service = self.service_id).\
                         filter (station = self.station_id,
                                 service__free_seats__gt = 0).\
                         filter (stop_enabled_on_wanted_date)

            if search_forwards:
                stops = stops.filter(departure_time__isnull = False)
            else:
                stops = stops.filter(arrival_time__isnull = False)

            for stop in stops:
                key = (stop.service_id, self.station_id)
                next = get_and_cache_node(key, stop)

                assert next.station_id == self.station_id

                if search_forwards:
                    prev_dt = self.service_departure_time
                    next_dt = next.service_departure_time
                else:
                    prev_dt = next.service_departure_time
                    next_dt = self.service_departure_time

                timediff = (next_dt.hour   - prev_dt.hour) * 60 + \
                           (next_dt.minute - prev_dt.minute)

                # Don't bother adding train-switch edges for nodes that lack an
                # arrival (departure) time: we can only enter them by switching
                # trains in the middle of the route, and there's no need to
                # switch again immediately thereafter.
                if (self.arrival_time if search_forwards
                                        else self.departure_time) != None:
                    if search_forwards:
                        timediff += next.departure_time - self.arrival_time
                    else:
                        timediff += self.departure_time - next.arrival_time

                    timediff %= 24*60
                    if timediff >= switch_margin:
                        self.successors.append((next, timediff))

        def __compute_continue_successors(self):
            # Secondly, one can continue in the same train, if it will ever
            # depart (arrive).
            if search_forwards:
                if self.departure_time == None:
                    return

                next_stop =\
                    Stop.objects.select_related().\
                         filter(service = self.service_id,
                                arrival_time__gt = self.departure_time).\
                         filter(stop_enabled_on_wanted_date).\
                         order_by('arrival_time')[0]
            else:
                if self.arrival_time == None:
                    return

                next_stop =\
                    Stop.objects.select_related().\
                         filter(service = self.service_id,
                                departure_time__isnull = False,
                                departure_time__lt = self.arrival_time).\
                         filter(stop_enabled_on_wanted_date).\
                         order_by('-departure_time')[0]

            key = (self.service_id, next_stop.station_id)
            next = get_and_cache_node(key, next_stop)

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
    costs_cache = {}
    stops_cache = {}

    def get_route(from_node):
        route_nodes = findroute.get_route(
                          from_node,
                          lambda n: n.station_id == to_station.id,
                          from_node)

        if not route_nodes:
            return False

        route = []
        for node in route_nodes:
            key = (node.service_id, node.station_id)
            stop = stops_cache.get(key, None)
            if stop == None:
                stop = Stop.objects.select_related().get(service = key[0],
                                                         station = key[1])
                stops_cache[key] = stop
            route.append(stop)

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
                        Ticket.objects.get(
                            service = start.service_id,
                            customer_type = customer_type_id).price_per_cost

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
                while len(stops) > 1 and \
                      stops[0].station_id == stops[1].station_id:
                    stops = stops[1:]
            else:
                while len(stops) > 1 and \
                      stops[-1].station_id == stops[-2].station_id:
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
                    from_to = (prev_stop.station_id, ss.station_id)
                    cost = costs_cache.get(from_to, None)
                    if cost == None:
                        [(cost,)] = Connection.objects.\
                            filter(out_of = from_to[0], to = from_to[1]).\
                            values_list('cost')
                        costs_cache[from_to] = cost

                    service_cost += cost
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
            node = get_and_cache_node(key, stop)

            if node in used_from_nodes:
                continue
            used_from_nodes.add(node)

            if get_route(node):
                count += 1
                if count == WANTED_ROUTE_COUNT:
                    break

    get_routes(from_stops_before)

    # from_stops_before is in descending order, but we want all our routes in
    # ascending order.
    routes.reverse()

    get_routes(from_stops_after)

    vals.update({'routes': routes})

    return render_to_response('get_route.html', vals,
                              context_instance = RequestContext(request))
