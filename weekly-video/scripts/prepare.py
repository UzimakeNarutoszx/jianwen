"""Freeze per-clause narration/captions for one episode; no web or database writes.

Default: macOS Chinese voice. To reuse an installed CosyVoice runtime, provide
--tts-command with {text} and {output} argument placeholders (no shell execution).
The command must write an audio file at {output}.

Qwen3-TTS notes:
  --unit clause   放一句一段（默认，历史各期的口径不变）
  --unit sentence 按整句合成，语气连贯；字幕仍按标点切成 ≤30 字，时间按该句实测时长
                  在段内按字数分配
  --ref-audio/--ref-text  给出参考音与文本时走 1.7B Base 的 ICL 克隆（日更「见闻」用的声音），
                  不给则用 0.6B CustomVoice 的 --voice 音色
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

def narration_units(text, unit):
    """合成单位：整句（。！？）或分句（逗号也切）。"""
    pattern = r'[^。！？]+[。！？]?' if unit == 'sentence' else r'[^，。；：？！]+[，。；：？！]?'
    return [part.strip() for part in re.findall(pattern, text) if part.strip()]

def caption_chunks(sentence, limit=30):
    """把一句切成字幕行：优先在标点处断开，单段过长再硬切。"""
    chunks, buffer = [], ''
    for token in re.findall(r'[^，；：？！]+[，；：？！]?', sentence):
        while len(token) > limit:
            if buffer:
                chunks.append(buffer)
                buffer = ''
            chunks.append(token[:limit])
            token = token[limit:]
        if len(buffer) + len(token) <= limit:
            buffer += token
        else:
            if buffer:
                chunks.append(buffer)
            buffer = token
    if buffer:
        chunks.append(buffer)
    return [chunk.strip() for chunk in chunks if chunk.strip()]

def split_frames(total, chunks):
    """按字数把一句的帧数分给各行字幕，至少 2 帧，余数补到最后一行。"""
    if len(chunks) == 1:
        return [total]
    weights = [max(len(chunk), 1) for chunk in chunks]
    scale = sum(weights)
    frames = [max(2, round(total * weight / scale)) for weight in weights]
    delta = total - sum(frames)
    index = len(frames) - 1
    while delta != 0:
        step = 1 if delta > 0 else -1
        if frames[index] + step >= 2:
            frames[index] += step
            delta -= step
        else:
            index = (index - 1) % len(frames)
    return frames

def prepare():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode', nargs='?', default='2026-W42')
    parser.add_argument('--voice', help='声线名称；不给时必须用 --ref-audio/--ref-text 走克隆，否则拒绝执行（旧默认音色已停用）')
    parser.add_argument('--engine', choices=['macos', 'qwen3'], default='macos')
    parser.add_argument('--model', default='mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit')
    parser.add_argument('--unit', choices=['clause', 'sentence'], default='clause')
    parser.add_argument('--ref-audio', help='ICL 克隆的参考音频；配合 --ref-text 使用 1.7B Base 模型')
    parser.add_argument('--ref-text', help='参考音频对应的文字')
    parser.add_argument('--tempo', type=float, default=1.0)
    parser.add_argument('--rate', type=int, default=285)
    parser.add_argument('--tts-command', help='Example: /path/to/python synth.py --text {text} --output {output}')
    args = parser.parse_args()
    if not .8 <= args.tempo <= 1.35:
        parser.error('tempo must be between 0.8 and 1.35')
    if bool(args.ref_audio) != bool(args.ref_text):
        parser.error('--ref-audio and --ref-text must be given together')
    retired = {'tingting', 'vivian', 'uncle_fu'}
    if args.voice and args.voice.lower() in retired:
        parser.error(f'--voice {args.voice} 已停用（2026-11-08 听感不佳）。请用 --ref-audio/--ref-text 走 1.7B ICL 克隆，或显式指定其他音色。')
    if args.engine == 'qwen3' and not args.ref_audio and not args.voice:
        parser.error('qwen3 引擎必须显式指定 --voice，或用 --ref-audio/--ref-text 走克隆；不再回落到已停用的 Vivian。')
    if args.engine == 'macos' and not args.tts_command and not args.voice:
        parser.error('macOS 引擎必须显式指定 --voice；旧的默认 Tingting 已移除。')
    reference = None
    if args.ref_audio:
        reference = (Path(args.ref_audio), Path(args.ref_text).read_text(encoding='utf-8').strip())
    synthesize = None
    if args.engine == 'qwen3':
        import mlx.core as mx
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model
        model = load_model(args.model)
        def synthesize(text, output):
            mx.random.seed(42)
            kwargs = dict(lang_code='Chinese', temperature=.65,
                          max_tokens=max(400, min(1600, len(text) * 12)))
            if reference:
                kwargs.update(ref_audio=str(reference[0]), ref_text=reference[1])
            else:
                kwargs.update(voice=args.voice, max_tokens=350)
            chunks = []
            for result in model.generate(text=text, **kwargs):
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
    fingerprint = hashlib.sha256(f'{args.engine}|{args.model}|{args.voice}|{args.unit}|{args.ref_audio}|{args.rate}|{args.tts_command}'.encode()).hexdigest()[:12]
    work = ROOT / '.work' / args.episode / fingerprint
    work.mkdir(parents=True, exist_ok=True)
    cues, slides, pieces = [], [], []
    frame = 0
    for slide_index, slide in enumerate(episode['slides']):
        start = frame
        for unit_index, unit in enumerate(narration_units(slide['narration'], args.unit)):
            text = unit
            key = f'{slide_index:02}-{unit_index:02}'
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
            # 字幕：一句之内按字数把实测时长分给各行，句间不留缝
            chunks = [unit[offset:offset + 30] for offset in range(0, len(unit), 30)]
            if args.unit == 'sentence':
                chunks = caption_chunks(unit)
            allocation = split_frames(frames - 3, chunks)
            cursor = frame
            for chunk, length in zip(chunks, allocation):
                cues.append({'start': cursor / 30, 'end': (cursor + length) / 30, 'text': chunk})
                cursor += length
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
                'durationInFrames': frame, 'durationTarget': duration_target,
                'voice': {'engine': 'Qwen3-TTS / MLX' if synthesize else 'external' if args.tts_command else 'macOS say',
                          'name': '见闻（1.7B ICL 克隆）' if reference else args.voice,
                          'model': args.model if synthesize else None,
                          'unit': args.unit,
                          'tempo': args.tempo}}
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
