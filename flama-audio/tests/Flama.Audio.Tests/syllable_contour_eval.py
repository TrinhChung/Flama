import wave
import struct
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def examine_f0_segments(path, label):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    samples = struct.unpack(f"<{n_frames}h", raw)
    norm = [s / 32768.0 for s in samples]
    
    win = int(sr * 0.03)
    hop = int(sr * 0.01)
    
    segments = []
    print(f"\n=== Detailed Analysis: {label} ===")
    
    time_pts = []
    f0_pts = []
    rms_pts = []
    
    for i in range(0, len(norm) - win, hop):
        t = i / sr
        frame = norm[i:i+win]
        rms = math.sqrt(sum(x*x for x in frame)/len(frame))
        f0 = 0
        if rms > 0.02:
            min_lag = int(sr / 400)
            max_lag = int(sr / 70)
            corr = [(sum(frame[j]*frame[j+lag] for j in range(len(frame)-lag)), lag) for lag in range(min_lag, max_lag)]
            best_c, best_lag = max(corr, key=lambda x: x[0])
            energy = sum(x*x for x in frame)
            if energy > 0 and best_c / energy > 0.35:
                f0 = sr / best_lag
        time_pts.append(t)
        f0_pts.append(f0)
        rms_pts.append(rms)
        
    # Group into sound bursts (syllables)
    in_burst = False
    burst_start = 0
    bursts = []
    for idx, (t, r) in enumerate(zip(time_pts, rms_pts)):
        if r > 0.025 and not in_burst:
            in_burst = True
            burst_start = t
        elif r <= 0.025 and in_burst:
            in_burst = False
            burst_dur = t - burst_start
            if burst_dur > 0.08: # Syllable > 80ms
                burst_f0s = [f0 for f0, f_t in zip(f0_pts, time_pts) if burst_start <= f_t <= t and f0 > 0]
                if burst_f0s:
                    f0_s = burst_f0s[0]
                    f0_e = burst_f0s[-1]
                    f0_m = sum(burst_f0s)/len(burst_f0s)
                    f0_min = min(burst_f0s)
                    f0_max = max(burst_f0s)
                    bursts.append((burst_start, t, burst_dur, f0_s, f0_e, f0_m, f0_min, f0_max))
    
    print(f"Found {len(bursts)} syllable bursts:")
    for idx, b in enumerate(bursts):
        t0, t1, dur, fs, fe, fm, fmin, fmax = b
        trend = "RISING" if fe - fs > 20 else ("FALLING" if fs - fe > 20 else "FLAT")
        print(f"  Syllable {idx+1:02d} [{t0:5.2f}s - {t1:5.2f}s] ({dur*1000:4.0f}ms): F0 mean={fm:5.1f}Hz, start={fs:5.1f}Hz, end={fe:5.1f}Hz, contour={trend} (min={fmin:5.1f}, max={fmax:5.1f})")

p1 = r"D:\Project\nihongo\flama-audio\tests\Flama.Audio.Tests\bin\Debug\net8.0\mandarin_eval_output\01_phoneme_sibilants_tonguetwister.wav"
p8 = r"D:\Project\nihongo\flama-audio\tests\Flama.Audio.Tests\bin\Debug\net8.0\mandarin_eval_output\08_polyphone_bank_walk_music.wav"
p10 = r"D:\Project\nihongo\flama-audio\tests\Flama.Audio.Tests\bin\Debug\net8.0\mandarin_eval_output\10_prosody_intonation_question.wav"

examine_f0_segments(p1, "01_phoneme_sibilants_tonguetwister (四是四十是十)")
examine_f0_segments(p8, "08_polyphone_bank_walk_music (银行/行走/音乐)")
examine_f0_segments(p10, "10_prosody_intonation_question (散步吗？)")
