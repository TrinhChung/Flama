using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

public class VoicevoxEngineInstaller
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<VoicevoxEngineInstaller>? _logger;
    private Process? _engineProcess;

    // Official VOICEVOX Engine Windows CPU direct zip package link
    private const string DOWNLOAD_URL = "https://github.com/VOICEVOX/voicevox_engine/releases/download/0.14.4/voicevox_engine-windows-cpu-0.14.4.zip";

    public VoicevoxEngineInstaller(HttpClient httpClient, ILogger<VoicevoxEngineInstaller>? logger = null)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public string GetInstalledEnginePath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localAppData, "Flama", "Audio", "engines", "voicevox");
    }

    public string? FindExecutable()
    {
        // 1. Check Flama Audio Local AppData Engine Dir
        var flamaDir = GetInstalledEnginePath();
        if (Directory.Exists(flamaDir))
        {
            var e1 = Path.Combine(flamaDir, "run.exe");
            var e2 = Path.Combine(flamaDir, "voicevox_engine.exe");
            if (File.Exists(e1)) return e1;
            if (File.Exists(e2)) return e2;
        }

        // 2. Check Standard Windows Standalone VOICEVOX installation paths
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);

        var candidatePaths = new[]
        {
            Path.Combine(localAppData, "Programs", "VOICEVOX", "run.exe"),
            Path.Combine(localAppData, "Programs", "VOICEVOX", "voicevox.exe"),
            Path.Combine(localAppData, "VOICEVOX", "run.exe"),
            Path.Combine(programFiles, "VOICEVOX", "run.exe"),
            Path.Combine(programFiles, "VOICEVOX", "voicevox.exe"),
            Path.Combine(programFilesX86, "VOICEVOX", "run.exe")
        };

        foreach (var p in candidatePaths)
        {
            if (File.Exists(p)) return p;
        }

        return null;
    }

    public bool IsEngineInstalled()
    {
        return !string.IsNullOrEmpty(FindExecutable());
    }

    public async Task<bool> IsPortActiveAsync(CancellationToken ct = default)
    {
        try
        {
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(2000);
            var res = await _httpClient.GetAsync("http://127.0.0.1:50021/version", cts.Token);
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<bool> TryAutoLaunchEngineAsync(CancellationToken ct = default)
    {
        if (await IsPortActiveAsync(ct))
        {
            _logger?.LogInformation("VOICEVOX Engine is already active on port 50021");
            return true;
        }

        var exePath = FindExecutable();
        if (string.IsNullOrEmpty(exePath))
        {
            _logger?.LogInformation("No VOICEVOX executable found on system for auto-launch");
            return false;
        }

        try
        {
            var workDir = Path.GetDirectoryName(exePath) ?? "";
            var startInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "--host 127.0.0.1 --port 50021",
                WorkingDirectory = workDir,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            _engineProcess = Process.Start(startInfo);
            _logger?.LogInformation("Auto-launched VOICEVOX Engine background process from {ExePath}", exePath);
            return _engineProcess != null;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to auto-launch VOICEVOX Engine from {ExePath}", exePath);
            return false;
        }
    }

    public async Task<bool> InstallEngineAsync(IProgress<double>? progress = null, CancellationToken ct = default)
    {
        var targetDir = GetInstalledEnginePath();
        Directory.CreateDirectory(targetDir);

        var tempZip = Path.Combine(Path.GetTempPath(), "flama_voicevox_engine.zip");

        try
        {
            _logger?.LogInformation("Starting VOICEVOX Engine download from {Url}", DOWNLOAD_URL);

            using (var response = await _httpClient.GetAsync(DOWNLOAD_URL, HttpCompletionOption.ResponseHeadersRead, ct))
            {
                response.EnsureSuccessStatusCode();
                var totalBytes = response.Content.Headers.ContentLength ?? -1L;

                using (var contentStream = await response.Content.ReadAsStreamAsync(ct))
                using (var fileStream = new FileStream(tempZip, FileMode.Create, FileAccess.Write, FileShare.None, 8192, true))
                {
                    var buffer = new byte[8192];
                    var totalRead = 0L;
                    int bytesRead;

                    while ((bytesRead = await contentStream.ReadAsync(buffer, 0, buffer.Length, ct)) > 0)
                    {
                        await fileStream.WriteAsync(buffer, 0, bytesRead, ct);
                        totalRead += bytesRead;
                        if (totalBytes > 0)
                        {
                            progress?.Report((double)totalRead / totalBytes * 100.0);
                        }
                    }
                }
            }

            _logger?.LogInformation("Extracting VOICEVOX Engine to {TargetDir}", targetDir);
            ZipFile.ExtractToDirectory(tempZip, targetDir, overwriteFiles: true);

            if (File.Exists(tempZip))
            {
                File.Delete(tempZip);
            }

            return true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to download and install VOICEVOX Engine");
            return false;
        }
    }

    public bool LaunchEngineProcess()
    {
        var exePath = FindExecutable();
        if (exePath == null) return false;

        try
        {
            if (_engineProcess != null && !_engineProcess.HasExited)
            {
                return true;
            }

            var workDir = Path.GetDirectoryName(exePath) ?? "";
            var startInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "--host 127.0.0.1 --port 50021",
                WorkingDirectory = workDir,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            _engineProcess = Process.Start(startInfo);
            return _engineProcess != null;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to launch VOICEVOX engine process {ExePath}", exePath);
            return false;
        }
    }

    public void StopEngineProcess()
    {
        try
        {
            if (_engineProcess != null && !_engineProcess.HasExited)
            {
                _engineProcess.Kill(entireProcessTree: true);
                _engineProcess.Dispose();
                _engineProcess = null;
            }
        }
        catch { }
    }
}
