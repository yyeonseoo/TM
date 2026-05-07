from __future__ import annotations

import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Response


router = APIRouter(tags=["assets"])


ALLOWED_IMAGE_HOSTS = {
    "upload.wikimedia.org",
    "ko.wikipedia.org",
    "wikipedia.org",
}


@router.get("/image-proxy")
def image_proxy(url: str):
    """
    Proxy remote images to avoid browser CORS issues.

    Security:
    - only allows https
    - host allowlist (Wikipedia thumbnail domains)
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid url")

    if parsed.scheme not in ("https",):
        raise HTTPException(status_code=400, detail="only https allowed")

    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=403, detail="host not allowed")

    try:
        r = requests.get(url, timeout=6, headers={"User-Agent": "TM-image-proxy/1.0"})
        r.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="failed to fetch image")

    content_type = r.headers.get("Content-Type", "image/jpeg")
    # SVG <image> loads can be picky with cross-origin resources.
    # We always add permissive CORS/CORP headers for this proxied image response.
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Cross-Origin-Resource-Policy": "cross-origin",
        "Cache-Control": "public, max-age=86400",
    }
    return Response(content=r.content, media_type=content_type, headers=headers)

