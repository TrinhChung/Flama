using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Flama.Audio.Core.Models;
using Flama.Audio.Engine.EdgeTts;
using Xunit;
using Xunit.Abstractions;

namespace Flama.Audio.Tests;

public class XunitLogger<T> : Microsoft.Extensions.Logging.ILogger<T>
{
    private readonly ITestOutputHelper _output;
    public XunitLogger(ITestOutputHelper output) { _output = output; }
    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(Microsoft.Extensions.Logging.LogLevel logLevel) => true;
    public void Log<TState>(Microsoft.Extensions.Logging.LogLevel logLevel, Microsoft.Extensions.Logging.EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        try { _output.WriteLine($"[{logLevel}] [{typeof(T).Name}] {formatter(state, exception)} {(exception != null ? exception.ToString() : "")}"); } catch { }
    }
}

public class EdgeTtsContinuousGenerationTests
{
    private readonly ITestOutputHelper _output;

    public EdgeTtsContinuousGenerationTests(ITestOutputHelper output)
    {
        _output = output;
    }

    private static bool IsMp3(byte[] data)
    {
        if (data == null || data.Length < 4) return false;
        if (data[0] == 0x49 && data[1] == 0x44 && data[2] == 0x33) return true;
        if (data[0] == 0xFF && (data[1] & 0xE0) == 0xE0) return true;
        return false;
    }

    [Fact]
    public async Task GenerateMultipleAudioFilesContinuously_SucceedsAndSavesValidMp3s()
    {
        var outputDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_output", "edge_tts_continuous");
        if (Directory.Exists(outputDir))
        {
            Directory.Delete(outputDir, true);
        }
        Directory.CreateDirectory(outputDir);

        var clientLogger = new XunitLogger<Flama.Audio.Engine.EdgeTts.Network.EdgeWebSocketClient>(_output);
        var client = new Flama.Audio.Engine.EdgeTts.Network.EdgeWebSocketClient(clientLogger);
        var adapterLogger = new XunitLogger<EdgeTtsEngineAdapter>(_output);
        using var adapter = new EdgeTtsEngineAdapter(client: client, logger: adapterLogger);

        var health = await adapter.GetHealthAsync();
        Assert.Equal("ready", health.Status);

        var testItems = new List<(string Lang, string Voice, string Text)>
        {
            // --- Japanese (10 items) ---
            ("ja-JP", "ja-JP-NanamiNeural", "こんにちは。Flama Audioへようこそ。"),
            ("ja-JP", "ja-JP-NanamiNeural", "日本語の単語学習を始めましょう。"),
            ("ja-JP", "ja-JP-KeitaNeural", "毎日少しずつ練習することが大切です。"),
            ("ja-JP", "ja-JP-KeitaNeural", "継続は力なり。"),
            ("ja-JP", "ja-JP-NanamiNeural", "猫が庭で日向ぼっこをしています。"),
            ("ja-JP", "ja-JP-NanamiNeural", "桜の花がとても綺麗に咲いています。"),
            ("ja-JP", "ja-JP-KeitaNeural", "明日の天気は晴れの予報です。"),
            ("ja-JP", "ja-JP-NanamiNeural", "辞書を引いて新しい言葉を覚えます。"),
            ("ja-JP", "ja-JP-KeitaNeural", "発音の練習を繰り返します。"),
            ("ja-JP", "ja-JP-NanamiNeural", "ありがとうございました。"),

            // --- English (10 items) ---
            ("en-US", "en-US-AvaNeural", "Hello, welcome to Flama Audio text to speech system."),
            ("en-US", "en-US-AvaNeural", "Mastering Japanese vocabulary step by step."),
            ("en-US", "en-US-AndrewNeural", "Consistency is the foundation of high language proficiency."),
            ("en-US", "en-US-AndrewNeural", "This test verifies continuous audio synthesis without interruption."),
            ("en-US", "en-US-AvaNeural", "All audio files are generated with pristine clarity."),
            ("en-US", "en-US-AvaNeural", "Spaced repetition helps you remember words longer."),
            ("en-US", "en-US-AndrewNeural", "Audio generation runs smoothly and reliably."),
            ("en-US", "en-US-AvaNeural", "Listening comprehension improves with daily audio exposure."),
            ("en-US", "en-US-AndrewNeural", "Batch speech generation is working as expected."),
            ("en-US", "en-US-AvaNeural", "Thank you for using Flama Audio companion."),

            // --- Vietnamese (10 items) ---
            ("vi-VN", "vi-VN-HoaiMyNeural", "Xin chào, chào mừng bạn đến với Flama Audio."),
            ("vi-VN", "vi-VN-HoaiMyNeural", "Học từ vựng tiếng Nhật mỗi ngày cùng Flama."),
            ("vi-VN", "vi-VN-NamMinhNeural", "Kiên trì luyện tập là chìa khóa của thành công."),
            ("vi-VN", "vi-VN-NamMinhNeural", "Chúc bạn một ngày học tập thật hiệu quả."),
            ("vi-VN", "vi-VN-HoaiMyNeural", "Âm thanh được phát âm rõ ràng và tự nhiên."),
            ("vi-VN", "vi-VN-NamMinhNeural", "Hệ thống lặp lại ngắt quãng giúp ghi nhớ sâu hơn."),
            ("vi-VN", "vi-VN-HoaiMyNeural", "Thời tiết ngày mai dự báo sẽ có nắng đẹp."),
            ("vi-VN", "vi-VN-NamMinhNeural", "Tự động tạo âm thanh cho các thẻ từ vựng."),
            ("vi-VN", "vi-VN-HoaiMyNeural", "Hẹn gặp lại bạn trong bài học tiếp theo."),
            ("vi-VN", "vi-VN-NamMinhNeural", "Cảm ơn bạn đã sử dụng Flama Audio.")
        };

        int totalCount = testItems.Count;
        int successCount = 0;
        var latencies = new List<long>();
        var generatedFiles = new List<string>();
        var totalSw = Stopwatch.StartNew();

        _output.WriteLine($"=== BẮT ĐẦU TEST GEN LIÊN TỤC {totalCount} FILE AUDIO VỚI EDGE TTS ===");
        _output.WriteLine($"Thư mục lưu trữ: {outputDir}");

        for (int i = 0; i < totalCount; i++)
        {
            var item = testItems[i];
            int fileIndex = i + 1;
            var itemSw = Stopwatch.StartNew();

            var request = new TtsRequest(
                RequestId: Guid.NewGuid().ToString("N"),
                EngineId: "edge-tts",
                Language: item.Lang,
                VoiceId: item.Voice,
                Text: item.Text
            );

            try
            {
                var result = await adapter.SynthesizeAsync(request);
                itemSw.Stop();
                latencies.Add(itemSw.ElapsedMilliseconds);

                Assert.NotNull(result);
                Assert.NotNull(result.AudioData);
                Assert.True(result.AudioData.Length > 0, $"File {fileIndex} audio byte length is 0");

                bool validMp3 = IsMp3(result.AudioData);
                Assert.True(validMp3, $"File {fileIndex} is not a valid MP3 audio stream");

                string fileName = $"audio_{fileIndex:D2}_{item.Voice}.mp3";
                string filePath = Path.Combine(outputDir, fileName);
                await File.WriteAllBytesAsync(filePath, result.AudioData);
                generatedFiles.Add(filePath);

                var fi = new FileInfo(filePath);
                Assert.True(fi.Exists);
                Assert.Equal(result.AudioData.Length, fi.Length);

                successCount++;
                _output.WriteLine($"[File {fileIndex:D2}/{totalCount:D2}] OK ({itemSw.ElapsedMilliseconds}ms) | {fi.Length:N0} bytes | {item.Lang} | Voice: {item.Voice} | Text: \"{item.Text}\"");
            }
            catch (Exception ex)
            {
                itemSw.Stop();
                _output.WriteLine($"[File {fileIndex:D2}/{totalCount:D2}] THẤT BẠI: {ex.GetType().Name} - {ex.Message} (sau {itemSw.ElapsedMilliseconds}ms)");
            }
        }

        totalSw.Stop();
        double avgLatency = latencies.Count > 0 ? latencies.Average() : 0;
        double throughputPerMinute = totalCount / (totalSw.Elapsed.TotalMinutes);

        _output.WriteLine("=================================================");
        _output.WriteLine("=== KẾT QUẢ TỔNG HỢP KIỂM THỬ GEN LIÊN TỤC ===");
        _output.WriteLine($"Tổng số file yêu cầu: {totalCount}");
        _output.WriteLine($"Số file thành công: {successCount}/{totalCount} ({(successCount * 100.0 / totalCount):F1}%)");
        _output.WriteLine($"Tổng thời gian: {totalSw.ElapsedMilliseconds}ms ({totalSw.Elapsed.TotalSeconds:F2}s)");
        _output.WriteLine($"Độ trễ trung bình: {avgLatency:F1}ms / file");
        if (latencies.Count > 0)
        {
            _output.WriteLine($"Độ trễ ngắn nhất: {latencies.Min()}ms | Dài nhất: {latencies.Max()}ms");
        }
        _output.WriteLine($"Tốc độ tạo thực tế: {throughputPerMinute:F1} file/phút");
        _output.WriteLine($"Tất cả {generatedFiles.Count} file mp3 đã được ghi thành công vào đĩa.");
        _output.WriteLine("=================================================");

        Assert.Equal(totalCount, successCount);
        Assert.Equal(totalCount, generatedFiles.Count);
    }
}
