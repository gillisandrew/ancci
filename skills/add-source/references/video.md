# Videos

yt-dlp is asked for metadata only; no video is ever downloaded. It returns the caption
tracks plus the title, duration and chapters, and the caption track is fetched directly.

## Timestamps are the point

Cues are merged into roughly sixty-second windows, each beginning with a literal marker:

```
[t=372] and the reason the cache misses here is that the prefix changed ...
```

When a fact comes from a particular moment, cite that moment:

```yaml
sources:
  - type: video
    url: https://www.youtube.com/watch?v=...
    t: 372
```

Copy the nearest preceding `[t=]` marker rather than working out a time yourself. Pointing
a second or two early is fine and better than late — the viewer lands just before the
sentence that matters.

## Auto-generated captions mangle exactly what you want to test

The script reports whether captions were human-written or auto-generated. Auto-generated
tracks are reliable for ordinary prose and **unreliable for precisely the technical terms
a card would test** — identifiers, parameter names, library names, numbers.

When the track is auto-generated:

- Treat any unusual term as suspect. "Prompt caching" survives; a parameter name probably
  did not.
- Do not put a spelling on a card that you only have from an auto-caption. Confirm it
  against documentation, or write the card around the concept instead of the identifier.
- Say in the research note that the captions were auto-generated, so whoever authors from
  it knows the terms need checking.

## What fails

Videos with no captions at all, and some age-gated or members-only videos. The error says
which. There is no transcription fallback — say so rather than guessing at content.
