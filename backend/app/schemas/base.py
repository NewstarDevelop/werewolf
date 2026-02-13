"""Shared Pydantic base models and serializers."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


def datetime_to_utc_z(value: datetime) -> str:
    """
    Serialize datetime to RFC3339 with trailing 'Z'.

    Policy:
    - Naive datetime is treated as UTC (matches backend usage of datetime.now(timezone.utc)).
    - Aware datetime is converted to UTC.
    """
    if value.tzinfo is None:
        utc_value = value.replace(tzinfo=timezone.utc)
    else:
        utc_value = value.astimezone(timezone.utc)

    iso_value = utc_value.isoformat()
    if iso_value.endswith("+00:00"):
        return iso_value[:-6] + "Z"
    return iso_value


class UTCZBaseModel(BaseModel):
    """Base model that serializes datetime fields as UTC with 'Z' suffix."""

    model_config = ConfigDict(
        json_encoders={datetime: datetime_to_utc_z},
    )


class UTCZFromAttributesModel(UTCZBaseModel):
    """Base model for ORM-backed schemas (from_attributes=True) with UTC 'Z' datetime serialization."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: datetime_to_utc_z},
    )
