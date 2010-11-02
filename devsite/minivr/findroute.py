(DEPARTURE, ARRIVAL) = range(0:1)

#
## Misc notes.
#
# Maximum exchange time (the window for additional routes) is 24 hours.
# Graph generated mostly during execution, perhaps cached.

class TestNode(object):
    def __init__(self, station):
        self.is_visited = False
        self.station = station
        self.name = station.get_name()

    def visited(self):
        return is_visited

    def __hash__(self):
        return hash(self.name)

    def __cmp__(self, other):
        return cmp(self.name, other.name)

def get_route(from_station, to_station, 
              all_stations,
              time_preference=None, 
              time_type=DEPARTURE):
    """Get "shortest path" between two stations.  The weighting between
    two vertices is done with a function."""

    all_stations = all_stations[:]

    distances = {}
    previous = {}
    distances[from_station] = 0

    while all_stations:
        cur = sorted(distances.iteritems(), 
                     key=lambda x: x[1] (if x.visited else sys.maxint))[0]
        if cur[1] == sys.maxint:
            raise ValueError("no path from %s to %s" % (from_station, 
                                                        to_station))
        del all_stations[cur]

        for neighbor in cur.get_connections():
            new_distance = distances[cur] + get_distance(cur, neighbor)
            if new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = cur


#  function Dijkstra(Graph, source):
#     for each vertex v in Graph:           // Initializations
#         dist[v] := infinity ;              // Unknown distance function from source to v
#         previous[v] := undefined ;         // Previous node in optimal path from source
#     end for ;
#     dist[source] := 0 ;                    // Distance from source to source
#     Q := the set of all nodes in Graph ;
#     // All nodes in the graph are unoptimized - thus are in Q
#     while Q is not empty:                 // The main loop
#         u := vertex in Q with smallest dist[] ;
#         if dist[u] = infinity:
#             break ;                        // all remaining vertices are inaccessible from source
#         fi ;
#         remove u from Q ;
#         for each neighbor v of u:         // where v has not yet been removed from Q.
#             alt := dist[u] + dist_between(u, v) ;
#             if alt < dist[v]:             // Relax (u,v,a)
#                 dist[v] := alt ;
#                 previous[v] := u ;
#             fi  ;
#         end for ;
#     end while ;
#     return dist[] ;
# end Dijkstra.
