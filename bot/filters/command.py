from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Optional, Union

from aiogram.filters.command import Command as AiogramCommand
from aiogram.filters.command import CommandObject


class Command(AiogramCommand):
    def __init__(
        self,
        *values,
        commands: Optional[Union[Sequence, str]] = None,
        **kwargs,
    ) -> None:
        self._match_any = False
        if not values and (commands is None or (isinstance(commands, Iterable) and not commands)):
            self._match_any = True
            commands = ["__any__"]
        super().__init__(*values, commands=commands, **kwargs)

    def validate_command(self, command: CommandObject) -> CommandObject:
        if self._match_any:
            return command
        return super().validate_command(command)
