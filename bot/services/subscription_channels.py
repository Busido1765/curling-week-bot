from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Sequence

from bot.config import RequiredChannel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionChannelsPresentation:
    message_text: str
    links: list[tuple[str, str]]

    @property
    def has_links(self) -> bool:
        return bool(self.links)


@dataclass(frozen=True)
class NormalizedRequiredChannel:
    id: int
    title: str
    url: str
    has_valid_url: bool


def normalize_required_channels(
    required_channels: Sequence[RequiredChannel],
) -> list[NormalizedRequiredChannel]:
    normalized: list[NormalizedRequiredChannel] = []
    seen_ids: set[int] = set()
    for index, channel in enumerate(required_channels, start=1):
        channel_id = channel.id
        if channel_id in seen_ids:
            logger.warning("Duplicate required channel id skipped: %s", channel_id)
            continue
        seen_ids.add(channel_id)

        title = channel.title.strip() if channel.title else ""
        if not title:
            title = f"Канал {index}"

        url = channel.url.strip() if channel.url else ""
        has_valid_url = url.startswith("https://") or url.startswith("http://")
        if not has_valid_url:
            url = ""
            title = "Нет ссылки"

        normalized.append(
            NormalizedRequiredChannel(
                id=channel_id,
                title=title,
                url=url,
                has_valid_url=has_valid_url,
            )
        )
    return normalized


def build_subscription_channels_presentation(
    required_channels: Sequence[RequiredChannel],
) -> SubscriptionChannelsPresentation:
    base_text = "Подпишись на обязательные каналы:"
    normalized = normalize_required_channels(required_channels)
    if not normalized:
        return SubscriptionChannelsPresentation(message_text=base_text, links=[])

    no_link_lines = [
        f"• {channel.title} ({channel.id})"
        for channel in normalized
        if not channel.has_valid_url
    ]
    message_text = base_text
    if no_link_lines:
        message_text = "\n".join([base_text, "", *no_link_lines])

    link_buttons = [
        (channel.title, channel.url)
        for channel in normalized
        if channel.has_valid_url
    ]
    return SubscriptionChannelsPresentation(
        message_text=message_text,
        links=link_buttons,
    )


def get_required_channel_ids_for_check(
    required_channels: Sequence[RequiredChannel],
) -> list[int]:
    normalized = normalize_required_channels(required_channels)
    return [channel.id for channel in normalized if channel.has_valid_url]
