# coding=utf-8

import datetime

from django.core.urlresolvers import reverse
from django.db.models         import Q, Min
from django.http              import HttpResponseRedirect
from django.shortcuts         import render_to_response, get_object_or_404
from django.template          import RequestContext

from minivr                          import findroute
from minivr.models                   import Service, Stop, Station
from minivr.templatetags.minivr_time import addminutes

def index(request):
    services = Service.objects.\
                   filter(free_seats__gt = 0).\
                   order_by('departure_time')
    last_reserved = int(request.GET.get('last_reserved', -1))
    return render_to_response(
        'minivr/index.html',
        {'services':services, 'last_reserved':last_reserved},
        context_instance = RequestContext(request))

def service_detail(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    stops = service.schedule.order_by('departure_time')
    return render_to_response('minivr/service_detail.html',
                              {'service':service, 'stops':stops})

def service_reserve(request, service_id):
    service = get_object_or_404(Service, id = service_id)
    service.free_seats -= 1
    url = reverse('minivr.views.index') + '?last_reserved=' + service_id
    service.save()
    return HttpResponseRedirect(url)

def get_route(request):
    if not request.GET:
        return render_to_response('minivr/get_route.html')

    # Passed to the template even in the case of errors, so that it can fill in
    # the form with what the user previously input.
    vals = dict((k, unicode(v)) for (k,v) in request.GET.iteritems())

    error = False
    try:
        from_station_name = request.GET['from']
        to_station_name   = request.GET['to']
        time              = datetime.time(hour   = int(request.GET['h']),
                                          minute = int(request.GET['m']))
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

        # Django doesn't understand intervals, so we have to do this manually.
        from_stops = Stop.objects.\
                filter(station__name__iexact = from_station_name).\
                extra(
                    where = [
                        '(minivr_service.departure_time = %s ' + \
                        'OR minivr_service.departure_time ' + \
                        '   + (minivr_stop.departure_time ' + \
                        "      * '1 minute'::interval) = %s)"
                    ],
                    params = [time, time],
                    tables = ['minivr_service']).\
                values_list('service_id', 'station_id')

        to_station = Station.objects.get(name__iexact = to_station_name)

        if len(from_stops) == 0:
            raise Station.DoesNotExist

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
        return render_to_response('minivr/get_route.html', vals)

    # We can use an arbitrary starting stop since we can switch trains at
    # zero cost anyway.
    from_stop = from_stops[0]

    from_stop_station_id = from_stop[1]

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
            return self.station_id == from_stop_station_id

    # The filter is to ignore route starting stops which aren't at our "from"
    # stations. (This could be doing more sophisticated rejection, but this is
    # just necessary to avoid an error when adding successors.)
    all_stops = Stop.objects.\
                    order_by('service__id', '-departure_time').\
                    filter( Q(station = from_stop_station_id) | \
                           ~Q(arrival_time = None))

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
                # FIXME: we have to reject negative weights here because
                # Dijkstra's algorithm can't handle them. Either switch
                # algorithms or figure out a better way of looking at trains
                # before the target time.
                if timediff >= 0:
                    node.successors.append((next, timediff))
            else:
                timediff += next.departure_time - node.arrival_time
                if 0 <= timediff <= findroute.TRAIN_SWITCH_TIME:
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
        # But if we're at the "from" station, use the departure time, because
        # the passenger doesn't have to wait at the station.
        timediff =\
            next.arrival_time - \
            (node.departure_time if node.is_at_from() else node.arrival_time)

        node.successors.append((next, timediff))

    route_nodes = findroute.get_route(
        nodes[from_stop], nodes.itervalues(),
        is_goal = lambda n: n.station_id == to_station.id)

    route = []
    for i,n in enumerate(route_nodes):
        stop = Stop.objects.select_related().\
                            get(service = n.service_id, station = n.station_id)

        # For the last node, use arrival_time. If we have only one node in the
        # path, it may be None, in which case use 0 instead.
        stop_time = addminutes(
            stop.service.departure_time,
            stop.departure_time if i < len(route_nodes)-1
            else stop.arrival_time or 0)

        route.append([str(x) for x in (stop.station, stop.service, stop_time)])

    vals.update({'route':route if route else 'No route!'})
    return render_to_response('minivr/get_route.html', vals)
