"""Mix the documented user-original score; leave the original and narration intact."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode')
    parser.add_argument('--source', type=Path, help='Original 雨.mp3, copied into this episode snapshot on first use')
    args = parser.parse_args()
    if not re.fullmatch(r'\d{4}-W\d{2}', args.episode):
        parser.error('Invalid episode ID')
    source = ROOT / 'episodes' / args.episode
    public = ROOT / 'public/episodes' / args.episode
    timeline = json.loads((source / 'timeline.json').read_text())
    music = source / 'music/雨.mp3'
    if args.source:
        if music.exists() and music.read_bytes() != args.source.read_bytes():
            parser.error('Music snapshot differs; do not replace an existing episode source')
        music.parent.mkdir(parents=True, exist_ok=True)
        if not music.exists():
            shutil.copyfile(args.source, music)
    if not music.exists():
        parser.error('Provide --source on first use; only the documented original 雨 is cleared for this workflow')
    duration = timeline['durationSeconds']
    track_duration = float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=nw=1:nk=1', str(music)], text=True))
    overlap = 3
    copies = max(1, int((duration - overlap) // (track_duration - overlap)) + 1)
    work = ROOT / '.work' / args.episode
    work.mkdir(parents=True, exist_ok=True)
    temporary = work / 'soundtrack.m4a'
    command = ['ffmpeg', '-hide_banner', '-y', '-i', str(public / 'narration.m4a')]
    for _ in range(copies):
        command += ['-i', str(music)]
    filters = ['[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][key]']
    for i in range(copies):
        filters.append(f'[{i+1}:a]aresample=48000,asetpts=PTS-STARTPTS[m{i}]')
    bed = 'm0'
    for i in range(1, copies):
        filters.append(f'[{bed}][m{i}]acrossfade=d={overlap}:c1=tri:c2=tri[loop{i}]')
        bed = f'loop{i}'
    filters += [
        f'[{bed}]atrim=duration={duration},loudnorm=I=-30:TP=-6:LRA=7,'
        f'aresample=48000,afade=t=in:d=3,afade=t=out:st={duration-5}:d=5[bed]',
        '[bed][key]sidechaincompress=threshold=0.035:ratio=4:attack=20:release=350[ducked]',
        f'[voice][ducked]amix=inputs=2:normalize=0,atrim=duration={duration},'
        'loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000[out]'
    ]
    command += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-vn',
                '-c:a', 'aac', '-b:a', '192k', '-t', str(duration), str(temporary)]
    subprocess.run(command, check=True)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    filename = f'soundtrack-{digest[:12]}.m4a'
    shutil.copyfile(temporary, public / filename)
    timeline['soundtrack'] = {'file': filename, 'sha256': digest, 'credit': '原创配乐《雨》 · 昔日烬'}
    for target in [source / 'timeline.json', public / 'timeline.json']:
        target.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + '\n')
    provenance_path = source / 'provenance.json'
    provenance = json.loads(provenance_path.read_text())
    provenance['music'] = {
        'title': '雨', 'artistTag': '昔日烬',
        'rightsBasis': 'User explicitly confirmed in this task on 2026-10-17 that 憩、柱、雨、岚、终 are their originals and authorized their use. See music-library.json. Earlier CLAUDE_HANDOFF.md entry 2026-10-11 also identifies 雨 as user-original. No public-domain or CC license claim.',
        'sourceSnapshot': 'music/雨.mp3',
        'sourceSha256': hashlib.sha256(music.read_bytes()).hexdigest(),
        'narrationSha256': hashlib.sha256((public / 'narration.m4a').read_bytes()).hexdigest(),
        'mix': {'loopCrossfadeSeconds': overlap, 'fadeInSeconds': 3, 'fadeOutSeconds': 5,
                'musicTargetLUFS': -30, 'speechDucking': True, 'mixTargetLUFS': -16, 'mixTruePeakCeilingDb': -1.5},
        'output': timeline['soundtrack']
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    print(f'Ready: {public / filename} ({duration:.3f}s); clean narration preserved')


if __name__ == '__main__':
    main()
