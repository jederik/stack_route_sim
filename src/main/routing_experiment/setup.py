import logging
import random
from typing import Callable

import experimentation
import instrumentation
from . import net, routing, graphs, route_storage, stacking, propagation
from .advertising import RouteAdvertisement, AdvertisementHandler, RouteAdvertiser, SelfAdvertiser
from .extendable_router import ExtendableRouter
from .metering import _create_metrics_calculator
from .net import NodeId
from .recovery import LinkFailureAdvertisement, LinkFailureAdvertisementHandler, LinkFailureAdvertiser
from .search import Searcher, RouteSearchMessage

CostGenerator = Callable[[random.Random, int, int], tuple[float, float]]


class RoutingCandidate(experimentation.Candidate):
    def __init__(
            self,
            routers: list[routing.Router],
            measurement_reader: instrumentation.MeasurementReader,
            network: net.Network,
            rnd: random.Random,
            link_fail_rate: float,
            cost_generator: CostGenerator,
    ):
        self.cost_generator = cost_generator
        self.link_fail_rate = link_fail_rate
        self.rnd = rnd
        self.measurement_reader = measurement_reader
        self.network = network
        self.routers = routers

    def run_step(self):
        self._tick_routers()
        self._ruin_and_recreate_links()

    def _tick_routers(self):
        for router in self.routers:
            router.tick()

    def scrape_metrics(self, metrics: list[str]) -> dict[str, float]:
        measurement_session = self.measurement_reader.session()
        metrics_calculator = _create_metrics_calculator(self.network, self.routers, measurement_session)
        return metrics_calculator.scrape(metrics)

    def _ruin_and_recreate_links(self):
        failing_links = [
            (node_id, port_num)
            for node_id, node in enumerate(self.network.nodes)
            for port_num, port in node.ports.items()
            if node_id > port.target_node and self.link_fail_rate > self.rnd.random()
        ]
        for (node_id, port_num) in failing_links:
            self.network.disconnect(node_id, port_num)
            self._establish_random_link()

    def _establish_random_link(self):
        node1 = self.rnd.choice(range(len(self.network.nodes)))
        node2 = self.rnd.choice(range(len(self.network.nodes)))
        cost, backward_cost = self.cost_generator(self.rnd, node1, node2)
        self.network.connect(node1, node2, cost, backward_cost)


def cost_generator_same(rnd: random.Random, i: int, j: int) -> tuple[float, float]:
    return 1, 1


def cost_generator_uniform(rnd: random.Random, i: int, j: int) -> tuple[float, float]:
    return rnd.random(), rnd.random()


def generate_network(config, rnd: random.Random, tracker: instrumentation.Tracker, cost_generator: CostGenerator):
    graph = _generate_graph(config, rnd, cost_generator)
    return _graph_to_network(graph, tracker)


def _generate_graph(config, rnd, cost_generator: CostGenerator):
    strategy = config["strategy"] if "strategy" in config else "gilbert"
    if strategy == "gilbert":
        graph = graphs.generate_gilbert_graph(
            n=config["node_count"],
            p=config["density"],
            rnd=rnd,
            cost_generator=lambda i, j: cost_generator(rnd, i, j),
        )
    elif strategy == "watts_strogatz":
        graph = graphs.generate_watts_strogatz_graph(
            n=config["node_count"],
            k=config["degree"],
            beta=config["beta"],
            rnd=rnd,
            cost_generator=lambda i, j: cost_generator(rnd, i, j),
        )
    else:
        raise Exception(f"unknown graph generation strategy: {strategy}")
    return graph


def _create_cost_generator(config) -> CostGenerator:
    cost_distribution = config["cost_distribution"] if "cost_distribution" in config else "same"
    cost_generator: Callable[[random.Random, int, int], tuple[float, float]]
    if cost_distribution == "same":
        return cost_generator_same
    elif cost_distribution == "uniform":
        return cost_generator_uniform
    else:
        raise Exception(f"unknown cost distribution: {cost_distribution}")


def _graph_to_network(graph: graphs.CostGraph, tracker: instrumentation.Tracker) -> net.Network:
    network = net.Network(len(graph), tracker)
    for vertex_id, vertex in graph.items():
        for successor_id, forward_cost in vertex.items():
            if successor_id > vertex_id:
                backward_cost = graph[successor_id][vertex_id]
                network.connect(vertex_id, successor_id, forward_cost, backward_cost)
    return network


def _create_router_factory(strategy_config, node_count: int) -> routing.RouterFactory:
    constructor: Callable[[dict[str], random.Random, int], routing.RouterFactory]
    constructor = ExtendableRouterFactory
    return constructor(strategy_config, random.Random(), node_count)


def create_candidate(config, rnd: random.Random) -> experimentation.Candidate:
    tracker, measurement_reader = instrumentation.setup()
    router_factory = _create_router_factory(config["routing"], config["network"]["node_count"])
    cost_generator = _create_cost_generator(config)
    network = generate_network(config["network"], rnd, tracker, cost_generator)
    routers = [
        router_factory.create_router(adapter, node_id, tracker)
        for node_id, adapter in enumerate(network.adapters)
    ]
    for router, adapter in zip(routers, network.adapters):
        adapter.register_handler(router.handler())
    return RoutingCandidate(
        routers=routers,
        measurement_reader=measurement_reader,
        network=network,
        rnd=rnd,
        link_fail_rate=config["link_fail_rate"],
        cost_generator=cost_generator,
    )


def _init_telemetry(node_id) -> tuple[logging.Logger, instrumentation.Tracker]:
    tracker = instrumentation.Tracker(
        counters={},
    )
    logger = logging.Logger(f"node {node_id}")
    return logger, tracker


class ExtendableRouterFactory(routing.RouterFactory):
    def __init__(self, config: dict, rnd: random.Random, node_count: int):
        self.advertise_link_failures = config["advertise_link_failures"]
        self.searching_enabled = config["searching"]
        self.auto_forward_propagations = config["auto_forward_propagations"]
        self.random_walk_broadcasting = (
            config["random_walk_broadcasting"]
            if self.auto_forward_propagations
            else False
        )
        self.route_propagation: bool = config["route_propagation"]
        self.self_propagation: bool = config["self_propagation"]
        self.broadcast_forwarding_rate: float = config["broadcast_forwarding_rate"]
        self.node_count = node_count
        self.config = config
        self.store_factory = route_storage.Factory(config["store"] if "store" in config else {})
        self.rnd = rnd
        self.store_factory = route_storage.Factory(config=config["store"] if "store" in config else {})

    def create_router(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            tracker: instrumentation.Tracker,
    ) -> routing.Router:
        stack_engine = stacking.StackEngine(
            adapter=adapter,
            rnd=self.rnd,
            broadcasting_forwarding_rate=self.broadcast_forwarding_rate,
            random_walk_broadcasting=self.random_walk_broadcasting
        )
        demand_map = self.generate_demand_map()
        propagator = propagation.create_propagator(self.config["propagation"], self.rnd)
        logger, tracker = _init_telemetry(node_id)
        store = self.store_factory.create_store(logger, node_id, tracker)
        scheduled_tasks = []
        port_disconnected_tasks = []
        message_handlers = {
            RouteAdvertisement: AdvertisementHandler(
                auto_forward_propagations=self.auto_forward_propagations,
                store=store,
                stack_engine=stack_engine,
            ),
        }
        if self.route_propagation:
            scheduled_tasks.append(
                RouteAdvertiser(
                    propagator=propagator,
                    store=store,
                    stack_engine=stack_engine,
                ),
            )
        if self.self_propagation:
            scheduled_tasks.append(
                SelfAdvertiser(
                    stack_engine=stack_engine,
                    address=node_id,
                ),
            )
        if self.searching_enabled:
            searcher = Searcher(store, stack_engine, self.rnd, demand_map)
            message_handlers[RouteSearchMessage] = searcher
            scheduled_tasks.append(searcher)
        if self.advertise_link_failures:
            message_handlers[LinkFailureAdvertisement] = LinkFailureAdvertisementHandler(stack_engine, store)
            port_disconnected_tasks.append(LinkFailureAdvertiser(stack_engine))
        router = ExtendableRouter(
            stack_engine=stack_engine,
            scheduled_tasks=scheduled_tasks,
            demand_map=demand_map,
            auto_forward_propagations=self.auto_forward_propagations,
            store=store,
            message_handlers=message_handlers,
            port_disconnected_tasks=port_disconnected_tasks,
        )
        stack_engine.endpoint = router
        return router

    def generate_demand_map(self) -> dict[NodeId, float]:
        return {
            node_id: self.rnd.random()
            for node_id in range(self.node_count)
        }
