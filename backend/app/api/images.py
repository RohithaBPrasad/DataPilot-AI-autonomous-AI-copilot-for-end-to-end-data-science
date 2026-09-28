from __future__ import annotations

from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter()
USER_AGENT = "EvolveDataScienceAgent/1.0"


@router.get("/images/generate")
def generate_image(
    prompt: str = Query(..., min_length=1, max_length=2000),
    seed: int | None = None,
):
    safe_seed = seed % 2_147_483_647 if seed is not None else None
    image_url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt, safe='')}"
        f"?width=1024&height=1024&nologo=true{f'&seed={safe_seed}' if safe_seed is not None else ''}"
    )
    request = Request(image_url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    try:
        with urlopen(request, timeout=180) as upstream:
            image_data = upstream.read()
            media_type = upstream.headers.get_content_type() or "image/jpeg"
    except Exception as error:
        raise HTTPException(status_code=502, detail="The image service could not generate this image yet.") from error

    return Response(content=image_data, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})
