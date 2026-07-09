import math
import os

from fastapi import HTTPException, UploadFile


CHUNK_SIZE = 64 * 1024
MAX_AUDIO_SIZE_BYTES = int(os.getenv("MAX_AUDIO_SIZE_BYTES", str(20 * 1024 * 1024)))


def _format_size_mb(size_bytes: int) -> int:
    return max(1, math.ceil(size_bytes / (1024 * 1024)))


async def read_audio_upload_limited(
    upload: UploadFile,
    *,
    max_size_bytes: int | None = None,
) -> bytes:
    """Read an uploaded audio file in chunks and reject oversized payloads early."""
    limit = MAX_AUDIO_SIZE_BYTES if max_size_bytes is None else max_size_bytes
    chunks: list[bytes] = []
    total_size = 0

    try:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > limit:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Audio file too large. "
                        f"Maximum allowed size is {_format_size_mb(limit)}MB."
                    ),
                )

            chunks.append(chunk)

        return b"".join(chunks)
    finally:
        await upload.close()
