"""Pydantic request and response schemas for the AI assistant chat."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Long enough for a detailed question, short enough to keep one exchange inside
# a free-tier quota. Enforced here so an oversized body is rejected before any
# request is made to the assistant provider.
MAX_MESSAGE_LENGTH = 2000


class ChatRequest(BaseModel):
    """A single question submitted to the SmartCycle AI assistant."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message", mode="after")
    @classmethod
    def message_is_not_blank(cls, value: str) -> str:
        """Reject a message that is only whitespace.

        `min_length` runs against the raw input, so a body of `"   "` would
        otherwise pass the field constraint and reach the provider as an empty
        question.
        """
        if not value.strip():
            raise ValueError("Please enter a message.")
        return value


class ChatResponse(BaseModel):
    """The assistant's reply.

    `response` always carries text the user can display. When the assistant is
    unavailable the service substitutes a fixed, safe apology instead of
    raising, so this shape is identical for a success and for a handled
    failure.
    """

    model_config = ConfigDict(extra="forbid")

    response: str
