"""配乐节拍分析：估算 BPM、拍点，并找能量突增的"drop"位置，输出 beats/<曲名>.json。

纯 numpy 实现（本机没有 librosa）：频谱通量做起拍包络 → 自相关估 BPM →
动态规划跟踪拍点（Ellis 2007 思路）→ 按拍统计能量找 drop。
用法: python3 promo/beats.py music/岚.mp3 [更多文件...]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR, HOP, NFFT = 22050, 512, 2048
OUT = Path(__file__).resolve().parents[1] / "output/promo-video/beats"


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def onset_envelope(x):
    win = np.hanning(NFFT).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    logmag = np.log1p(100 * mag)
    flux = np.maximum(np.diff(logmag, axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0], flux])
    # 去掉缓慢变化的趋势，再归一化
    k = int(SR / HOP * 0.5)
    trend = np.convolve(flux, np.ones(k) / k, mode="same")
    env = np.maximum(flux - trend, 0)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return env / (env.std() + 1e-9), rms


def tempo(env):
    fps = SR / HOP
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    lags = np.arange(len(ac)) / fps
    bpm = 60 / np.maximum(lags, 1e-9)
    ok = (bpm > 60) & (bpm < 180)
    # 以 120 BPM 为中心的对数高斯先验，减少倍频/半频误判
    prior = np.exp(-0.5 * (np.log2(bpm / 120) / 0.9) ** 2)
    score = np.where(ok, ac * prior, 0)
    lag = int(np.argmax(score))
    return 60 * fps / lag, lag


def track_beats(env, period, tightness=100):
    n = len(env)
    score = env.copy()
    back = np.full(n, -1)
    lo, hi = int(round(period * 0.5)), int(round(period * 2))
    for i in range(hi, n):
        prev = np.arange(i - hi, i - lo)
        pen = -tightness * np.log((i - prev) / period) ** 2
        cand = score[prev] + pen
        j = int(np.argmax(cand))
        score[i] = env[i] + cand[j]
        back[i] = prev[j]
    i = int(np.argmax(score[-hi:])) + n - hi
    beats = []
    while i >= 0:
        beats.append(i)
        i = back[i]
    return np.array(beats[::-1])


def analyse(path):
    x = load(path)
    env, rms = onset_envelope(x)
    bpm, lag = tempo(env)
    beats = track_beats(env, lag)
    t = beats * HOP / SR
    # 每拍能量（dB），用来找 drop：后 8 拍均值相对前 8 拍的抬升
    edges = np.append(beats, len(rms))
    e = np.array([20 * np.log10(rms[a:b].mean() + 1e-9) for a, b in zip(edges[:-1], edges[1:])])
    drops = []
    for i in range(8, len(e) - 8):
        rise = e[i:i + 8].mean() - e[i - 8:i].mean()
        drops.append((float(rise), i))
    drops.sort(reverse=True)
    picked = []
    for rise, i in drops:
        if rise < 2.5:
            break
        if all(abs(i - j) > 16 for _, j in picked):
            picked.append((rise, i))
        if len(picked) == 4:
            break
    return dict(
        file=str(path), duration=round(len(x) / SR, 2), bpm=round(float(bpm), 1),
        beats=[round(float(v), 3) for v in t],
        beat_db=[round(float(v), 1) for v in e],
        drops=[dict(time=round(float(t[i]), 2), beat=int(i), rise_db=round(r, 1)) for r, i in sorted(picked, key=lambda p: p[1])],
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sys.argv[1:]:
        res = analyse(Path(p))
        (OUT / f"{Path(p).stem}.json").write_text(json.dumps(res, ensure_ascii=False))
        iv = np.diff(res["beats"])
        print(f"{Path(p).stem}: {res['bpm']} BPM, {len(res['beats'])} beats, beat interval median {np.median(iv):.3f}s "
              f"(sd {iv.std():.3f}), drops {[(d['time'], d['rise_db']) for d in res['drops']]}")


if __name__ == "__main__":
    main()
