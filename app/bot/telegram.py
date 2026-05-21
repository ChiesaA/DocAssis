from pathlib import Path

import httpx

from app.config import get_settings


settings = get_settings()
BASE_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def send_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


async def get_file_path(file_id: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        response.raise_for_status()
        data = response.json()
    return data["result"]["file_path"]


async def download_file(file_id: str, destination: str) -> None:
    file_path = await get_file_path(file_id)
    url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
    Path(destination).write_bytes(response.content)
