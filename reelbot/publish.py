"""Publishers. Instagram uses Meta's official Content Publishing API (resumable upload)."""
import os
import time

import requests


def _check(resp: requests.Response):
    if not resp.ok:
        raise RuntimeError(f"{resp.request.method} {resp.url.split('?')[0]} -> {resp.status_code}: {resp.text[:500]}")
    return resp


def instagram(video_path: str, caption: str) -> dict:
    version = os.getenv("IG_API_VERSION", "v26.0")
    user_id, token = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    base = f"https://graph.facebook.com/{version}"

    # 1) create a resumable Reels container
    r = _check(requests.post(f"{base}/{user_id}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "access_token": token,
    }))
    container = r.json()
    cid = container["id"]
    upload_uri = container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{version}/{cid}"

    # 2) upload the file bytes
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        _check(requests.post(upload_uri, timeout=600, data=f, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
        }))

    # 3) wait until Instagram finishes processing (Meta suggests polling for up to ~5 minutes)
    for _ in range(20):
        s = _check(requests.get(f"{base}/{cid}", timeout=30, params={
            "fields": "status_code,status", "access_token": token})).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {s}")
        time.sleep(15)
    else:
        raise TimeoutError("Instagram did not finish processing the video in time")

    # 4) publish
    media = _check(requests.post(f"{base}/{user_id}/media_publish", timeout=60, data={
        "creation_id": cid, "access_token": token})).json()
    media_id = media["id"]
    link = requests.get(f"{base}/{media_id}", timeout=30,
                        params={"fields": "permalink", "access_token": token}).json().get("permalink")
    return {"id": media_id, "url": link}


def youtube(video_path: str, title: str, description: str, privacy: str) -> dict:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title[:100], "description": description[:4900], "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    request = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk()
    return {"id": response["id"], "url": f"https://youtube.com/shorts/{response['id']}", "privacy": privacy}
