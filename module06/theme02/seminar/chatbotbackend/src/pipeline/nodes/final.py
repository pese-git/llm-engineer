from src.pipeline.abc_base_node import BaseNode
from src.pipeline.context import Context


class FinalNode(BaseNode):
    async def _execute(self, context: Context) -> Context:
        return context
