import os
import httpx


async def chat(
    model: str,
    messages: list[dict],
    api_key: str,
    referer: str | None = None,
    title: str | None = None,
) -> str:
    """
    Call OpenRouter chat API.
    
    Args:
        model: Model ID (e.g., "anthropic/claude-3.5-sonnet")
        messages: List of dicts with "role" and "content"
        api_key: OpenRouter API key
        referer: Optional HTTP-Referer header
        title: Optional X-Title header
    
    Returns:
        Assistant message text (choices[0].message.content)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    payload = {
        "model": model,
        "messages": messages,
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
