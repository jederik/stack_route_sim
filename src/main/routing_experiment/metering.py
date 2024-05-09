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
        if name == "demanded_efficiency":
            return self.demanded_efficiency()
        if name == "route_insertion_duration":
            return self.route_update_duration()
        if name == "distance_update_duration":
            return self.distance_update_time()
        if name == "propagated_route_length":
            return self.propagated_route_length()
        raise Exception(f"metric not supported: {name}")

    def route_cost(self, source: NodeId, route: Route) -> Cost:
        route_cost = 0
        node = source
        for port_num in route:
            port = self.network.nodes[node].ports[port_num]
            route_cost += port.cost
            node = port.target_node
        return route_cost

    def transmissions_per_node(self):
        return self.measurement_session.get(measurements.TRANSMISSION_COUNT) / len(self.network.nodes)

    def routability(self):
        total_supply = total_demand = 0
        reachabilities = graphs.reachabilities(self.graph)
        for source, _ in enumerate(self.network.nodes):
            for target, _ in enumerate(self.network.nodes):
                if reachabilities[source][target]:
                    demand = self.routers[source].demand(target) / self.overall_demand
                    demand = 1
                    total_demand += demand
                    if self.routers[source].has_route(target):
                        total_supply += demand
        return total_supply / total_demand

    def efficiency(self):
        route_lengths = 0
        node_distances = 0
        distances = graphs.distances(self.graph)
        for i in range(len(self.network.nodes)):
            for j in range(len(self.network.nodes)):
                route = self.routers[i].route(j)
                if route is not None:
                    route_lengths += self.route_cost(i, route)
                    node_distances += distances[i][j]
        if route_lengths == 0:
            return 1
        return node_distances / route_lengths

    def demanded_efficiency(self):
        route_lengths = 0
        node_distances = 0
        distances = graphs.distances(self.graph)
        for i in range(len(self.network.nodes)):
            for j in range(len(self.network.nodes)):
                demand = self.routers[i].demand(j) / self.overall_demand
                route = self.routers[i].route(j)
                if route is not None:
                    route_lengths += self.route_cost(i, route) * demand
                    node_distances += distances[i][j] * demand
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
