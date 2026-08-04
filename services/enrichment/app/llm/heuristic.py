"""Local regex fallback when no LLM API key is configured."""

from __future__ import annotations

import re

from autopulse_shared.schemas.listing import ListingOptions, RawListing


class HeuristicOptionsExtractor:
    """Sync text heuristics for packages/features/owners (no network)."""

    _PACKAGE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("M-Sport", re.compile(r"\bm[-\s]?sport\b", re.I)),
        ("AMG", re.compile(r"\bamg\b", re.I)),
        ("S-Line", re.compile(r"\bs[-\s]?line\b", re.I)),
    ]

    _FEATURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("panorama", re.compile(r"panorama|панорама", re.I)),
        ("harman_kardon", re.compile(r"harman|харман", re.I)),
        ("heated_seats", re.compile(r"heated seats|подогрев сидений", re.I)),
        ("leather", re.compile(r"leather|кожа", re.I)),
    ]

    _OWNER_PATTERN = re.compile(
        r"(one owner|single owner|один владелец|1 владелец)",
        re.I,
    )

    def extract(self, listing: RawListing) -> ListingOptions:
        text = " ".join(
            part for part in (listing.title, listing.description) if part
        )
        packages = [
            name for name, pat in self._PACKAGE_PATTERNS if pat.search(text)
        ]
        features = [
            name for name, pat in self._FEATURE_PATTERNS if pat.search(text)
        ]
        tags: list[str] = ["heuristic"]
        owner_count = 1 if self._OWNER_PATTERN.search(text) else None
        if owner_count == 1:
            tags.append("one_owner")
        return ListingOptions(
            packages=packages,
            features=features,
            tags=tags,
            owner_count=owner_count,
            notes="heuristic extractor (no LLM_API_KEY)",
        )
