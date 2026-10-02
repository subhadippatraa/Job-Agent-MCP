from types import SimpleNamespace

import pytest

from job_search_agent.tools import telegram


@pytest.mark.parametrize(("decision", "approved"), [("yes", True), ("no", False)])
async def test_button_response_deletes_exact_batch_messages(monkeypatch, decision, approved):
    clients = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class Client:
        def __init__(self, **kwargs):
            self.sent_ids = []
            self.deleted_ids = []
            self.approval_message_id = None
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            if url.endswith("/sendMessage"):
                message_id = len(self.sent_ids) + 7
                self.sent_ids.append(message_id)
                if json.get("reply_markup"):
                    self.approval_message_id = message_id
                    self.nonce = json["reply_markup"]["inline_keyboard"][0][0][
                        "callback_data"
                    ].split(":")[1]
                return Response({"ok": True, "result": {"message_id": message_id}})
            if url.endswith("/deleteMessage"):
                self.deleted_ids.append(json["message_id"])
            return Response({"ok": True})

        async def get(self, url, params, timeout):
            return Response(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1,
                            "callback_query": {
                                "id": "cb1",
                                "data": f"{decision}:{self.nonce}",
                                "message": {
                                    "message_id": self.approval_message_id,
                                    "chat": {"id": 123},
                                },
                            },
                        }
                    ],
                }
            )

    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="hidden", telegram_chat_id="123"),
    )
    monkeypatch.setattr(telegram.httpx, "AsyncClient", Client)

    result = await telegram.request_submission_approval(
        [
            {
                "company": f"Example {i}",
                "role": "AI Engineer",
                "application_url": f"https://example.com/apply/{i}",
                "details": "Python, RAG, agent workflows",
            }
            for i in range(100)
        ]
    )
    assert result == {"approved": approved, "application_count": 100, "messages_deleted": True}
    assert len(clients[0].sent_ids) >= 3
    assert clients[0].deleted_ids == clients[0].sent_ids
