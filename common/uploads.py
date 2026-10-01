"""Image upload validation.

The browser-supplied filename and Content-Type are never trusted: the real
type is sniffed from the file's leading bytes, and the stored file is renamed
to a random name with the extension that matches. SVG/HTML therefore can't be
smuggled in as an "image".
"""
import uuid

from rest_framework import serializers


def _sniff_extension(head: bytes):
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"avif", b"avis"):
        return "avif"
    return None


def _pretty(num_bytes):
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def clean_image_upload(upload, max_bytes):
    """Validate an uploaded image and give it a safe random name."""
    if upload.size > max_bytes:
        raise serializers.ValidationError(
            f"That image is {_pretty(upload.size)}. The limit is {_pretty(max_bytes)}."
        )
    head = upload.read(16)
    upload.seek(0)
    ext = _sniff_extension(head)
    if ext is None:
        raise serializers.ValidationError(
            "Unsupported image type. Use JPG, PNG, WEBP, GIF or AVIF."
        )
    upload.name = f"{uuid.uuid4().hex}.{ext}"
    return upload
