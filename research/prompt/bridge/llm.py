import json
import httpx
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class LLMClient:
    async def call(self, prompt: str) -> tuple[dict, int, int]:
        raise NotImplementedError

class GeminiClient(LLMClient):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

    async def call(self, prompt: str) -> tuple[dict, int, int]:
        if not self.api_key:
            logger.error("Gemini API key is missing.")
            return {"action": "ignore", "threat_level": "none", "reason": "API key missing"}, 0, 0

        headers = {"Content-Type": "application/json", "X-goog-api-key": self.api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(self.url, headers=headers, json=payload, timeout=30.0)
                resp.raise_for_status()
                res_json = resp.json()
                
                usage = res_json.get("usageMetadata", {})
                p_tokens = usage.get("promptTokenCount", 0)
                c_tokens = usage.get("candidatesTokenCount", 0)
                
                candidates = res_json.get("candidates", [])
                if not candidates: raise ValueError("No candidates")
                raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
                return self._parse_json(raw_text), p_tokens, c_tokens
            except Exception as e:
                logger.error(f"Gemini error: {e}")
                return {"action": "ignore", "threat_level": "none", "reason": str(e)}, 0, 0

    def _parse_json(self, text: str) -> dict:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"action": "ignore", "threat_level": "none", "reason": "json parse error"}

class OllamaClient(LLMClient):
    def __init__(self, model: str = "qwen2.5:0.5b", base_url: str = "http://ollama:11434"):
        self.model = model
        self.url = f"{base_url}/api/generate"

    async def call(self, prompt: str) -> tuple[dict, int, int]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(self.url, json=payload, timeout=60.0)
                resp.raise_for_status()
                res_json = resp.json()
                
                raw_text = res_json.get("response", "")
                # Ollama doesn't always provide token counts in the same way, 
                # but it often provides prompt_eval_count and eval_count.
                p_tokens = res_json.get("prompt_eval_count", 0)
                c_tokens = res_json.get("eval_count", 0)
                
                try:
                    result = json.loads(raw_text)
                except json.JSONDecodeError:
                    # Fallback to brace extraction if needed
                    result = GeminiClient()._parse_json(raw_text)
                
                return result, p_tokens, c_tokens
            except Exception as e:
                logger.error(f"Ollama error: {e}")
                return {"action": "ignore", "threat_level": "none", "reason": str(e)}, 0, 0

def get_llm_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "ollama":
        return OllamaClient(
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        )
    return GeminiClient()
