import instrumentation
from experimentation.metering import MetricName
from routing_experiment import net, measurements, graphs, routing
from routing_experiment.graphs import CostGraph
from routing_experiment.net import NodeId, Cost
from routing_experiment.routing import Route


class MetricsCalculator:
    def __init__(
            self,
            network: net.Network,
            routers: list[routing.Router],
            graph: CostGraph,
            measurement_session: instrumentation.Session,
    ):
        self.overall_demand = sum(
            [
                sum(
                    [
                        source_router.demand(target)
                        for target in range(len(network.nodes))
                    ]
                )
                for source_router in routers
            ]
        )
        self.measurement_session = measurement_session
        self.network = network
        self.routers = routers
        self.graph = graph

    def _calculate_metric(self, name) -> float:
        if name == "transmissions_per_node":
            return self.transmissions_per_node()
        if name == "routability":
            return self.routability()
        if name == "efficiency":
            return self.efficiency()
        if name == "efficient_routability":
            return self.routability() * self.efficiency()
        if name == "demanded_routability":
            return self.demanded_routability()
        if name == "demanded_efficiency":
            return self.demanded_efficiency()
        if name == "demanded_efficient_routability":
            return self.demanded_routability() * self.demanded_efficiency()
        if name == "route_insertion_duration":
            return self.route_update_duration()
        if name == "distance_update_duration":
            return self.distance_update_time()
        if name == "propagated_route_length":
            return self.propagated_route_length()
        if name == "route_failures":
            return self.route_failures()
        raise Exception(f"metric not supported: {name}")

    def _route_cost(self, source: NodeId, route: Route) -> Cost:
        route_cost = 0
        node = source
        for port_num in route:
            port = self.network.nodes[node].ports[port_num]
            route_cost += port.cost
            node = port.target_node
        return route_cost

    def _route_correct(self, source: NodeId, route: Route, target: NodeId) -> bool:
        node = source
        for port in route:
            if port not in self.network.nodes[node].ports:
                return False
            node = self.network.nodes[node].ports[port].target_node
        return node == target

    def transmissions_per_node(self):
        return self.measurement_session.get(measurements.TRANSMISSION_COUNT) / len(self.network.nodes)

    def route_failures(self):
        total_failures = total_routable_pairs = 0
        for source, _ in enumerate(self.network.nodes):
            for target, _ in enumerate(self.network.nodes):
                if self.routers[source].has_route(target):
                    total_routable_pairs += 1
                    route = self.routers[source].route(target)
                    if not self._route_correct(source, route, target):
                        total_failures += 1
        return total_failures / total_routable_pairs

    def routability(self):
        total_supply = total_demand = 0
        reachabilities = graphs.reachabilities(self.graph)
        for source, _ in enumerate(self.network.nodes):
            for target, _ in enumerate(self.network.nodes):
                if reachabilities[source][target]:
                    total_demand += 1
                    if self.routers[source].has_route(target):
                        route = self.routers[source].route(target)
                        if self._route_correct(source, route, target):
                            total_supply += 1
        return total_supply / total_demand

    def efficiency(self):
        route_lengths = 0
        node_distances = 0
        distances = graphs.distances(self.graph)
        for source in range(len(self.network.nodes)):
            for target in range(len(self.network.nodes)):
                if self.routers[source].has_route(target):
                    route = self.routers[source].route(target)
                    if route is not None:
                        if self._route_correct(source, route, target):
                            route_lengths += self._route_cost(source, route)
                            node_distances += distances[source][target]
        if route_lengths == 0:
            return 1
        return node_distances / route_lengths

    def demanded_routability(self):
        total_supply = total_demand = 0
        reachabilities = graphs.reachabilities(self.graph)
        for source, _ in enumerate(self.network.nodes):
            for target, _ in enumerate(self.network.nodes):
                if reachabilities[source][target]:
                    demand = self.routers[source].demand(target) / self.overall_demand
                    total_demand += demand
                    if self.routers[source].has_route(target):
                        route = self.routers[source].route(target)
                        if self._route_correct(source, route, target):
                            total_supply += demand
        return total_supply / total_demand

    def demanded_efficiency(self):
        route_lengths = 0
        node_distances = 0
        distances = graphs.distances(self.graph)
        for source in range(len(self.network.nodes)):
            for target in range(len(self.network.nodes)):
                demand = self.routers[source].demand(target) / self.overall_demand
                route = self.routers[source].route(target)
                if route is not None:
                    if self._route_correct(source, route, target):
                        route_lengths += self._route_cost(source, route) * demand
                        node_distances += distances[source][target] * demand
        if route_lengths == 0:
            return 1
        return node_distances / route_lengths

    def route_update_duration(self) -> float:
        return self.measurement_session.rate(measurements.ROUTE_UPDATE_SECONDS_SUM, measurements.ROUTE_INSERTION_COUNT)

    def distance_update_time(self) -> float:
        return self.measurement_session.rate(measurements.DISTANCE_UPDATE_SECONDS_SUM,
                                             measurements.ROUTE_INSERTION_COUNT)

    def propagated_route_length(self) -> float:
        return self.measurement_session.rate(measurements.RECEIVED_ROUTE_LENGTH, measurements.ROUTE_INSERTION_COUNT)

    def scrape(self, metrics: list[MetricName]):
        return {
            metric_name: self._calculate_metric(metric_name)
            for metric_name in metrics
        }


def to_graph(network: net.Network) -> graphs.CostGraph:
    return {
        node_id: {
            port.target_node: port.cost
            for port in node.ports.values()
        }
        for node_id, node in enumerate(network.nodes)
    }


def _create_metrics_calculator(network: net.Network, routers: list[routing.Router], measurement_session: instrumentation.Session):
    return MetricsCalculator(
        measurement_session=measurement_session,
        network=network,
        routers=routers,
        graph=to_graph(network),
    )
