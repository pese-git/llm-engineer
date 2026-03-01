import dataclasses

from src.pipeline.abc_base_node import BaseDescisionEnum, BaseDescisionNode, BaseNode
from src.pipeline.nodes.chit_chat import ChitChatNode
from src.pipeline.nodes.dialog_type_decision import DialogDescision, DiloagTypeDescision
from src.pipeline.nodes.final import FinalNode
from src.pipeline.nodes.generate_answer import LLMAnswer
from src.pipeline.nodes.get_context import RetrieveNode


@dataclasses.dataclass
class Node:
    name: str
    node: BaseNode | BaseDescisionNode
    next_node: str | dict[BaseDescisionEnum, str] | None


class Graph:
    def __init__(self, nodes: list[Node], start_node_name: str, end_node_name: str):
        self.graph = nodes
        self.name_to_node: dict[str, Node] = {node.name: node for node in nodes}
        if (
            start_node_name not in self.name_to_node
            or end_node_name not in self.name_to_node
        ):
            raise ValueError(
                f"Node {start_node_name} or {end_node_name} does not exist"
            )

        self.start_node = self.name_to_node[start_node_name]
        self.end_node = self.name_to_node[end_node_name]


CHAT_BOT = Graph(
    [
        Node(
            name="chat_type",
            node=DialogDescision(),
            next_node={
                DiloagTypeDescision.RAG: "retrieval",
                DiloagTypeDescision.CHIT_CHAT: "chit_chat",
            },
        ),
        Node(
            name="chit_chat",
            node=ChitChatNode(),
            next_node="final",
        ),
        Node(
            name="retrieval",
            node=RetrieveNode(),
            next_node="answer",
        ),
        Node(
            name="answer",
            node=LLMAnswer(),
            next_node="final",
        ),
        Node(
            name="final",
            node=FinalNode(),
            next_node=None,
        ),
    ],
    start_node_name="chat_type",
    end_node_name="final",
)
