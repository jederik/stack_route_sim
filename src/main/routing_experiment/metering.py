import numpy.random

import instrumentation
from experimentation.metering import MetricName
from routing_experiment import net, routing, measurements, graphs
from routing_experiment.graphs import CostGraph
from routing_experiment.net import NodeId, Cost
from routing_experiment.routing import Route


class MetricsCalculator:
    def __init__(self, network: net.Network, routers: list[routing.Router],
                 measurement_reader: instrumentation.MeasurementReader,
                 graph: CostGraph):
        self.measurement_session = measurement_reader.session()
        self.network = network
        self.routers = routers
        self.graph = graph

    def _calculate_metric(self, name) -> float:
        if name == "transmissions_per_node":
            return self.transmissions_per_node()
        if name == "routability_rate":
            return self.routability_rate()
        if name == "efficiency":
            return self.efficiency()
        if name == "efficient_routability":
            return self.routability_rate() * self.efficiency()
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

    def routability_rate(self):
        num_samples = 100
        n = len(self.network.nodes)

        routable_pairs = 0
        for _ in range(num_samples):
            source = numpy.random.randint(n)
            target = numpy.random.randint(n)
            if self.routers[source].has_route(target):
                routable_pairs += 1

        reachable_pairs = 0
        reachabilities = graphs.reachabilities(self.graph)
        for _ in range(num_samples):
            source = numpy.random.randint(n)
            target = numpy.random.randint(n)
            if reachabilities[source][target]:
                reachable_pairs += 1

        return routable_pairs / reachable_pairs

    def efficiency(self):
        num_samples = 1000
        n = len(self.network.nodes)

        total_route_length = 0
        total_node_distance = 0
        distances = graphs.distances(self.graph)
        for _ in range(num_samples):
            source = numpy.random.randint(n)
            target = numpy.random.randint(n)
            route = self.routers[source].route(target)
            if route is not None:
                total_route_length += self.route_cost(source, route)
                total_node_distance += distances[source][target]
        if total_route_length == 0:
            return 1
        return total_node_distance / total_route_length

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


def _create_metrics_calculator(network, routers, measurement_reader):
    return MetricsCalculator(
        network=network,
        routers=routers,
        measurement_reader=measurement_reader,
        graph=to_graph(network),
    )
