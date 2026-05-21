from openai import OpenAI

from app.config import get_settings


settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]


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
