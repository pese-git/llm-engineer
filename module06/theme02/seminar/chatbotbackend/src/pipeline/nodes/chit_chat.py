from src.clients.llm import get_chat_completion
from src.pipeline.abc_base_node import BaseNode
from src.pipeline.context import Context


class ChitChatNode(BaseNode):
    name = "ChitChatNode"

    async def _execute(self, context: Context) -> Context:
        prompt = (
            "You are a friendly and engaging AI chatbot. "
            "Your task is to have a natural and enjoyable conversation with the user. "
            "Respond to the user's messages in a way that is informative, empathetic, and contextually relevant. "
            "Make sure to keep the conversation flowing and ask questions to keep the user engaged."
        )
        response = await get_chat_completion(
            user_query=context.query,
            system_message=prompt,
            history=context.history,
            settings=context.settings,
        )
        context.output = response
        return context
