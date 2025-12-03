from openai import OpenAI

class OpenAILLM:
    def __init__(self, model: str, api_key: str, base_url: str = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.model = model
        self.client = OpenAI(**kwargs)

    def complete(self, prompt: str, **kwargs) -> str:
        resp = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0),
            max_completion_tokens=kwargs.get("max_tokens", 1024),
            response_format=kwargs.get("response_format", {"type": "text"})
        )
        return resp.choices[0].message.content.strip()
