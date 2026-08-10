using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Flama.Audio.Engine.Kokoro.G2P;
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

namespace Flama.Audio.Engine.Kokoro;

/// <summary>
/// Execution engine for Hexgrad Kokoro-82M TTS model using ONNX Runtime CPU.
/// Model specs: 82M parameters, 24kHz audio output.
/// Repo: https://github.com/hexgrad/kokoro / https://hf.co/hexgrad/Kokoro-82M
/// </summary>
public class KokoroOnnxEngine : IDisposable
{
    private readonly string _modelPath;
    private readonly string _voicesPath;
    private readonly string _configPath;
    private readonly string _cmuDictPath;

    private InferenceSession? _session;
    private EnglishG2P? _g2p;
    private ChineseG2P? _chineseG2p;
    private KokoroTokenizer? _tokenizer;
    private VoiceManager? _voiceManager;

    private readonly object _initLock = new();
    private string _tokenInputName = "tokens";
    private string _styleInputName = "style";
    private string _speedInputName = "speed";
    private int _styleDim = 256;

    public KokoroOnnxEngine(string? baseEngineDir = null)
    {
        string localDataFolder = baseEngineDir
            ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Flama", "Audio", "engines", "kokoro");

        string appDirFolder = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "models");

        // Model path resolution
        if (File.Exists(Path.Combine(localDataFolder, "kokoro-v1.0.int8.onnx")))
        {
            _modelPath = Path.Combine(localDataFolder, "kokoro-v1.0.int8.onnx");
        }
        else if (File.Exists(Path.Combine(localDataFolder, "kokoro-v1_0.onnx")))
        {
            _modelPath = Path.Combine(localDataFolder, "kokoro-v1_0.onnx");
        }
        else
        {
            _modelPath = Path.Combine(appDirFolder, "kokoro-v1.0.int8.onnx");
        }

        _voicesPath = Path.Combine(localDataFolder, "voices-v1.0.bin");
        _configPath = Path.Combine(localDataFolder, "config.json");
        _cmuDictPath = Path.Combine(localDataFolder, "cmudict-0.7b.txt");
    }

    public bool IsModelLoaded => _session != null || File.Exists(_modelPath);

    public void Initialize()
    {
        if (_session != null && _g2p != null) return;

        lock (_initLock)
        {
            if (_session != null && _g2p != null) return; // double-check inside lock

            // Initialize helper modules
            var cmuDict = new CmuDictionary(File.Exists(_cmuDictPath) ? _cmuDictPath : null);
            _g2p = new EnglishG2P(cmuDict);
            _tokenizer = new KokoroTokenizer(File.Exists(_configPath) ? _configPath : null);
            _voiceManager = new VoiceManager(File.Exists(_voicesPath) ? _voicesPath : null);

            if (File.Exists(_modelPath))
            {
                var options = new SessionOptions
                {
                    IntraOpNumThreads = Math.Min(4, Environment.ProcessorCount),
                    ExecutionMode = ExecutionMode.ORT_SEQUENTIAL,
                    GraphOptimizationLevel = GraphOptimizationLevel.ORT_ENABLE_ALL
                };

                _session = new InferenceSession(_modelPath, options);
                DetectOnnxMetadata(_session);
            }
        }
    }

    public byte[] Synthesize(string text, string voiceId, double speed = 1.0, string? language = null)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            throw new ArgumentException("Text cannot be empty", nameof(text));
        }

        Initialize();

        if (_g2p == null || _tokenizer == null || _voiceManager == null)
        {
            throw new InvalidOperationException("Kokoro engine components failed to initialize.");
        }

        if (_chineseG2p == null)
        {
            _chineseG2p = new ChineseG2P(_g2p);
        }

        IG2P g2p = ResolveG2P(language, voiceId);

        // 1. Text -> IPA Phonemes
        string phonemes = g2p.Phonemize(text);

        // 2. IPA Phonemes -> Token IDs
        long[] tokenIds = _tokenizer.Tokenize(phonemes);

        // 3. Get style embedding vector
        float[] styleVector = _voiceManager.GetStyleVector(voiceId, tokenIds.Length);

        // 4. ONNX Inference or Fallback
        float[] pcmSamples;
        if (_session != null)
        {
            pcmSamples = RunOnnxInference(tokenIds, styleVector, (float)speed);
        }
        else
        {
            throw new FileNotFoundException($"Kokoro ONNX model file not found at '{_modelPath}'. Please install the Kokoro engine.");
        }

        // 5. Package PCM to 24kHz WAV
        return PackageWav24kHz(pcmSamples);
    }

    private IG2P ResolveG2P(string? language, string voiceId)
    {
        if ((language != null && language.Equals("zh-CN", StringComparison.OrdinalIgnoreCase)) ||
            (voiceId != null && voiceId.StartsWith("z", StringComparison.OrdinalIgnoreCase)))
        {
            return _chineseG2p!;
        }
        return _g2p!;
    }

    public IReadOnlyList<string> GetAvailableVoiceIds()
    {
        Initialize();
        return _voiceManager?.ListVoiceIds() ?? new List<string> { "af_bella", "af_sarah", "am_adam", "am_michael", "bf_emma", "bm_george" };
    }

    private float[] RunOnnxInference(long[] tokenIds, float[] voiceVector, float speed)
    {
        if (_session == null) throw new InvalidOperationException("ONNX session not initialized.");

        // Input 1: tokens [1, N]
        var tokenTensor = new DenseTensor<long>(tokenIds, new[] { 1, tokenIds.Length });

        // Ensure voiceVector matches expected shape [1, _styleDim]
        float[] matchedStyle = voiceVector;
        if (voiceVector.Length != _styleDim)
        {
            matchedStyle = new float[_styleDim];
            Array.Copy(voiceVector, matchedStyle, Math.Min(voiceVector.Length, _styleDim));
        }
        var styleTensor = new DenseTensor<float>(matchedStyle, new[] { 1, _styleDim });

        // Input 3: speed [1]
        var speedTensor = new DenseTensor<float>(new[] { speed }, new[] { 1 });

        var inputs = new List<NamedOnnxValue>
        {
            NamedOnnxValue.CreateFromTensor(_tokenInputName, tokenTensor),
            NamedOnnxValue.CreateFromTensor(_styleInputName, styleTensor),
            NamedOnnxValue.CreateFromTensor(_speedInputName, speedTensor)
        };

        using var results = _session.Run(inputs);
        // Use first output tensor — models may name it "audio", a numeric index, etc.
        var audioOutput = results.First().AsTensor<float>();

        return audioOutput.ToArray();
    }

    private void DetectOnnxMetadata(InferenceSession session)
    {
        var inputNames = session.InputMetadata.Keys.ToList();
        
        if (inputNames.Contains("input_ids", StringComparer.OrdinalIgnoreCase))
        {
            _tokenInputName = inputNames.First(n => n.Equals("input_ids", StringComparison.OrdinalIgnoreCase));
        }
        else if (inputNames.Contains("tokens", StringComparer.OrdinalIgnoreCase))
        {
            _tokenInputName = inputNames.First(n => n.Equals("tokens", StringComparison.OrdinalIgnoreCase));
        }

        if (inputNames.Contains("style", StringComparer.OrdinalIgnoreCase))
        {
            _styleInputName = inputNames.First(n => n.Equals("style", StringComparison.OrdinalIgnoreCase));
            var shape = session.InputMetadata[_styleInputName].Dimensions;
            if (shape != null && shape.Length >= 2 && shape[1] > 0)
            {
                _styleDim = shape[1];
            }
        }

        if (inputNames.Contains("speed", StringComparer.OrdinalIgnoreCase))
        {
            _speedInputName = inputNames.First(n => n.Equals("speed", StringComparison.OrdinalIgnoreCase));
        }
    }

    private static byte[] PackageWav24kHz(float[] samples)
    {
        const int sampleRate = 24000;
        const short numChannels = 1;
        const short bitsPerSample = 16;

        using var ms = new MemoryStream();
        using var writer = new BinaryWriter(ms);

        int dataSize = samples.Length * 2;

        // RIFF Header
        writer.Write(Encoding.ASCII.GetBytes("RIFF"));
        writer.Write(36 + dataSize);
        writer.Write(Encoding.ASCII.GetBytes("WAVE"));

        // fmt Chunk
        writer.Write(Encoding.ASCII.GetBytes("fmt "));
        writer.Write(16);
        writer.Write((short)1); // PCM
        writer.Write(numChannels);
        writer.Write(sampleRate);
        writer.Write(sampleRate * numChannels * (bitsPerSample / 8));
        writer.Write((short)(numChannels * (bitsPerSample / 8)));
        writer.Write(bitsPerSample);

        // data Chunk
        writer.Write(Encoding.ASCII.GetBytes("data"));
        writer.Write(dataSize);

        foreach (float sample in samples)
        {
            float clamped = Math.Clamp(sample, -1.0f, 1.0f);
            short pcm = (short)(clamped * short.MaxValue);
            writer.Write(pcm);
        }

        writer.Flush();
        return ms.ToArray();
    }

    public void Dispose()
    {
        _session?.Dispose();
        _session = null;
    }
}
