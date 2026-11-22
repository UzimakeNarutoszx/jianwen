"""Explicit local publication only: validate a finished MP4, then update the public catalog.

`--sync` is the recovery path for a published episode whose video was re-rendered
(or re-narrated) after the catalog entry was written: it reconciles only the
catalog time fields (durationSeconds/chapters) with episodes/<id>/timeline.json
and never copies or rewrites media.
"""
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
parser.add_argument('--video', type=Path, help='Finished MP4 to publish (required unless --sync)')
parser.add_argument('--replace', action='store_true', help='Re-publish an existing episode in place (e.g. after a voice fix)')
parser.add_argument('--sync', action='store_true', help='Only reconcile duration/chapters in the catalog from timeline.json; never touches media')
args = parser.parse_args()
if not re.fullmatch(r'\d{4}-W\d{2}', args.episode):
    parser.error('episode must be YYYY-Www')
if args.sync and args.video:
    parser.error('--sync does not take --video; it only reconciles catalog time fields.')
if not args.sync and not args.video:
    parser.error('--video is required unless --sync is used.')
snapshot = json.loads((ROOT / 'episodes' / args.episode / 'timeline.json').read_text())
duration_target = {'min': 180, 'max': 300, **(snapshot.get('durationTarget') or {})}
catalog_path = ROOT.parent / 'webpage/data/weekly-videos.json'
catalog = json.loads(catalog_path.read_text())
existing = next((item for item in catalog['episodes'] if item['id'] == args.episode), None)
if args.sync:
    if existing is None:
        raise SystemExit(f'{args.episode} is not in the catalog; nothing to sync.')
    timeline_chapters = [{'title': item['title'], 'seconds': item['seconds']} for item in snapshot['chapters']]
    timeline_duration = snapshot['durationSeconds']
    media = ROOT.parent / 'webpage' / existing['video']
    actual_duration = None
    if media.is_file():
        actual_duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(media)]))
    changes = []
    if existing['durationSeconds'] != timeline_duration:
        changes.append(f'durationSeconds {existing["durationSeconds"]} -> {timeline_duration}')
        existing['durationSeconds'] = timeline_duration
    if existing['chapters'] != timeline_chapters:
        drift = max((abs(old['seconds'] - new['seconds']) for old, new in zip(existing['chapters'], timeline_chapters)), default=None)
        changes.append(f'chapters updated (max drift {drift:.2f}s)' if drift is not None else 'chapters updated')
        existing['chapters'] = timeline_chapters
    if changes:
        existing['updatedAt'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
        temporary = catalog_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(catalog_path)
        print(f'Synced {args.episode}: ' + '; '.join(changes))
    else:
        print(f'{args.episode}: catalog already matches timeline.json; nothing written.')
    if actual_duration is not None:
        print(f'Media {media.relative_to(ROOT.parent)}: {actual_duration:.2f}s; catalog {existing["durationSeconds"]:.2f}s; drift {abs(actual_duration - existing["durationSeconds"]):.2f}s')
    print('Sync does not deploy; run scripts/deploy-webpage.sh to publish the data file.')
    raise SystemExit(0)
if existing and not args.replace:
    raise SystemExit('This episode is already published; pass --replace to update it in place.')
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
record['music'] = (snapshot.get('soundtrack') or {}).get('credit')
record.update(status='published', publishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), video=f'{base}/episode.mp4', poster=f'{base}/cover.jpg', captions=f'{base}/captions.vtt')
if existing:
    record['publishedAt'] = existing.get('publishedAt', record['publishedAt'])
    record['updatedAt'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    catalog['episodes'][catalog['episodes'].index(existing)] = record
    print(f"Replaced {args.episode} in place; publishedAt kept, updatedAt recorded.")
else:
    catalog['episodes'].append(record)
if (catalog.get('upcoming') or {}).get('id') == args.episode:
    catalog['upcoming'] = None
temporary = catalog_path.with_suffix('.json.tmp')
temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
temporary.replace(catalog_path)
print(f'Published {args.episode} to the local website. No remote deployment was performed.')
