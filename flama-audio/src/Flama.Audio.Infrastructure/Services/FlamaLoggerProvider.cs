using System;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.Infrastructure.Services;

public class FlamaLoggerProvider : ILoggerProvider
{
    public ILogger CreateLogger(string categoryName)
    {
        return new FlamaLogger(categoryName);
    }

    public void Dispose() { }
}

public class FlamaLogger : ILogger
{
    private readonly string _categoryName;

    public FlamaLogger(string categoryName)
    {
        // Shorten category name for readable log output (e.g. Flama.Audio.Engine.Kokoro.KokoroOnnxEngine -> KokoroOnnxEngine)
        int lastDot = categoryName.LastIndexOf('.');
        _categoryName = lastDot >= 0 ? categoryName[(lastDot + 1)..] : categoryName;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

    public bool IsEnabled(LogLevel logLevel) => logLevel != LogLevel.None;

    public void Log<TState>(
        LogLevel logLevel,
        EventId eventId,
        TState state,
        Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        string message = formatter(state, exception);
        if (string.IsNullOrEmpty(message) && exception == null) return;

        LogSeverity severity = logLevel switch
        {
            LogLevel.Error or LogLevel.Critical => LogSeverity.Error,
            LogLevel.Warning => LogSeverity.Warning,
            _ => LogSeverity.Info
        };

        AppLogStore.Instance.AddLog(severity, _categoryName, message, exception);
    }
}
