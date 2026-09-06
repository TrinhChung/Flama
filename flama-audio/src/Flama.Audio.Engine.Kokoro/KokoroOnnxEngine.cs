using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Flama.G2P;
using Flama.G2P.English;
using Flama.G2P.Chinese;
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
            _chineseG2p = new ChineseG2P(_g2p);
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

        if (_session == null)
        {
            throw new FileNotFoundException($"Kokoro ONNX model file not found at '{_modelPath}'. Please install the Kokoro engine.");
        }

        IG2P g2p = ResolveG2P(language, voiceId);

        var chunks = SplitIntoChunks(text);
        if (chunks.Count <= 1)
        {
            float[] samples = SynthesizeSingleChunk(chunks.Count == 1 ? chunks[0] : text, voiceId, speed, g2p);
            return PackageWav24kHz(samples);
        }

        var allSamples = new List<float>();
        const int silenceSamples = (int)(24000 * 0.12); // ~120ms natural pause between sentences
        var silence = new float[silenceSamples];

        for (int i = 0; i < chunks.Count; i++)
        {
            float[] chunkSamples = SynthesizeSingleChunk(chunks[i], voiceId, speed, g2p);
            if (chunkSamples.Length > 0)
            {
                allSamples.AddRange(chunkSamples);
                if (i < chunks.Count - 1)
                {
                    allSamples.AddRange(silence);
                }
            }
        }

        return PackageWav24kHz(allSamples.ToArray());
    }

    private float[] SynthesizeSingleChunk(string chunkText, string voiceId, double speed, IG2P g2p)
    {
        // 1. Text -> IPA Phonemes
        string phonemes = g2p.Phonemize(chunkText);
        if (string.IsNullOrWhiteSpace(phonemes))
        {
            return Array.Empty<float>();
        }

        // 2. IPA Phonemes -> Token IDs
        long[] tokenIds = _tokenizer!.Tokenize(phonemes);
        if (tokenIds.Length <= 2)
        {
            return Array.Empty<float>();
        }

        // 3. Get style embedding vector
        float[] styleVector = _voiceManager!.GetStyleVector(voiceId, tokenIds.Length);

        // 4. ONNX Inference
        return RunOnnxInference(tokenIds, styleVector, (float)speed);
    }

    private static List<string> SplitIntoChunks(string text, int maxChunkChars = 100)
    {
        if (string.IsNullOrWhiteSpace(text)) return new List<string>();
        string trimmed = text.Trim();
        if (trimmed.Length <= maxChunkChars) return new List<string> { trimmed };

        // 1. Split on sentence terminators: 。！？!?\n and English period followed by whitespace
        string sentencePattern = @"(?<=[。！？!?\n])(?![。！？!?\n])\s*|(?<=\.)(?!\.)\s+";
        var rawSentences = Regex.Split(trimmed, sentencePattern)
            .Select(s => s.Trim())
            .Where(s => !string.IsNullOrEmpty(s))
            .ToList();

        var chunks = new List<string>();
        foreach (var sentence in rawSentences)
        {
            if (sentence.Length <= maxChunkChars)
            {
                chunks.Add(sentence);
            }
            else
            {
                // Sub-split by clause punctuation: ，, ；; ：:
                string clausePattern = @"(?<=[，,；;：:])(?![，,；;：:])\s*";
                var rawClauses = Regex.Split(sentence, clausePattern)
                    .Select(s => s.Trim())
                    .Where(s => !string.IsNullOrEmpty(s))
                    .ToList();

                var currentChunk = new StringBuilder();
                foreach (var clause in rawClauses)
                {
                    if (currentChunk.Length + clause.Length <= maxChunkChars)
                    {
                        currentChunk.Append(clause);
                    }
                    else
                    {
                        if (currentChunk.Length > 0)
                        {
                            chunks.Add(currentChunk.ToString().Trim());
                            currentChunk.Clear();
                        }

                        if (clause.Length <= maxChunkChars)
                        {
                            currentChunk.Append(clause);
                        }
                        else
                        {
                            for (int k = 0; k < clause.Length; k += maxChunkChars)
                            {
                                int len = Math.Min(maxChunkChars, clause.Length - k);
                                chunks.Add(clause.Substring(k, len).Trim());
                            }
                        }
                    }
                }
                if (currentChunk.Length > 0)
                {
                    chunks.Add(currentChunk.ToString().Trim());
                }
            }
        }

        return chunks.Count > 0 ? chunks : new List<string> { trimmed };
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

    public bool IsChineseHighPrecisionMode => _chineseG2p?.IsHighPrecisionMode ?? false;

    public void ReloadChineseG2p()
    {
        lock (_initLock)
        {
            if (_chineseG2p != null)
            {
                _chineseG2p.InitializeLexicon();
            }
            else if (_g2p != null)
            {
                _chineseG2p = new ChineseG2P(_g2p);
            }
        }
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
