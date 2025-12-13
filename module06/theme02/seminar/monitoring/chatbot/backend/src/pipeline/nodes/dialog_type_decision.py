from src.clients.llm import get_chat_completion
from src.pipeline.base_node import BaseDecisionEnum, BaseDecisionNode
from src.pipeline.context import Context


class DiloagTypeDecision(BaseDecisionEnum):
    CHIT_CHAT = "CHIT_CHAT"
    RAG = "RAG"


class DialogDecision(BaseDecisionNode[DiloagTypeDecision]):
    available_decisions = DiloagTypeDecision
    name = "dialog_type_decision"

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
                # standard json request
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "descision",
                        "schema": self.get_decision_scheme.model_json_schema(),
                    },
                },
                # simplified version of json request. Need to change base method to client.chat.completions.parse
                # "response_format": self.get_Decision_scheme,
                # vllm guided choice
                # "extra_body": {
                #     "structured_outputs": {
                #         "choice": [
                #             transition.value for transition in DiloagTypeDecision
                #         ]
                #     }
                # },
            },
        )

        context.decision = self.parse_decision(response)
        return context
