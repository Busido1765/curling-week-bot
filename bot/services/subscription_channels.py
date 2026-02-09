from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SubscriptionChannelsPresentation:
    message_text: str
    links: list[str]

    @property
    def has_links(self) -> bool:
        return bool(self.links)


def build_subscription_channels_presentation(
    required_channel_ids: Sequence[int],
    required_channel_links: Sequence[str],
) -> SubscriptionChannelsPresentation:
    base_text = "Подпишись на обязательные каналы:"
    if required_channel_links and len(required_channel_links) == len(required_channel_ids):
        return SubscriptionChannelsPresentation(
            message_text=base_text,
            links=[str(link) for link in required_channel_links],
        )

    if not required_channel_ids:
        return SubscriptionChannelsPresentation(message_text=base_text, links=[])

    channel_lines = [f"Канал: {channel_id}" for channel_id in required_channel_ids]
    message_text = "\n".join([base_text, "", *channel_lines])
    return SubscriptionChannelsPresentation(message_text=message_text, links=[])
