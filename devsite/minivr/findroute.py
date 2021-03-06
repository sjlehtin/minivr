import unittest

class GraphNode(object):
    """
    This class describes the interface required from nodes handled by
    get_route().  Used also in unittests, below.
    """
    def __init__(self, id):
        self.id = id
        self.previous = None
        self.connections = []

    def add_connection(self, neighbor, cost):
        self.connections.append((neighbor, cost))

    def get_connections(self):
        return self.connections[:]

    def __hash__(self):
        return hash(self.id)

    def __cmp__(self, other):
        return cmp(self.id, other.id)

def get_route(from_node, is_goal, *connections_args):
    """Get the shortest path from the starting node to the nearest goal."""

    visited = set()
    distances = {}
    distances[from_node] = 0

    while True:
        if not distances:
            return []

        cur = (nn[0] for nn in sorted(distances.iteritems(),
                                      key = lambda x: x[1])).next()

        # The next closest node is the target node.
        if is_goal(cur):
            break

        visited.add(cur)

        for neighbor, distance in cur.get_connections(*connections_args):
            assert distance >= 0
            new_distance = distances[cur] + distance
            old_distance = distances.get(neighbor, None)
            if (old_distance == None or new_distance < old_distance) and \
               not neighbor in visited:
                distances[neighbor] = new_distance
                neighbor.previous   = cur

        del distances[cur]

    route = [cur]
    while cur != from_node:
        cur = cur.previous
        assert cur not in route
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

def test_get_route(from_node, to_node):
    return get_route(from_node, lambda node: node == to_node)

class SimpleLinearTestCase(unittest.TestCase):
    def testRouteToSelf(self):
        a = GraphNode("first")
        route = test_get_route(a, a)
        self.assertEqual(route, [a])

    def testRouteToNeighbor(self):
        a = GraphNode("first")
        b = GraphNode("second")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        route = test_get_route(a, b)
        self.assertEqual(route, [a, b])

    def testRouteToEnd(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 1)
        c.add_connection(b, 1)
        route = test_get_route(a, c)
        self.assertEqual(route, [a, b, c])

    def testRouteFromBeginningToMiddle(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 1)
        c.add_connection(b, 1)
        route = test_get_route(a, b)
        self.assertEqual(route, [a, b])

    def testRouteFromMiddleToEnd(self):
        a = GraphNode("first")
        b = GraphNode("second")
        c = GraphNode("third")
        a.add_connection(b, 1)
        b.add_connection(a, 1)
        b.add_connection(c, 2)
        c.add_connection(b, 2)
        route = test_get_route(b, c)
        self.assertEqual(route, [b, c])

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
        self.assertEqual(test_get_route(self.a, self.b),
                         [self.a, self.d, self.b])

        self.assertEqual(test_get_route(self.a, self.e),
                         [self.a, self.d, self.e])

        self.assertEqual(test_get_route(self.a, self.f),
                         [self.a, self.d, self.f])

        self.assertEqual(test_get_route(self.f, self.g),
                         [self.f, self.g])

        self.assertEqual(test_get_route(self.d, self.g),
                         [self.d, self.e, self.g])

        self.assertEqual(test_get_route(self.e, self.f),
                         [self.e, self.g, self.f])

        self.assertEqual(test_get_route(self.a, self.g),
                         [self.a, self.d, self.e, self.g])

        self.assertEqual(test_get_route(self.g, self.a),
                         [self.g, self.e, self.d, self.a])

class LargeGraphTestCase(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
