"""Prompt templates for LLM option extraction."""

from __future__ import annotations

SYSTEM_PROMPT = "Return only valid JSON for ListingOptions."

USER_PROMPT_TEMPLATE = """\
Extract car options as JSON with keys: packages, features, tags, owner_count, notes.

Listing Title: {title}
Listing Description: {description}
"""
