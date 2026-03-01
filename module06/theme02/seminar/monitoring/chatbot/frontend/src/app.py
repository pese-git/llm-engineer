import uuid

import gradio as gr
import requests

from src.schemes import ApiResponse
from src.settings import Settings

settings = Settings()


def add_message(history: list[gr.MessageDict], message: str) -> tuple[list[gr.MessageDict], gr.Textbox]:
    history.append(gr.MessageDict(role="user", content=message))
    return history, gr.Textbox(value=None, interactive=True)


def bot(history: list[gr.MessageDict], session_id: str) -> list[gr.MessageDict]:
    user_message = history[-1]["content"]
    if isinstance(user_message, list):
        full_message = []
        for msg in user_message:
            if msg["type"] == "text":
                full_message.append(msg["text"])
        user_message = " ".join(full_message)
    cur_history = history[:-1]
    response = requests.post(
        settings.backend_url + "/chat",
        json={
            "query": user_message,
            "history": cur_history,
            "session_id": session_id,
        },
    )
    if response.status_code != 200:
        raise gr.Error(response.text)
    response_model = ApiResponse.model_validate_json(response.text)
    history.append(gr.MessageDict(role="assistant", content=response_model.content))
    return history


def main() -> gr.Blocks:
    with gr.Blocks(title="Chatbot") as demo:
        chatbot = gr.Chatbot(
            show_label=True,
        )

        chat_input = gr.Textbox(
            interactive=True,
            placeholder="Enter message or upload file...",
            show_label=False,
        )

        session_id = gr.Textbox(str(uuid.uuid4()), visible=False)

        chat_msg = chat_input.submit(add_message, [chatbot, chat_input], [chatbot, chat_input])
        bot_msg = chat_msg.then(bot, inputs=[chatbot, session_id], outputs=chatbot)
        bot_msg.then(lambda: gr.Textbox(interactive=True), None, chat_input)

        chatbot.clear(lambda: gr.Textbox(str(uuid.uuid4()), visible=False), None, session_id)
    return demo


if __name__ == "__main__":
    blocks = main()
    blocks.launch()
