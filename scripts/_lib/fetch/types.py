"""What every acquirer returns.

Text to read, and the citation that text came from. The citation is a schema `Source`, so
whatever a card ends up citing is exactly what was fetched — never reconstructed later from
memory of where something was read.
"""

from dataclasses import dataclass, field

from ..sources import Source


class FetchError(Exception):
    """Raised when material cannot be acquired. The message is shown to the user as-is."""


@dataclass
class Fetched:
    text: str
    citation: Source
    # What to call this in a research note, and on disk in the cache.
    title: str
    # Anything worth recording that is not part of the citation: caption language, page
    # count, the commit's date, whether a transcript was auto-generated.
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        """A filename-safe stem for the cache and the research note."""
        keep = [c.lower() if c.isalnum() else "-" for c in self.title.strip()]
        slug = "".join(keep)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")[:60] or "source"
