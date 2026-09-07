import os
import sys
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COSY_DIR = os.environ.get(
    "COSYVOICE_DIR",
    os.path.abspath(os.path.join(ROOT_DIR, "..", "cosyvoice3"))
    if os.path.exists(os.path.join(ROOT_DIR, "..", "cosyvoice3"))
    else os.path.join(ROOT_DIR, "engines", "cosyvoice")
)
MATCHA_DIR = os.path.join(COSY_DIR, "third_party", "Matcha-TTS")

sys.path.append(COSY_DIR)
sys.path.append(MATCHA_DIR)

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

def main():
    print(f"[1/3] CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"      GPU: {torch.cuda.get_device_name(0)}")

    model_dir = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B-2512")
    prompt_wav = os.path.join(COSY_DIR, "asset", "zero_shot_prompt.wav")
    prompt_text = "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。"

    print(f"[2/3] Loading CosyVoice 3 model from {model_dir}...")
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir, fp16=True)
    load_time = time.time() - t0
    print(f"      Model loaded in {load_time:.2f}s (Sample Rate: {cosyvoice.sample_rate}Hz)")

    test_text = "你好，我是CosyVoice 3大模型。今天天气真好，很高兴与你见面！"
    print(f"[3/3] Synthesizing text: '{test_text}'...")
    t0 = time.time()
    outputs = list(cosyvoice.inference_zero_shot(test_text, prompt_text, prompt_wav, stream=False))
    synth_time = time.time() - t0

    out_dir = os.path.join(ROOT_DIR, "output", "test")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "cosyvoice3_test.wav")

    speech = outputs[0]["tts_speech"]
    torchaudio.save(out_file, speech, cosyvoice.sample_rate)
    duration = speech.shape[1] / cosyvoice.sample_rate
    rtf = synth_time / duration

    print(f"SUCCESS!")
    print(f"Saved to: {out_file}")
    print(f"Audio Duration: {duration:.2f}s")
    print(f"Inference Time: {synth_time:.2f}s")
    print(f"Real-Time Factor (RTF): {rtf:.3f} (RTF < 1.0 means faster than real time!)")

if __name__ == "__main__":
    main()
