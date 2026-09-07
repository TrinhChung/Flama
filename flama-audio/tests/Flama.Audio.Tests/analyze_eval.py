import wave
import struct
import math
import os
import glob

wav_dir = r"D:\Project\nihongo\flama-audio\tests\Flama.Audio.Tests\bin\Debug\net8.0\mandarin_eval_output"

def analyze_wav(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    
    samples = struct.unpack(f"<{n_frames * n_ch}h", raw)
    if n_ch > 1:
        samples = samples[::n_ch]
    
    # Normalize to -1.0 to 1.0
    norm = [s / 32768.0 for s in samples]
    duration = n_frames / sr
    
    # Frame-based analysis (window 25ms, hop 10ms)
    win_size = int(sr * 0.025)
    hop_size = int(sr * 0.010)
    
    f0_list = []
    rms_list = []
    
    for i in range(0, len(norm) - win_size, hop_size):
        frame = norm[i:i + win_size]
        # RMS
        rms = math.sqrt(sum(x * x for x in frame) / len(frame))
        rms_list.append(rms)
        
        # Simple Autocorrelation F0 estimation for voiced frames
        if rms > 0.02:  # Voiced threshold
            corr = []
            min_lag = int(sr / 400) # 400 Hz max
            max_lag = int(sr / 70)  # 70 Hz min
            for lag in range(min_lag, max_lag):
                c = sum(frame[j] * frame[j + lag] for j in range(len(frame) - lag))
                corr.append((c, lag))
            if corr:
                best_c, best_lag = max(corr, key=lambda x: x[0])
                # Check peak quality
                energy0 = sum(x*x for x in frame)
                if energy0 > 0 and best_c / energy0 > 0.35:
                    f0 = sr / best_lag
                    f0_list.append(f0)
    
    avg_f0 = sum(f0_list) / len(f0_list) if f0_list else 0
    min_f0 = min(f0_list) if f0_list else 0
    max_f0 = max(f0_list) if f0_list else 0
    pitch_range = max_f0 - min_f0 if f0_list else 0
    
    # Silence vs active ratio
    active_frames = sum(1 for r in rms_list if r > 0.015)
    total_frames = len(rms_list)
    speech_ratio = (active_frames / total_frames) if total_frames > 0 else 0
    
    return {
        "duration": duration,
        "avg_f0": avg_f0,
        "min_f0": min_f0,
        "max_f0": max_f0,
        "pitch_range": pitch_range,
        "speech_ratio": speech_ratio,
        "num_voiced": len(f0_list)
    }

print(f"{'Filename':<35} | {'Dur(s)':<7} | {'Avg F0':<7} | {'Min F0':<7} | {'Max F0':<7} | {'F0 Range':<8} | {'Speech%':<7}")
print("-" * 90)

for f in sorted(glob.glob(os.path.join(wav_dir, "*.wav"))):
    name = os.path.basename(f)
    info = analyze_wav(f)
    print(f"{name:<35} | {info['duration']:<7.2f} | {info['avg_f0']:<7.1f} | {info['min_f0']:<7.1f} | {info['max_f0']:<7.1f} | {info['pitch_range']:<8.1f} | {info['speech_ratio']*100:<7.1f}")
