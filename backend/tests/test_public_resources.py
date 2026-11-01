"""Public catalogs and weekly media must be shared without exposing the website root."""
import asyncio
import json
import unittest
from pathlib import Path

import httpx
from app.main import app


class PublicResourceTests(unittest.TestCase):
    def test_catalogs_media_and_path_boundary(self):
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                root = Path(__file__).resolve().parents[2] / "webpage"
                for catalog in ("changelog.json", "weekly-videos.json"):
                    response = await client.get(f"/public/data/{catalog}")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), json.loads((root / "data" / catalog).read_text()))
                media_root = root / "assets" / "weekly-video"
                poster = next((p for p in media_root.rglob("*") if p.suffix in (".webp", ".jpg", ".png")), None)
                if poster is not None:
                    response = await client.get(f"/public/assets/weekly-video/{poster.relative_to(media_root).as_posix()}")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, poster.read_bytes())
                catalog = json.loads((root / "data" / "weekly-videos.json").read_text())
                for episode in catalog["episodes"]:
                    if episode.get("video"):
                        response = await client.get(f'/public/{episode["video"]}', headers={"Range": "bytes=0-99"})
                        self.assertEqual(response.status_code, 206)
                        self.assertEqual(len(response.content), 100)
                        break
                for path in ("/public/changelog.html", "/public/js/site.js", "/public/data/%2e%2e/changelog.html", "/public/assets/weekly-video/%2e%2e/%2e%2e/changelog.html"):
                    self.assertEqual((await client.get(path)).status_code, 404)
        asyncio.run(check())
