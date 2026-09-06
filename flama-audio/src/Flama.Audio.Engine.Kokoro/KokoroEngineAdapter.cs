using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Engine.Kokoro;

public class KokoroEngineAdapter : ITtsEngineAdapter
{
    public string EngineId => "kokoro";
    private readonly KokoroOnnxEngine _onnxEngine;
    private readonly ILogger<KokoroEngineAdapter>? _logger;

    public KokoroEngineAdapter(ILogger<KokoroEngineAdapter>? logger = null)
    {
        _onnxEngine = new KokoroOnnxEngine();
        _logger = logger;
    }

    public Task<EngineHealth> GetHealthAsync(CancellationToken ct = default)
    {
        string status = _onnxEngine.IsModelLoaded ? "ready" : "not_installed";
        string statusMessage = _onnxEngine.IsModelLoaded
            ? "Kokoro-82M ONNX Neural Engine active"
            : "Kokoro-82M English Model not installed. Click install to download weights.";

        return Task.FromResult(new EngineHealth(status, "1.0.0", statusMessage));
    }

    public bool IsChineseHighPrecisionMode => _onnxEngine.IsChineseHighPrecisionMode;

    public void ReloadChinesePack()
    {
        _onnxEngine.ReloadChineseG2p();
    }

    public Task StartAsync(CancellationToken ct = default)
    {
        try
        {
            _onnxEngine.Initialize();
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Failed to initialize Kokoro ONNX model session during startup");
        }
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken ct = default)
    {
        _onnxEngine.Dispose();
        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<VoiceDescriptor>> ListVoicesAsync(CancellationToken ct = default)
    {
        var voiceIds = _onnxEngine.GetAvailableVoiceIds();
        var voices = new List<VoiceDescriptor>();

        foreach (var id in voiceIds)
        {
            // Exclude Japanese voices from Kokoro (Japanese is handled exclusively by VOICEVOX Engine)
            if (id.StartsWith("jf_", StringComparison.OrdinalIgnoreCase) || id.StartsWith("jm_", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string name = FormatVoiceName(id);
            var (locale, langName, gender) = ResolveVoiceMetadata(id);
            string display = $"{name} [{langName}] ({gender} • Kokoro 82M)";

            voices.Add(new VoiceDescriptor(
                VoiceId: id,
                Name: display,
                SpeakerName: name,
                StyleName: $"{langName} {gender}",
                Locale: locale,
                CommercialSafe: true,
                Attribution: "hexgrad/Kokoro-82M (Apache 2.0 License)"
            ));
        }

        return Task.FromResult<IReadOnlyList<VoiceDescriptor>>(voices);
    }

    public static (string Locale, string LanguageName, string Gender) ResolveVoiceMetadata(string voiceId)
    {
        if (string.IsNullOrEmpty(voiceId))
            return ("en-US", "English (US)", "Female");

        char langPrefix = char.ToLowerInvariant(voiceId[0]);
        bool isFemale = voiceId.Length > 1 && char.ToLowerInvariant(voiceId[1]) == 'f';
        string gender = isFemale ? "Female" : "Male";

        var (locale, langName) = langPrefix switch
        {
            'a' => ("en-US", "English (US)"),
            'b' => ("en-GB", "English (UK)"),
            'j' => ("ja-JP", "Japanese"),
            'z' => ("zh-CN", "Mandarin Chinese"),
            'e' => ("es-ES", "Spanish"),
            'f' => ("fr-FR", "French"),
            'h' => ("hi-IN", "Hindi"),
            'i' => ("it-IT", "Italian"),
            'p' => ("pt-BR", "Portuguese (Brazil)"),
            _ => ("en-US", "English")
        };

        return (locale, langName, gender);
    }

    public Task<TtsResult> SynthesizeAsync(TtsRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.Text))
        {
            throw new ArgumentException("Text parameter cannot be empty.", nameof(request));
        }

        _logger?.LogInformation("Kokoro-82M TTS synthesizing text ({Language}): '{Text}' with voice '{VoiceId}'", request.Language ?? "auto", request.Text, request.VoiceId);

        double speed = request.Options?.Speed ?? 1.0;
        byte[] wavBytes = _onnxEngine.Synthesize(request.Text, request.VoiceId, speed, request.Language);

        var result = new TtsResult(
            AudioData: wavBytes,
            ContentType: "audio/wav",
            EngineId: EngineId,
            VoiceId: request.VoiceId,
            RequestId: request.RequestId
        );

        return Task.FromResult(result);
    }

    private static string FormatVoiceName(string voiceId)
    {
        if (string.IsNullOrEmpty(voiceId)) return "Default";
        var parts = voiceId.Split('_');
        if (parts.Length > 1 && parts[1].Length > 0)
        {
            return char.ToUpper(parts[1][0]) + parts[1][1..];
        }
        return voiceId;
    }
}
