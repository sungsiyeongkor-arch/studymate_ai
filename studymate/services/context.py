"""Prepare bounded domain context without treating it as a corrected transcript."""

import re


def short_utf8(value, size):
    # A conservative byte budget also bounds byte-pair tokens without downloading a tokenizer.
    return value.encode("utf-8")[:size].decode("utf-8", errors="ignore")


def whisper_context(title, topic, terms, sources):
    """Whisper accepts 224 prompt tokens. Reserve space for each context source."""
    vocabulary = ", ".join(
        t.word
        + ("/" + t.pronunciation if t.pronunciation else "")
        + (" " + ",".join(t.related[:2]) if t.related else "")
        for t in terms
    )
    passages = " ".join(s["text"] for s in sources)
    # This is a brief recognition hint, not full-document training or forced replacement.
    return ". ".join(
        [
            short_utf8(title + " " + topic, 55),
            short_utf8(vocabulary, 90),
            short_utf8(re.sub(r"\s+", " ", passages), 70),
        ]
    ).strip(". ")
