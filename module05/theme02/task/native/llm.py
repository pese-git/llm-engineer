from openai import OpenAI

class OpenAILLM:
    def __init__(self, model: str, api_key: str, base_url: str = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.model = model
        self.client = OpenAI(**kwargs)

    def complete(self, prompt: str, **kwargs) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 300),
        )
        return resp.choices[0].message.content.strip()
