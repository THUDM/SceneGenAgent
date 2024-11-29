from typing import (
    Any,
    Dict,
)
from openai import OpenAI

class Model:
    @property
    def _default_params(self) -> Dict[str, Any]:
        params = {
            "model": self.model,
            # "max_tokens": self.max_tokens,
            "stream": False,
        }
        if hasattr(self, "temperature"):
            params["temperature"] = self.temperature
        return params

    def __init__(self, model_name, base_url, api_key):
        self.model: str = model_name
        self.max_tokens: int = 4096
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def post(self, request: Any) -> Any:
        retries = 5
        for _ in range(retries):
            response = self.client.chat.completions.create(**request)
            try:
                choice = response.choices[0]
                if choice.finish_reason != 'stop':
                    print(f"Finish reason: {choice.finish_reason}")
                    raise NotImplementedError
                return response
            except:
                print(f"Response content: {response}")
        raise NotImplementedError
    
    def generate(self, prompt: str, model: str=None):
        request = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }
        request.update(self._default_params)
        if model:
            request['model'] = model
        response = self.post(request)
        return response.choices[0].message.content.rstrip()

    def invoke(
        self,
        messages,
        model=None,
        **kwargs: Any,
    ) -> str:
        request = kwargs
        for i in range(len(messages)):
            messages[i] = {key: messages[i][key] for key in ['role', 'content']}
        request["messages"] = messages
        request.update(self._default_params)
        if model:
            request['model'] = model
        response = self.post(request)
        return response.choices[0].message.content.rstrip()

class LocalModel(Model):
    def __init__(self, model_name, base_url="http://localhost:8000/v1"):
        super().__init__(model_name, base_url, api_key='EMPTY')

class ChatGPT(Model):
    def __init__(self, model_name="gpt-4-0125-preview", base_url="https://api.openai.com/v1"):
        api_key=open('openai_key').read()
        super().__init__(model_name, base_url, api_key=api_key)
