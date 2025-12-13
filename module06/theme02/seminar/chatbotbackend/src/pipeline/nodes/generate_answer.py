from src.clients.llm import get_chat_completion
from src.pipeline.abc_base_node import BaseNode
from src.pipeline.context import Context


class LLMAnswer(BaseNode):
    name = "llm_answer"

    async def _execute(self, context: Context) -> Context:
        prompt = "Answer on user query based on documents"

        formatted_documents = []
        for i, document in enumerate(context.documents):
            formatted_documents.append("Документ 1 " + document)

        response = await get_chat_completion(
            user_query=context.query
            + "\n\nДокументы:\n"
            + "\n\n".join(formatted_documents),
            system_message=prompt,
            history=context.history,
            settings=context.settings,
        )
        context.output = response
        return context
