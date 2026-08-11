using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

public class VoicevoxEngineInstaller
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<VoicevoxEngineInstaller>? _logger;
    private Process? _engineProcess;

    // Official VOICEVOX Engine Windows CPU package. This third-party package is
    // verified before extraction and is never re-signed by Flama.
    private const string DOWNLOAD_URL = "https://github.com/VOICEVOX/voicevox_engine/releases/download/0.14.4/voicevox_engine-windows-cpu-0.14.4.vvpp";
    internal const string DOWNLOAD_SHA256 = "E425A8F6A7A3B36C7A2646242E23D7E748F23A202FC3D36A07FF7F8E81BD8E50";

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
            var e3 = Path.Combine(flamaDir, "voicevox_engine", "run.exe");
            var e4 = Path.Combine(flamaDir, "vv-engine", "run.exe");
            if (File.Exists(e1)) return e1;
            if (File.Exists(e2)) return e2;
            if (File.Exists(e3)) return e3;
            if (File.Exists(e4)) return e4;
        }

        // 2. Check Standard Windows Standalone VOICEVOX installation paths
        // NOTE: Must prioritize 'run.exe' inside 'vv-engine' or 'voicevox_engine' subfolders.
        // DO NOT launch 'voicevox.exe' directly as that is the Electron GUI Desktop app!
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);

        var candidatePaths = new[]
        {
            // Headless Engine Runner paths (Pure HTTP API Backend - NO GUI Window)
            Path.Combine(localAppData, "Programs", "VOICEVOX", "vv-engine", "run.exe"),
            Path.Combine(localAppData, "Programs", "VOICEVOX", "voicevox_engine", "run.exe"),
            Path.Combine(localAppData, "Programs", "VOICEVOX", "run.exe"),
            Path.Combine(localAppData, "VOICEVOX", "vv-engine", "run.exe"),
            Path.Combine(localAppData, "VOICEVOX", "voicevox_engine", "run.exe"),
            Path.Combine(localAppData, "VOICEVOX", "run.exe"),
            Path.Combine(programFiles, "VOICEVOX", "vv-engine", "run.exe"),
            Path.Combine(programFiles, "VOICEVOX", "voicevox_engine", "run.exe"),
            Path.Combine(programFiles, "VOICEVOX", "run.exe"),
            Path.Combine(programFilesX86, "VOICEVOX", "vv-engine", "run.exe"),
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
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
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

        var tempPackage = Path.Combine(
            Path.GetTempPath(),
            $"flama_voicevox_engine_{Guid.NewGuid():N}.vvpp"
        );

        try
        {
            _logger?.LogInformation("Starting VOICEVOX Engine download from {Url}", DOWNLOAD_URL);

            using (var response = await _httpClient.GetAsync(DOWNLOAD_URL, HttpCompletionOption.ResponseHeadersRead, ct))
            {
                response.EnsureSuccessStatusCode();
                var totalBytes = response.Content.Headers.ContentLength ?? -1L;

                using (var contentStream = await response.Content.ReadAsStreamAsync(ct))
                using (var fileStream = new FileStream(tempPackage, FileMode.CreateNew, FileAccess.Write, FileShare.None, 8192, true))
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

            await VerifySha256Async(tempPackage, DOWNLOAD_SHA256, ct);
            _logger?.LogInformation("Extracting VOICEVOX Engine to {TargetDir}", targetDir);
            ZipFile.ExtractToDirectory(tempPackage, targetDir, overwriteFiles: true);

            return true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Failed to download and install VOICEVOX Engine");
            return false;
        }
        finally
        {
            if (File.Exists(tempPackage))
            {
                File.Delete(tempPackage);
            }
        }
    }

    internal static async Task VerifySha256Async(
        string filePath,
        string expectedSha256,
        CancellationToken ct = default
    )
    {
        await using var stream = new FileStream(
            filePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            8192,
            true
        );
        var actualSha256 = Convert.ToHexString(await SHA256.HashDataAsync(stream, ct));
        if (!string.Equals(actualSha256, expectedSha256, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                $"VOICEVOX package SHA-256 mismatch. Expected {expectedSha256}, got {actualSha256}."
            );
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
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
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
