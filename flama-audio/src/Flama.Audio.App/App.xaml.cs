using System;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using Flama.Audio.Api;
using Flama.Audio.Api.Middlewares;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Engine.Voicevox;
using Flama.Audio.Engine.Kokoro;
using Flama.Audio.Engine.EdgeTts;
using Flama.Audio.Infrastructure.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Flama.Audio.App;

public partial class App : Application
{
    private static Mutex? _singleInstanceMutex;
    private WebApplication? _webApp;
    private IPairingManager? _pairingManager;

    protected override void OnStartup(StartupEventArgs e)
    {
        const string mutexName = "Global\\FlamaAudioAppSingleInstanceMutex";
        _singleInstanceMutex = new Mutex(true, mutexName, out bool isNewInstance);

        if (!isNewInstance)
        {
            MessageBox.Show(
                "Flama Audio Service đang chạy sẵn trên máy tính của bạn (kiểm tra thanh Taskbar / khay hệ thống).",
                "Flama Audio đã mở",
                MessageBoxButton.OK,
                MessageBoxImage.Information
            );
            Shutdown();
            return;
        }

        // Global Unhandled Exception Handling for easy debugging
        AppDomain.CurrentDomain.UnhandledException += (s, ev) =>
        {
            if (ev.ExceptionObject is Exception ex)
            {
                AppLogStore.Instance.AddLog(LogSeverity.Error, "AppDomain", "Unhandled Exception", ex);
            }
        };

        DispatcherUnhandledException += (s, ev) =>
        {
            AppLogStore.Instance.AddLog(LogSeverity.Error, "WPFDispatcher", "Unhandled UI Exception", ev.Exception);
            ev.Handled = true; // Prevent crash, log for easy copying
        };

        base.OnStartup(e);

        try
        {
            var builder = WebApplication.CreateBuilder();

            builder.Logging.ClearProviders();
            builder.Logging.AddProvider(new FlamaLoggerProvider());

            builder.WebHost.ConfigureKestrel(options =>
            {
                options.Listen(IPAddress.Loopback, 4791);
            });

            builder.Services.AddHttpClient();
            builder.Services.AddSingleton<IPairingManager, PairingManager>();
            builder.Services.AddSingleton<ITtsEngineAdapter, VoicevoxEngineAdapter>();
            builder.Services.AddSingleton<ITtsEngineAdapter, KokoroEngineAdapter>();
            builder.Services.AddSingleton<ITtsEngineAdapter, EdgeTtsEngineAdapter>();
            builder.Services.AddSingleton<IEngineRouter, EngineRouter>();
            builder.Services.AddSingleton<VoicevoxEngineInstaller>();
            builder.Services.AddSingleton<KokoroEngineInstaller>();
            builder.Services.AddSingleton<ChinesePackInstaller>();

            _webApp = builder.Build();
            _pairingManager = _webApp.Services.GetService<IPairingManager>();
            var engineRouter = _webApp.Services.GetRequiredService<IEngineRouter>();
            var voicevoxInstaller = _webApp.Services.GetRequiredService<VoicevoxEngineInstaller>();
            var kokoroInstaller = _webApp.Services.GetRequiredService<KokoroEngineInstaller>();
            var chinesePackInstaller = _webApp.Services.GetRequiredService<ChinesePackInstaller>();
            _webApp.UseMiddleware<CorsAndPnaMiddleware>();
            _webApp.UseMiddleware<PairingAuthMiddleware>();
            _webApp.MapFlamaAudioEndpoints();

            _ = _webApp.RunAsync();

            var mainWindow = new MainWindow(_pairingManager!, engineRouter, voicevoxInstaller, kokoroInstaller, chinesePackInstaller);

            _ = Task.Run(async () =>
            {
                if (voicevoxInstaller != null)
                {
                    await voicevoxInstaller.TryAutoLaunchEngineAsync();
                    Dispatcher.Invoke(() => mainWindow.RefreshData());
                }
            });

            mainWindow.Show();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể khởi chạy Flama Audio Service: {ex.Message}", "Lỗi khởi động", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        try
        {
            var installer = _webApp?.Services.GetService<VoicevoxEngineInstaller>();
            installer?.StopEngineProcess();
        }
        catch {}

        if (_webApp != null)
        {
            await _webApp.StopAsync();
            await _webApp.DisposeAsync();
        }
        if (_singleInstanceMutex != null)
        {
            try
            {
                _singleInstanceMutex.ReleaseMutex();
            }
            catch {}
            _singleInstanceMutex.Dispose();
        }
        base.OnExit(e);
    }
}
