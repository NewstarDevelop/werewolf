"""Schemas for game history."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HistoryListItem(BaseModel):
    id: int
    room_id: int
    mode: str
    winner: str | None
    player_count: int
    duration_seconds: int | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class HistoryParticipant(BaseModel):
    seat: int
    nickname: str
    role: str
    faction: str
    is_ai: bool
    survived: bool

    model_config = {"from_attributes": True}


class HistoryDetail(BaseModel):
    id: int
    room_id: int
    mode: str
    winner: str | None
    player_count: int
    duration_seconds: int | None
    finished_at: datetime | None
    participants: list[HistoryParticipant]
    events: list[dict]

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    items: list[HistoryListItem]
    total: int
    page: int
    page_size: int
