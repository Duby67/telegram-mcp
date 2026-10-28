"""Telegram code-delivery chats are never readable.

Service notifications (777000) deliver login codes; Verification Codes (489000)
delivers third-party verification codes.
"""

from datetime import timedelta

import pytest

from telegram_mcp.adapters.config import Settings
from telegram_mcp.bootstrap import build_service
from telegram_mcp.domain.models import Chat, Folder, ToolError
from tests.support.fakes import BASE, FakeBackend, msg
from tests.support.incremental import incremental_fixture

FROM, TO = BASE, BASE + timedelta(days=7)


@pytest.fixture(params=["777000", "489000"], ids=["service-notifications", "verification-codes"])
def code_chat(request) -> str:
    return request.param


def backend_with_service_chat(code_chat: str) -> FakeBackend:
    chats = [
        Chat(id="1", title="Jobs", type="group"),
        Chat(id=code_chat, title="Telegram", type="private"),
    ]
    messages = [msg("1", 1), msg(code_chat, 2)]
    for message, chat in zip(messages, chats, strict=True):
        message.chat = chat
    folder = Folder(id=7, title="All", position=0, included_chat_ids=["1", code_chat])
    return FakeBackend(messages, chats=chats, folders=[folder])


async def test_service_chats_are_never_readable(code_chat: str) -> None:
    backend = FakeBackend([msg("1", 1), msg(code_chat, 2)])
    service = build_service(backend, Settings(allow_all_chats=True))
    listed = await service.list_chats()
    assert [chat.id for chat in listed.chats] == ["1"]
    page = await service.search_messages(query="budget")
    assert [m.chat.id for m in page.messages] == ["1"]
    history = await service.search_messages(query="budget", chat_ids=["1"])
    assert [m.chat.id for m in history.messages] == ["1"]
    result = await service.get_messages([f"{code_chat}:2"])
    assert not result.messages and result.issues[0].code == "ACCESS_DENIED"
    with pytest.raises(ToolError, match="ACCESS_DENIED"):
        await service.get_chat(code_chat)
    with pytest.raises(ToolError, match="ACCESS_DENIED"):
        await service.search_messages(query="budget", chat_ids=[code_chat])
    assert f"{code_chat}:2" not in backend.reads
    await service.close()


@pytest.mark.parametrize(
    "settings",
    [Settings(allow_all_chats=True), Settings(allowed_folder_ids=[7])],
    ids=["all-chats", "folder"],
)
async def test_history_selectors_exclude_or_deny_the_service_chat(settings, code_chat: str) -> None:
    backend = backend_with_service_chat(code_chat)
    service = build_service(backend, settings)
    folder = await service.get_history(folder_ids=[7], date_from=FROM, date_to=TO)
    assert folder.scope.chat_ids == ["1"]
    assert {m.chat.id for m in folder.messages} == {"1"}
    with pytest.raises(ToolError, match="ACCESS_DENIED"):
        await service.get_history(chat_id=code_chat)
    with pytest.raises(ToolError, match="ACCESS_DENIED"):
        await service.get_history(chat_ids=[code_chat], date_from=FROM, date_to=TO)
    assert code_chat not in backend.fetches
    await service.close()


async def test_monitoring_and_exports_deny_the_service_chat(tmp_path, code_chat: str) -> None:
    settings = Settings(allow_all_chats=True, allow_attachment_downloads=True)
    async with incremental_fixture(
        tmp_path, backend=backend_with_service_chat(code_chat), settings=settings
    ) as env:
        for call in (
            lambda: env.service.create_watch("codes", chat_refs=[code_chat]),
            lambda: env.service.get_changes(chat_ref=code_chat),
            lambda: env.service.export_history(chat_ref=code_chat),
            lambda: env.service.download_attachment(f"{code_chat}:2:document"),
        ):
            with pytest.raises(ToolError, match="ACCESS_DENIED"):
                await call()
        info = await env.service.create_watch("all", folder_ids=[7])
        assert info.source_count == 1
