using System;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using Flama.Audio.Api;
using Flama.Audio.Api.Middlewares;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Engine.Voicevox;
using Flama.Audio.Infrastructure.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;

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

        base.OnStartup(e);

        try
        {
            var builder = WebApplication.CreateBuilder();

            builder.WebHost.ConfigureKestrel(options =>
            {
                options.Listen(IPAddress.Loopback, 4791);
            });

            builder.Services.AddHttpClient();
            builder.Services.AddSingleton<IPairingManager, PairingManager>();
            builder.Services.AddSingleton<ITtsEngineAdapter, VoicevoxEngineAdapter>();
            builder.Services.AddSingleton<IEngineRouter, EngineRouter>();
            builder.Services.AddSingleton<VoicevoxEngineInstaller>();

            _webApp = builder.Build();
            _pairingManager = _webApp.Services.GetService<IPairingManager>();
            var installer = _webApp.Services.GetService<VoicevoxEngineInstaller>();
            var voicevoxAdapter = _webApp.Services.GetService<ITtsEngineAdapter>();

            _webApp.UseMiddleware<CorsAndPnaMiddleware>();
            _webApp.UseMiddleware<PairingAuthMiddleware>();
            _webApp.MapFlamaAudioEndpoints();

            _ = _webApp.RunAsync();

            var mainWindow = new MainWindow(_pairingManager!, installer!, voicevoxAdapter!);

            _ = Task.Run(async () =>
            {
                if (installer != null)
                {
                    await installer.TryAutoLaunchEngineAsync();
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
