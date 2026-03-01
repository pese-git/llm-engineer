from src.pipeline.config import Graph
from src.pipeline.context import Context


class Orchestrator:
    def __init__(self, graph: Graph):
        self.graph = graph

    async def execute(self, context: Context) -> str:
        max_steps = len(self.graph.graph) * 2

        node = self.graph.start_node
        while max_steps > 0:
            max_steps -= 1
            context = await node.node.execute(context)

            if context.decision is not None:
                next_node_name = node.next_node[context.decision]
            else:
                next_node_name = node.next_node

            node = self.graph.name_to_node[next_node_name]
            context.decision = None

            if node.name == self.graph.end_node.name:
                break
        return context.output
