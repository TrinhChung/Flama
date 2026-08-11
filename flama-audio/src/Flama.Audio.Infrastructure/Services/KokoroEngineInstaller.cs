using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

public class KokoroEngineInstaller
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<KokoroEngineInstaller>? _logger;

    private static readonly Dictionary<string, string> RequiredFiles = new()
    {
        { "kokoro-v1.0.int8.onnx", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" },
        { "voices-v1.0.bin", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" },
        { "config.json", "https://huggingface.co/hexgrad/Kokoro-82M/raw/main/config.json" },
        { "cmudict-0.7b.txt", "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict" }
    };

    public KokoroEngineInstaller(HttpClient httpClient, ILogger<KokoroEngineInstaller>? logger = null)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public string GetInstalledEnginePath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localAppData, "Flama", "Audio", "engines", "kokoro");
    }

    public bool IsEngineInstalled()
    {
        var dir = GetInstalledEnginePath();
        if (!Directory.Exists(dir)) return false;

        // ONNX model and voices file are essential
        bool modelExists = File.Exists(Path.Combine(dir, "kokoro-v1.0.int8.onnx")) || File.Exists(Path.Combine(dir, "kokoro-v1_0.onnx"));
        bool voicesExist = File.Exists(Path.Combine(dir, "voices-v1.0.bin"));

        return modelExists && voicesExist;
    }

    public async Task<bool> InstallEngineAsync(IProgress<double>? progress = null, CancellationToken ct = default)
    {
        var targetDir = GetInstalledEnginePath();
        Directory.CreateDirectory(targetDir);

        int totalFiles = RequiredFiles.Count;
        int completedFiles = 0;

        try
        {
            _logger?.LogInformation("Starting Kokoro-82M Engine download to {TargetDir}", targetDir);

            foreach (var (fileName, downloadUrl) in RequiredFiles)
            {
                var destPath = Path.Combine(targetDir, fileName);
                var tempPath = destPath + ".part";

                if (File.Exists(destPath))
                {
                    completedFiles++;
                    progress?.Report((double)completedFiles / totalFiles * 100.0);
                    continue;
                }

                _logger?.LogInformation("Downloading Kokoro file {FileName} from {Url}", fileName, downloadUrl);

                using (var response = await _httpClient.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead, ct))
                {
                    response.EnsureSuccessStatusCode();

                    using (var contentStream = await response.Content.ReadAsStreamAsync(ct))
                    using (var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None, 8192, true))
                    {
                        var buffer = new byte[8192];
                        int bytesRead;

                        while ((bytesRead = await contentStream.ReadAsync(buffer, 0, buffer.Length, ct)) > 0)
                        {
                            await fileStream.WriteAsync(buffer, 0, bytesRead, ct);
                        }
                    }
                }

                if (File.Exists(destPath))
                {
                    File.Delete(destPath);
                }
                File.Move(tempPath, destPath);

                completedFiles++;
                progress?.Report((double)completedFiles / totalFiles * 100.0);
            }

            _logger?.LogInformation("Kokoro-82M Engine installed successfully.");
            return true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to download and install Kokoro-82M Engine");
            return false;
        }
    }
}
