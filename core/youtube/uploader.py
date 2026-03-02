from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    privacy_status: str,
    client_secret_path: str,
    token_path: str,
) -> Dict[str, Any]:
    """Upload to YouTube using OAuth (Installed App).

    Requires:
      pip install -r requirements_youtube.txt

    Notes:
    - This function will open a browser the first time (or show a device-code flow) depending on auth library.
    - After token saved, subsequent uploads are automatic.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception as e:
        raise RuntimeError(
            "Dependências do YouTube não instaladas. Rode: pip install -r requirements_youtube.txt.\n"
            f"Erro: {e}"
        )

    video_path = str(Path(video_path))
    if not Path(video_path).is_file():
        raise FileNotFoundError(video_path)

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    client_secret_path = str(Path(client_secret_path))
    token_path = str(Path(token_path))
    Path(token_path).parent.mkdir(parents=True, exist_ok=True)

    creds: Optional[Credentials] = None  # type: ignore[name-defined]
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, scopes)  # type: ignore[attr-defined]
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # type: ignore[arg-type]
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes)  # type: ignore[attr-defined]
            creds = flow.run_local_server(port=0)  # type: ignore[assignment]
        Path(token_path).write_text(creds.to_json(), encoding="utf-8")  # type: ignore[union-attr]

    youtube = build("youtube", "v3", credentials=creds)  # type: ignore[arg-type]

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:25],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        # status may be None at start
    return {"id": resp.get("id"), "status": resp.get("status"), "snippet": resp.get("snippet")}
