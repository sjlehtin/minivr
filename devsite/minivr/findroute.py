import unittest

(DEPARTURE, ARRIVAL) = range(0, 2)

class GraphNode(object):
    """
    This class describes the interface required from nodes handled by
    get_route().  Used also in unittests, below.
    """
    def __init__(self, id):
        self.id = id
        self.connections = []

    def add_connection(self, neighbor, cost):
        self.connections.append((neighbor, cost))

    def get_connections(self):
        return self.connections[:]

    def __hash__(self):
        return hash(self.id)

    def __cmp__(self, other):
        return cmp(self.id, other.id)

def get_route(from_station, all_stations, is_goal):
    """Get "shortest path" between two stations."""

    stations = set(all_stations)

    if from_station not in stations:
        raise ValueError("departure station must be in set of all stations")

    distances = {}
    previous = {}
    distances[from_station] = 0

    while stations:
        def get_closest_node():
            candidates = filter(lambda x: x[0] in stations,
                                distances.iteritems())
            if not candidates:
                return None
            closest_nodes = [nn[0] for nn in
                             sorted(candidates, key=lambda x: x[1])]
            return closest_nodes[0]

        cur = get_closest_node()
        if not cur:
            return []

        # The next closest node is the target node.
        if is_goal(cur):
            break

        stations.remove(cur)

        for (neighbor, distance) in cur.get_connections():
            new_distance = distances[cur] + distance
            if ((not neighbor in distances)
                or (new_distance < distances[neighbor])):
                distances[neighbor] = new_distance
                previous[neighbor] = cur

    route = [cur]
    while (cur in previous):
        cur = previous[cur]
        route.insert(0, cur)

    return route

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

def test_get_route(from_node, to_node, nodes):
    return get_route(from_node, nodes, lambda node: node == to_node)

class SimpleLinearTestCase(unittest.TestCase):
    def testRouteToSelf(self):
        a = GraphNode("first")
        route = test_get_route(a, a, [a])
        self.assertEqual(route, [a])

    def testRouteToNeighbor(self):
        a = GraphNode("first")
        b = GraphNode("second")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        route = test_get_route(a, b, [a, b])
        self.assertEqual(route, [a, b])

    def testRouteToEnd(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 1)
        c.add_connection(b, 1)
        route = test_get_route(a, c, [a, b, c])
        self.assertEqual(route, [a, b, c])

    def testRouteFromBeginningToMiddle(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 1)
        c.add_connection(b, 1)
        route = test_get_route(a, b, [a, b, c])
        self.assertEqual(route, [a, b])

    def testRouteFromMiddleToEnd(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 2)
        c.add_connection(b, 2)
        route = test_get_route(b, c, [a, b, c])
        self.assertEqual(route, [b, c])

    def testNoRouteConnectionNotInSet(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 2)
        c.add_connection(b, 2)

        route = test_get_route(a, c, [a, c])
        self.assertEqual(route, [])

class SmallGraphTestCase(unittest.TestCase):
    def setUp(self):
        a = GraphNode("a")
        b = GraphNode("b")
        c = GraphNode("c")
        d = GraphNode("d")
        e = GraphNode("e")
        f = GraphNode("f")
        g = GraphNode("g")
        a.add_connection(d, 1)
        d.add_connection(a, 1)

        b.add_connection(d, 2)
        d.add_connection(b, 2)

        c.add_connection(d, 2)
        d.add_connection(c, 2)

        d.add_connection(e, 4)
        e.add_connection(d, 4)

        d.add_connection(f, 3)
        f.add_connection(d, 3)

        e.add_connection(g, 1)
        g.add_connection(e, 1)

        f.add_connection(g, 3)
        g.add_connection(f, 3)

        self.all_nodes = [a, b, c, d, e, f, g]
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f
        self.g = g

    def testBasic(self):
        self.assertEqual(test_get_route(self.a, self.b, self.all_nodes),
                         [self.a, self.d, self.b])

        self.assertEqual(test_get_route(self.a, self.e, self.all_nodes),
                         [self.a, self.d, self.e])

        self.assertEqual(test_get_route(self.a, self.f, self.all_nodes),
                         [self.a, self.d, self.f])

        self.assertEqual(test_get_route(self.f, self.g, self.all_nodes),
                         [self.f, self.g])

        self.assertEqual(test_get_route(self.d, self.g, self.all_nodes),
                         [self.d, self.e, self.g])

        self.assertEqual(test_get_route(self.e, self.f, self.all_nodes),
                         [self.e, self.g, self.f])

        self.assertEqual(test_get_route(self.a, self.g, self.all_nodes),
                         [self.a, self.d, self.e, self.g])

        self.assertEqual(test_get_route(self.g, self.a, self.all_nodes),
                         [self.g, self.e, self.d, self.a])

class LargeGraphTestCase(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
