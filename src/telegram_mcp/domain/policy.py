"""A credential-free snapshot of the current retrieval policy."""

from dataclasses import dataclass

# Telegram's service-notification account delivers login codes, and its Verification Codes
# account delivers third-party verification codes; neither is ever readable.
SERVICE_NOTIFICATIONS_ID = "777000"
VERIFICATION_CODES_ID = "489000"
PROTECTED_CHAT_IDS = frozenset({SERVICE_NOTIFICATIONS_ID, VERIFICATION_CODES_ID})


@dataclass(frozen=True)
class ReadPolicy:
    allowed_chat_ids: tuple[str, ...] = ()
    allowed_folder_ids: tuple[int, ...] = ()
    allow_all_chats: bool = False
    allow_public_channel_reads: bool = False
    allow_public_channel_discovery: bool = False
    allow_attachment_downloads: bool = False
