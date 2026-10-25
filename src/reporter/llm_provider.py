import os
import requests

class NightshiftLLMProvider:
    def __init__(self):
        self.base_url = os.getenv("METERLESS_BASE_URL", "http://localhost:8080/v1")
        self.api_key = os.getenv("METERLESS_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

    def summarize(self, evaluation_result: dict) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "meterless-app": "handoff-guardian",
            "meterless-scope": "user"
        }
        prompt = f"Summarize this handoff evaluation result: Decision: {evaluation_result.get('decision')}, Risk Score: {evaluation_result.get('risk_score')}, Conflicts: {evaluation_result.get('conflicts')}."
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return "LLM summary generation failed; falling back to standard metrics."