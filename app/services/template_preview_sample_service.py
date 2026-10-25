"""Small built-in preview media. No user media, files or database writes."""

from functools import lru_cache
from io import BytesIO
import math
import struct
import wave


_IMAGE = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 200">
<rect width="360" height="200" rx="16" fill="#fff4e8"/>
<circle cx="270" cy="52" r="23" fill="#ffb76b"/>
<path d="M0 175L100 55L200 175Z" fill="#e27d50"/>
<path d="M120 200L240 84L360 200Z" fill="#f3a36d"/>
<path d="M0 177Q90 140 180 177T360 177V200H0Z" fill="#578e83"/>
</svg>'''
_DIAGRAM = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 180">
<rect width="360" height="180" rx="16" fill="#fff4e8"/>
<path d="M105 90H141M219 90H255" stroke="#ac6448" stroke-width="3"/>
<path d="M133 82L141 90L133 98M247 82L255 90L247 98" fill="none" stroke="#ac6448" stroke-width="3"/>
<rect x="20" y="55" width="85" height="70" rx="12" fill="#ffb76b"/>
<rect x="141" y="55" width="78" height="70" rx="12" fill="#e27d50"/>
<rect x="255" y="55" width="85" height="70" rx="12" fill="#578e83"/>
<g font-family="sans-serif" font-size="24" text-anchor="middle" fill="#38221b">
<text x="62" y="99">1</text><text x="180" y="99">2</text><text x="297" y="99">3</text></g>
</svg>'''


def preview_sample_media(asset_id: str) -> tuple[bytes, str, str] | None:
    """Resolve only the three reserved preview IDs; ordinary assets fall through."""
    if asset_id == "sample-image":
        return _IMAGE, "image/svg+xml", "sample-image.svg"
    if asset_id == "sample-diagram":
        return _DIAGRAM, "image/svg+xml", "sample-diagram.svg"
    if asset_id != "sample-audio":
        return None
    return _sample_audio(), "audio/wav", "sample-audio.wav"


@lru_cache(maxsize=1)
def _sample_audio() -> bytes:
    rate, frames = 8000, 4000
    data = b"".join(
        struct.pack("<h", int(3500 * min(1, index / 160, (frames - index) / 160)
                             * math.sin(2 * math.pi * 440 * index / rate)))
        for index in range(frames)
    )
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(data)
    return output.getvalue()
