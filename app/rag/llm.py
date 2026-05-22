import httpx
from openai import OpenAI

from app.config import Settings, get_settings


settings = get_settings()
client = None


def build_openai_client(settings: Settings) -> OpenAI:
    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


client = build_openai_client(settings)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if uses_gemini_api(settings):
        return embed_texts_with_gemini_api(texts, settings)
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]


def uses_gemini_api(settings: Settings) -> bool:
    return bool(settings.openai_base_url and "generativelanguage.googleapis.com" in settings.openai_base_url)


def normalize_gemini_model_name(model: str) -> str:
    if model.startswith("gemini/"):
        return model.split("/", 1)[1]
    return model


def build_gemini_batch_embeddings_request(texts: list[str], model: str) -> tuple[str, dict]:
    model_name = normalize_gemini_model_name(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:batchEmbedContents"
    body = {
        "requests": [
            {
                "model": f"models/{model_name}",
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }
    return url, body


def embed_texts_with_gemini_api(texts: list[str], settings: Settings) -> list[list[float]]:
    url, body = build_gemini_batch_embeddings_request(texts, settings.openai_embedding_model)
    response = httpx.post(
        url,
        headers={"x-goog-api-key": settings.openai_api_key, "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return [item["values"] for item in data.get("embeddings", [])]


def generate_answer(question: str, contexts: list[dict]) -> str:
    context_text = "\n\n".join(
        f"Source: {item['file_name']}"
        f"{', page ' + str(item['page_number']) if item.get('page_number') else ''}\n"
        f"{item['text']}"
        for item in contexts
    )
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an internal assistant. Answer only from the provided context. "
                    "If the context is insufficient, say: Chưa tìm thấy thông tin phù hợp."
                ),
            },
            {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}"},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or "Chưa tìm thấy thông tin phù hợp."
