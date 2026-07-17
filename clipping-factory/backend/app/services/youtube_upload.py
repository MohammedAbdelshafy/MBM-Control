"""
YouTube Upload Service — upload videos to YouTube via Data API v3.

Supports multiple channels via youtube_tokens.json (created by youtube_oauth_setup.py).

Usage:
  from app.services.youtube_upload import YouTubeUploader

  uploader = YouTubeUploader()
  uploader.upload(
      video_path="/path/to/video.mp4",
      title="My Video",
      description="Description here",
      tags=["tag1", "tag2"],
      privacy="public",  # public | unlisted | private
      channel_id="optional特定channel",  # defaults to first configured channel
  )
"""
import json
import time
from pathlib import Path
from typing import Optional

TOKENS_PATH = Path(__file__).parent.parent.parent / "clipping-factory" / "backend" / "youtube_tokens.json"
if not TOKENS_PATH.exists():
    TOKENS_PATH = Path(__file__).parent.parent / "youtube_tokens.json"


class YouTubeUploader:
    def __init__(self, tokens_path: Optional[str] = None):
        self.tokens_path = Path(tokens_path) if tokens_path else TOKENS_PATH
        self._tokens = self._load_tokens()

    def _load_tokens(self) -> dict:
        if not self.tokens_path.exists():
            return {}
        return json.loads(self.tokens_path.read_text())

    def list_channels(self) -> list[dict]:
        """List all configured channels."""
        return [
            {"channel_id": cid, "channel_name": info.get("channel_name", "Unknown")}
            for cid, info in self._tokens.items()
        ]

    def _get_credentials(self, channel_id: Optional[str] = None):
        """Get google OAuth2 credentials for a channel."""
        from google.oauth2.credentials import Credentials

        if not self._tokens:
            raise RuntimeError(
                "No YouTube tokens found. Run youtube_oauth_setup.py first."
            )

        if channel_id:
            if channel_id not in self._tokens:
                raise ValueError(f"Channel {channel_id} not configured. Available: {list(self._tokens.keys())}")
            info = self._tokens[channel_id]
        else:
            # Use first channel
            cid = next(iter(self._tokens))
            info = self._tokens[cid]

        creds = Credentials(
            token=info.get("access_token"),
            refresh_token=info["refresh_token"],
            token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=info["client_id"],
            client_secret=info["client_secret"],
            scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
        )
        return creds

    def _refresh_token(self, channel_id: Optional[str] = None):
        """Force refresh the access token and save it."""
        from google.auth.transport.requests import Request

        creds = self._get_credentials(channel_id)
        creds.refresh(Request())

        # Update stored token
        cid = channel_id or next(iter(self._tokens))
        self._tokens[cid]["access_token"] = creds.token
        self.tokens_path.write_text(json.dumps(self._tokens, indent=2))
        return creds

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] = None,
        privacy: str = "public",
        category_id: str = "28",  # 28 = Science & Technology
        channel_id: Optional[str] = None,
        made_for_kids: bool = False,
    ) -> dict:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy: "public", "unlisted", or "private"
            category_id: YouTube category (28 = Science & Technology)
            channel_id: Specific channel to upload to (default: first configured)
            made_for_kids: Whether the video is made for kids

        Returns:
            dict with video_id, channel_id, status
        """
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        creds = self._get_credentials(channel_id)
        # Refresh if expired
        if creds.expired or not creds.token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            cid = channel_id or next(iter(self._tokens))
            self._tokens[cid]["access_token"] = creds.token
            self.tokens_path.write_text(json.dumps(self._tokens, indent=2))

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],  # YouTube max 100 chars
                "description": description[:5000],
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": made_for_kids,
                "embeddable": True,
                "publicStatsViewable": True,
            },
        }

        media = MediaFileUpload(
            str(video_file),
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  Upload progress: {pct}%")

        video_id = response.get("id", "")
        cid = channel_id or next(iter(self._tokens))
        print(f"  Uploaded: https://youtube.com/watch?v={video_id}")

        return {
            "video_id": video_id,
            "channel_id": cid,
            "url": f"https://youtube.com/watch?v={video_id}",
            "status": "uploaded",
        }

    def upload_short(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] = None,
        channel_id: Optional[str] = None,
    ) -> dict:
        """Upload a YouTube Short (vertical video < 60s, same API call)."""
        all_tags = (tags or []) + ["Shorts", "short"]
        return self.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=all_tags,
            privacy="public",
            category_id="28",
            channel_id=channel_id,
            made_for_kids=False,
        )


# Standalone CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--channel", default=None, help="Channel ID (default: first configured)")
    parser.add_argument("--short", action="store_true", help="Upload as YouTube Short")
    parser.add_argument("--list-channels", action="store_true", help="List configured channels")

    args = parser.parse_args()
    uploader = YouTubeUploader()

    if args.list_channels:
        channels = uploader.list_channels()
        if not channels:
            print("No channels configured. Run youtube_oauth_setup.py first.")
        else:
            for ch in channels:
                print(f"  {ch['channel_name']}: {ch['channel_id']}")
        sys.exit(0)

    if args.short:
        result = uploader.upload_short(
            video_path=args.video,
            title=args.title,
            description=args.description,
            tags=args.tags,
            channel_id=args.channel,
        )
    else:
        result = uploader.upload(
            video_path=args.video,
            title=args.title,
            description=args.description,
            tags=args.tags,
            privacy=args.privacy,
            channel_id=args.channel,
        )

    print(json.dumps(result, indent=2))
