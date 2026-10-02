"""Telegram yes/no gate for a specific prepared application batch."""

from __future__ import annotations

import asyncio
import secrets

import httpx

from job_search_agent.config import get_settings


async def request_submission_approval(applications: list[dict], timeout_seconds: int = 300) -> dict:
    """Send an exact application summary and wait for a chat-bound button response."""
    if not 10 <= timeout_seconds <= 1800:
        return {"error": "timeout_seconds must be between 10 and 1800"}
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {
            "error": "Telegram is not configured",
            "message": "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env, then restart the MCP server.",
        }
    if not applications:
        return {"error": "No applications supplied"}
    if len(applications) > 100:
        return {"error": "Approval batches are limited to 100 applications"}

    chat_id = str(settings.telegram_chat_id)
    nonce = secrets.token_urlsafe(12)
    entries: list[str] = []
    for i, app in enumerate(applications, 1):
        entry = (
            f"{i}. {app.get('company', 'Unknown company')} — {app.get('role', 'Unknown role')}\n"
            f"Match: {app.get('match_score', 'not provided')} | "
            f"URL: {app.get('application_url', 'not provided')}"
        )
        if app.get("details"):
            entry += f"\n{app['details']}"
        if len(entry) > 3800:
            return {"error": f"Application {i} is too long for Telegram"}
        entries.append(entry)

    messages: list[str] = []
    chunk = ""
    for entry in entries:
        next_chunk = f"{chunk}\n\n{entry}" if chunk else entry
        if len(next_chunk) > 3800:
            messages.append(chunk)
            chunk = entry
        else:
            chunk = next_chunk
    if chunk:
        messages.append(chunk)

    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Approve this batch", "callback_data": f"yes:{nonce}"},
                {"text": "Reject", "callback_data": f"no:{nonce}"},
            ]
        ]
    }
    message_ids: list[int] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for i, message in enumerate(messages, 1):
                sent = await client.post(
                    f"{base}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": f"Ranked batch ({i}/{len(messages)})\n\n{message}",
                    },
                )
                sent.raise_for_status()
                data = sent.json()
                if not data.get("ok"):
                    raise httpx.HTTPError("Telegram rejected a job-list message")
                message_ids.append(data["result"]["message_id"])

            approval = await client.post(
                f"{base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        f"Approve applying to all {len(applications)} prepared jobs? "
                        "This approval applies only to this exact batch."
                    ),
                    "reply_markup": keyboard,
                },
            )
            approval.raise_for_status()
            data = approval.json()
            if not data.get("ok"):
                raise httpx.HTTPError("Telegram rejected the approval message")
            approval_message_id = data["result"]["message_id"]
            message_ids.append(approval_message_id)
            offset: int | None = None
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                updates = await client.get(
                    f"{base}/getUpdates",
                    params={
                        "timeout": 20,
                        "allowed_updates": '["callback_query"]',
                        **({"offset": offset} if offset is not None else {}),
                    },
                    timeout=25,
                )
                updates.raise_for_status()
                result = updates.json()
                if not result.get("ok"):
                    return {"error": "Telegram approval polling failed"}
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    callback = update.get("callback_query", {})
                    source = callback.get("message", {})
                    if (
                        str(source.get("chat", {}).get("id")) != chat_id
                        or source.get("message_id") != approval_message_id
                        or callback.get("data") not in {f"yes:{nonce}", f"no:{nonce}"}
                    ):
                        continue
                    approved = callback["data"] == f"yes:{nonce}"
                    try:
                        response = await client.post(
                            f"{base}/answerCallbackQuery",
                            json={
                                "callback_query_id": callback["id"],
                                "text": "Approved" if approved else "Rejected",
                            },
                        )
                        response.raise_for_status()
                    except httpx.HTTPError:
                        pass
                    deleted = True
                    for message_id in message_ids:
                        try:
                            response = await client.post(
                                f"{base}/deleteMessage",
                                json={"chat_id": chat_id, "message_id": message_id},
                            )
                            response.raise_for_status()
                            deleted = deleted and response.json().get("ok", False)
                        except httpx.HTTPError:
                            deleted = False
                    return {
                        "approved": approved,
                        "application_count": len(applications),
                        "messages_deleted": deleted,
                    }
            return {"approved": False, "timed_out": True, "application_count": len(applications)}
    except httpx.HTTPError:
        # Avoid returning exception text: it can contain the bot-token URL.
        return {"error": "Could not reach Telegram; no approval was granted"}


async def request_candidate_input(question: str, timeout_seconds: int = 600) -> dict:
    """Ask one profile question in Telegram and return the chat-bound reply."""
    if not question.strip():
        return {"error": "Question is required"}
    if not 10 <= timeout_seconds <= 1800:
        return {"error": "timeout_seconds must be between 10 and 1800"}
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"error": "Telegram is not configured"}

    chat_id = str(settings.telegram_chat_id)
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            sent = await client.post(
                f"{base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": question,
                    "reply_markup": {"force_reply": True, "selective": True},
                },
            )
            sent.raise_for_status()
            question_id = sent.json()["result"]["message_id"]
            offset: int | None = None
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                updates = await client.get(
                    f"{base}/getUpdates",
                    params={"timeout": 20, **({"offset": offset} if offset is not None else {})},
                    timeout=25,
                )
                updates.raise_for_status()
                for update in updates.json().get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    if (
                        str(message.get("chat", {}).get("id")) != chat_id
                        or message.get("message_id", 0) <= question_id
                        or not message.get("text", "").strip()
                    ):
                        continue
                    answer = message["text"].strip()
                    deleted = True
                    for message_id in (question_id, message["message_id"]):
                        response = await client.post(
                            f"{base}/deleteMessage",
                            json={"chat_id": chat_id, "message_id": message_id},
                        )
                        deleted = (
                            deleted and response.is_success and response.json().get("ok", False)
                        )
                    return {"answer": answer, "messages_deleted": deleted}
            return {"error": "Telegram response timed out"}
    except httpx.HTTPError:
        return {"error": "Could not reach Telegram"}
