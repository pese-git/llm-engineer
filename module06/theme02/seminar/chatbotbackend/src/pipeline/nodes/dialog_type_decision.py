from src.clients.llm import get_chat_completion
from src.pipeline.abc_base_node import BaseDescisionEnum, BaseDescisionNode
from src.pipeline.context import Context


class DiloagTypeDescision(BaseDescisionEnum):
    CHIT_CHAT = "CHIT_CHAT"
    RAG = "RAG"


class DialogDescision(BaseDescisionNode[DiloagTypeDescision]):
    available_decisions = DiloagTypeDescision
    name = "DialogType"

    async def _execute(self, context: Context) -> Context:
        prompt = (
            "Based on the dialog decide if user want to chat or want to find information about AI talent hub or AI news. "
            "If user want to chat respond with CHIT_CHAT else respond with RAG."
        )
        response = await get_chat_completion(
            user_query=context.query,
            system_message=prompt,
            history=context.history,
            settings=context.settings,
            params={
                "extra_body": {
                    "structured_outputs": {
                        "choice": [
                            transition.value for transition in DiloagTypeDescision
                        ]
                    }
                }
            },
        )

        context.decision = DiloagTypeDescision(response.strip())
        return context
