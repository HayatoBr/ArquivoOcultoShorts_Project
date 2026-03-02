
import requests

class OllamaLLM:
    def __init__(self, base_url="http://127.0.0.1:11434", model="llama3.2:latest", fallback_models=None, timeout=120):
        self.base_url = base_url
        self.model = model
        self.fallback_models = fallback_models or []
        self.timeout = timeout

    def _call_model(self, model, prompt):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()["response"]

    def generate(self, prompt):
        models_to_try = [self.model] + self.fallback_models
        last_error = None

        for m in models_to_try:
            try:
                print(f"[LLM] Tentando modelo: {m}")
                return self._call_model(m, prompt)
            except Exception as e:
                print(f"[LLM] Falha no modelo {m}: {e}")
                last_error = e

        raise RuntimeError(f"Todos os modelos Ollama falharam. Último erro: {last_error}")
