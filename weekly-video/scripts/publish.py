"""Explicit local publication only: validate a finished MP4, then update the public catalog."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('episode')
parser.add_argument('--video', type=Path, required=True)
args = parser.parse_args()
if not re.fullmatch(r'\d{4}-W\d{2}', args.episode):
    parser.error('episode must be YYYY-Www')
snapshot = json.loads((ROOT / 'episodes' / args.episode / 'timeline.json').read_text())
duration_target = {'min': 180, 'max': 300, **(snapshot.get('durationTarget') or {})}
catalog_path = ROOT.parent / 'webpage/data/weekly-videos.json'
catalog = json.loads(catalog_path.read_text())
if any(item['id'] == args.episode for item in catalog['episodes']):
    raise SystemExit('This episode is already published; refusing to overwrite the archive.')
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(args.video)]))
video = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
audio = next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')
if (video['width'], video['height'], video['codec_name'], video['r_frame_rate'], audio['codec_name']) != (1920, 1080, 'h264', '30/1', 'aac'):
    raise SystemExit('Expected 1920×1080, 30fps, H.264 + AAC.')
if not duration_target['min'] <= float(probe['format']['duration']) <= duration_target['max'] or abs(float(probe['format']['duration']) - snapshot['durationSeconds']) > .2:
    raise SystemExit(f'Video duration must match the prepared {duration_target["min"]}–{duration_target["max"]}s timeline.')
assets = ROOT / 'public/episodes' / args.episode
for name in ['cover.jpg', 'captions.vtt']:
    if not (assets / name).is_file():
        raise SystemExit(f'Missing {name}; export the cover and prepare subtitles first.')
destination = ROOT.parent / 'webpage/assets/weekly-video' / args.episode
destination.mkdir(parents=True, exist_ok=True)
shutil.copy2(args.video, destination / 'episode.mp4')
for name in ['cover.jpg', 'captions.vtt']:
    shutil.copy2(assets / name, destination / name)
base = f'assets/weekly-video/{args.episode}'
record = {key: snapshot[key] for key in ['id', 'number', 'title', 'description', 'weekStart', 'weekEnd', 'cutoff', 'durationSeconds', 'chapters', 'articles', 'sources']}
record['durationTarget'] = duration_target
record.update(status='published', publishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), video=f'{base}/episode.mp4', poster=f'{base}/cover.jpg', captions=f'{base}/captions.vtt')
catalog['episodes'].append(record)
if (catalog.get('upcoming') or {}).get('id') == args.episode:
    catalog['upcoming'] = None
temporary = catalog_path.with_suffix('.json.tmp')
temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
temporary.replace(catalog_path)
print(f'Published {args.episode} to the local website. No remote deployment was performed.')
