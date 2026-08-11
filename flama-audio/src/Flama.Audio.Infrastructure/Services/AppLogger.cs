using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Flama.Audio.Infrastructure.Services;

public enum LogSeverity
{
    Info,
    Warning,
    Error
}

public record LogEntry(
    DateTime Timestamp,
    LogSeverity Severity,
    string Category,
    string Message,
    string? ExceptionDetails = null
);

public class AppLogStore
{
    private static readonly Lazy<AppLogStore> _instance = new(() => new AppLogStore());
    public static AppLogStore Instance => _instance.Value;

    private readonly List<LogEntry> _entries = new();
    private readonly object _lock = new();
    private readonly string _logFilePath;

    public event Action<LogEntry>? OnLogAdded;

    private AppLogStore()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string logDir = Path.Combine(localAppData, "Flama", "Audio", "logs");
        Directory.CreateDirectory(logDir);

        _logFilePath = Path.Combine(logDir, "flama_audio.log");
        
        // Write session start header to log file
        WriteToFile($"\n========== Session Started at {DateTime.Now:yyyy-MM-dd HH:mm:ss} ==========\n");
    }

    public string LogFilePath => _logFilePath;

    public void AddLog(LogSeverity severity, string category, string message, Exception? exception = null)
    {
        string? exText = exception?.ToString();
        var entry = new LogEntry(DateTime.Now, severity, category, message, exText);

        lock (_lock)
        {
            _entries.Add(entry);
            if (_entries.Count > 1000)
            {
                _entries.RemoveAt(0); // Keep last 1000 logs in memory
            }
        }

        string formatted = FormatSingleEntry(entry);
        WriteToFile(formatted);

        OnLogAdded?.Invoke(entry);
    }

    public IReadOnlyList<LogEntry> GetLogs(LogSeverity? minSeverity = null)
    {
        lock (_lock)
        {
            if (minSeverity == null) return _entries.ToArray();
            return _entries.FindAll(e => e.Severity >= minSeverity.Value);
        }
    }

    public string GetFormattedLogs(LogSeverity? minSeverity = null)
    {
        var sb = new StringBuilder();
        var logs = GetLogs(minSeverity);

        foreach (var log in logs)
        {
            sb.AppendLine(FormatSingleEntry(log));
        }

        return sb.ToString();
    }

    public string GetFormattedErrorsOnly()
    {
        return GetFormattedLogs(LogSeverity.Error);
    }

    public void Clear()
    {
        lock (_lock)
        {
            _entries.Clear();
        }
    }

    private static string FormatSingleEntry(LogEntry entry)
    {
        string levelStr = entry.Severity switch
        {
            LogSeverity.Error => "[ERROR]",
            LogSeverity.Warning => "[WARN ]",
            _ => "[INFO ]"
        };

        var sb = new StringBuilder();
        sb.Append($"[{entry.Timestamp:yyyy-MM-dd HH:mm:ss.fff}] {levelStr} [{entry.Category}] {entry.Message}");
        if (!string.IsNullOrEmpty(entry.ExceptionDetails))
        {
            sb.AppendLine();
            sb.Append($"   Exception Details:\n{entry.ExceptionDetails}");
        }
        return sb.ToString();
    }

    private void WriteToFile(string text)
    {
        try
        {
            File.AppendAllText(_logFilePath, text + "\n");
        }
        catch
        {
            // Ignore file write errors during logging
        }
    }
}
