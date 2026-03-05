"""Pydantic schemas for user authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Registration request."""

    email: EmailStr
    display_name: str = Field(
        ..., min_length=2, max_length=100, description="Public display name"
    )
    password: str = Field(
        ..., min_length=8, max_length=128, description="Password (min 8 chars)"
    )


class UserLogin(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class CredentialInfo(BaseModel):
    """A verified credential attached to a user profile."""

    id: int
    credential_type: str
    description: str
    is_verified: bool = False
    verified_at: datetime | None = None


class UserProfile(BaseModel):
    """Public user profile (returned after login or from /me)."""

    id: int
    email: str
    display_name: str
    avatar_url: str | None = None
    created_at: datetime
    submission_count: int = 0
    reputation_score: int = 0
    reputation_tier: str = "newcomer"
    credentials: list[CredentialInfo] = Field(default_factory=list)


class TokenResponse(BaseModel):
    """JWT token pair."""

    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class SpeciesCount(BaseModel):
    """Species breakdown item."""

    species: str
    count: int


class PublicProfile(BaseModel):
    """Public-facing user profile (no email)."""

    id: int
    display_name: str
    avatar_url: str | None = None
    created_at: datetime
    submission_count: int = 0
    verified_count: int = 0
    reputation_score: int = 0
    reputation_tier: str = "newcomer"
    credentials: list[CredentialInfo] = Field(default_factory=list)
    species_breakdown: list[SpeciesCount] = Field(default_factory=list)
