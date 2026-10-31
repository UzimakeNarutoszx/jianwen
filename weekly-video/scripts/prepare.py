"""Freeze per-clause narration/captions for one episode; no web or database writes.

Default: macOS Chinese voice. To reuse an installed CosyVoice runtime, provide
--tts-command with {text} and {output} argument placeholders (no shell execution).
The command must write an audio file at {output}.
"""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(args):
    return subprocess.check_output([str(arg) for arg in args], stderr=subprocess.DEVNULL).decode().strip()

def stamp(seconds, separator='.'):
    milliseconds = round(seconds * 1000)
    return f'{milliseconds // 3600000:02}:{milliseconds // 60000 % 60:02}:{milliseconds // 1000 % 60:02}{separator}{milliseconds % 1000:03}'

def prepare():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode', nargs='?', default='2026-W42')
    parser.add_argument('--voice', default='Tingting')
    parser.add_argument('--engine', choices=['macos', 'qwen3'], default='macos')
    parser.add_argument('--model', default='mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit')
    parser.add_argument('--tempo', type=float, default=1.0)
    parser.add_argument('--rate', type=int, default=285)
    parser.add_argument('--tts-command', help='Example: /path/to/python synth.py --text {text} --output {output}')
    args = parser.parse_args()
    if not .8 <= args.tempo <= 1.35:
        parser.error('tempo must be between 0.8 and 1.35')
    synthesize = None
    if args.engine == 'qwen3':
        import mlx.core as mx
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model
        if args.voice == 'Tingting':
            args.voice = 'Vivian'
        model = load_model(args.model)
        def synthesize(text, output):
            mx.random.seed(42)
            chunks = []
            for result in model.generate(text=text, voice=args.voice, lang_code='Chinese', max_tokens=350, temperature=.65):
                mx.eval(result.audio)
                chunks.append(np.array(result.audio))
                sample_rate = result.sample_rate
            if not chunks:
                raise RuntimeError('Qwen returned no audio')
            sf.write(str(output), np.concatenate(chunks), sample_rate, format='WAV')
    if not re.fullmatch(r'\d{4}-W\d{2}', args.episode):
        parser.error('episode must be YYYY-Www')
    source = ROOT / 'episodes' / args.episode
    episode = json.loads((source / 'episode.json').read_text())
    duration_target = {'min': 180, 'max': 300, **(episode.get('durationTarget') or {})}
    public = ROOT / 'public' / 'episodes' / args.episode
    public.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(f'{args.engine}|{args.model}|{args.voice}|{args.rate}|{args.tts_command}'.encode()).hexdigest()[:12]
    work = ROOT / '.work' / args.episode / fingerprint
    work.mkdir(parents=True, exist_ok=True)
    cues, slides, pieces = [], [], []
    frame = 0
    for slide_index, slide in enumerate(episode['slides']):
        start = frame
        clauses = re.findall(r'[^，。；：？！]+[，。；：？！]?', slide['narration'])
        for clause_index, clause in enumerate(clauses):
            # Keep every subtitle within a readable width, including long unpunctuated clauses.
            for part_index, offset in enumerate(range(0, len(clause), 30)):
                text = clause[offset:offset + 30]
                key = f'{slide_index:02}-{clause_index:02}-{part_index}'
                raw, wav = work / f'{key}{".raw.wav" if synthesize else ".aiff"}', work / f'{key}.wav'
                fingerprint_path = work / f'{key}.txt'
                cached = raw.exists() and fingerprint_path.exists() and fingerprint_path.read_text() == text
                if cached:
                    pass
                elif synthesize:
                    synthesize(text, raw)
                elif args.tts_command:
                    command = [item.format(text=text, output=str(raw)) for item in shlex.split(args.tts_command)]
                    run(command)
                else:
                    run(['say', '-v', args.voice, '-r', args.rate, '-o', raw, text])
                fingerprint_path.write_text(text)
                duration = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', raw]))
                frames = round(duration / args.tempo * 30) + 3
                run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', f'atempo={args.tempo},apad,atrim=duration={frames / 30}', '-ar', '48000', '-ac', '1', wav])
                cues.append({'start': frame / 30, 'end': (frame + frames - 3) / 30, 'text': text})
                pieces.append(wav)
                frame += frames
        slides.append({**slide, 'start': start / 30, 'end': frame / 30})
        print(f'{slide_index + 1}/{len(episode["slides"])}: {slide["title"]} · {frame / 30:.2f}s', flush=True)
    if not duration_target['min'] <= frame / 30 <= duration_target['max']:
        raise SystemExit(f'Duration {frame / 30:.2f}s outside {duration_target["min"]}–{duration_target["max"]}s. Adjust --tempo or narration. Existing preview was preserved; generated voice clips are cached.')
    # Only our generated filenames enter the concat manifest.
    concat = work / 'audio.txt'
    concat.write_text('\n'.join(f"file '{p.name}'" for p in pieces))
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', concat, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7', '-c:a', 'aac', '-b:a', '192k', public / 'narration.m4a'])
    chapters = []
    for slide in slides:
        if not chapters or chapters[-1]['title'] != slide['chapter']:
            chapters.append({'title': slide['chapter'], 'seconds': slide['start']})
    prepared = {**episode, 'slides': slides, 'cues': cues, 'chapters': chapters, 'durationSeconds': frame / 30,
                'durationInFrames': frame, 'durationTarget': duration_target, 'voice': {'engine': 'Qwen3-TTS / MLX' if synthesize else 'external' if args.tts_command else 'macOS say', 'name': args.voice, 'model': args.model if synthesize else None, 'rate': args.rate if not synthesize else None, 'tempo': args.tempo}}
    (public / 'timeline.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + '\n')
    (source / 'timeline.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + '\n')
    for extension, separator in [('vtt', '.'), ('srt', ',')]:
        entries = ['WEBVTT\n'] if extension == 'vtt' else []
        for index, cue in enumerate(cues, 1):
            entries.append(f"{index}\n{stamp(cue['start'], separator)} --> {stamp(cue['end'], separator)}\n{cue['text']}\n")
        (public / f'captions.{extension}').write_text('\n'.join(entries))
    print(f"{args.episode}: {frame / 30:.2f}s, {len(cues)} captions; {prepared['voice']}")
    if not duration_target['min'] <= frame / 30 <= duration_target['max']:
        raise SystemExit(f'Duration {frame / 30:.2f}s outside {duration_target["min"]}–{duration_target["max"]}s. Adjust narration/rate and prepare again before publishing.')

if __name__ == '__main__':
    prepare()
