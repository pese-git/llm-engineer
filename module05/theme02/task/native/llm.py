from openai import OpenAI
import json

class OpenAILLM:
    def __init__(self, model: str, api_key: str, base_url: str = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.model = model
        self.client = OpenAI(**kwargs)


    
    def complete(self, messages, schema=None, **kwargs):
        # messages должен быть списком сообщений (чат-формат)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format=kwargs.get("response_format", {"type": "json_object"}),
            max_tokens=kwargs.get("max_tokens", 1024),
            temperature=kwargs.get("temperature", 0)
        )
        out = resp.choices[0].message.content
        if schema is not None:
            try:
                data = json.loads(out)
            except Exception:
                raise RuntimeError(f"LLM did not return JSON: {out}")
            try:
                res = schema(**data)
            except Exception as e:
                raise RuntimeError(f"Rejected by {schema.__name__} schema: {data} / {e}")
            return res.dict()
        else:
            return out
