"""Общие типы и абстракции для всех announcers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol

@dataclass(frozen=True, slots=True)
class Announcement:
    """Данные о листинге монеты."""
    exchange: str
    symbol: str
    details_url: str

    def key(self) -> str:  # уникальный идентификатор для дедупликации
        return f"{self.exchange}:{self.symbol}"

class AnnouncerProto(Protocol):
    name: str
    async def fetch(self) -> AsyncIterator[Announcement]:
        """Асинхронно генерирует анонсы."""

# Для типизации в main.py можно наследоваться от этого минимального класса
class AbstractAnnouncer:
    name: str = "abstract"
    async def fetch(self) -> AsyncIterator[Announcement]:  # pragma: no cover – заглушка
        raise NotImplementedError