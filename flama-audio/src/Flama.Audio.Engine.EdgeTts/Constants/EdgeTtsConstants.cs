namespace Flama.Audio.Engine.EdgeTts.Constants;

public static class EdgeTtsConstants
{
    public const string EngineId = "edge-tts";

    public const string BaseUrl = "speech.platform.bing.com/consumer/speech/synthesize/readaloud";
    public const string TrustedClientToken = "6A5AA1D4EAFF4E9FB37E23D68491D6F4";

    public const string WssUrl = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1";
    public const string VoiceListUrl = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list";

    public const string ChromiumFullVersion = "143.0.3650.75";
    public static readonly string ChromiumMajorVersion = ChromiumFullVersion.Split('.')[0];
    public static readonly string SecMsGecVersion = $"2-{ChromiumFullVersion}";

    public const string DefaultOutputFormat = "audio-24khz-48kbitrate-mono-mp3";
    public const string DefaultContentType = "audio/mpeg";

    public const string Origin = "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold";
    public static readonly string DefaultUserAgent = $"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ChromiumMajorVersion}.0.0.0 Safari/537.36 Edg/{ChromiumMajorVersion}.0.0.0";
    public const string DefaultAcceptEncoding = "gzip, deflate, br, zstd";
    public const string DefaultAcceptLanguage = "en-US,en;q=0.9";

    // Rate Limiting & Anti-Abuse Protection
    public const int MinInterRequestDelayMs = 300;     // Minimum pause between consecutive requests (pacing)
    public const int MaxRequestsPerMinute = 50;         // Max requests allowed in a 60-second sliding window
    public const int MaxThrottleWaitMs = 15000;         // Max time to wait for rate window before rejecting (15s)
}
