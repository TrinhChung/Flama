using System;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Infrastructure.Services;

namespace Flama.Audio.App;

public partial class MainWindow : Window
{
    private readonly IPairingManager? _pairingManager;
    private readonly VoicevoxEngineInstaller? _installer;
    private readonly ITtsEngineAdapter? _voicevoxAdapter;

    public MainWindow()
    {
        InitializeComponent();
    }

    public MainWindow(IPairingManager pairingManager, VoicevoxEngineInstaller installer, ITtsEngineAdapter voicevoxAdapter) : this()
    {
        _pairingManager = pairingManager;
        _installer = installer;
        _voicevoxAdapter = voicevoxAdapter;

        _pairingManager.OnPairingRequested += (s, e) =>
        {
            Dispatcher.Invoke(() =>
            {
                RefreshData();
                if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;
                Activate();
            });
        };
        RefreshData();
    }

    private async void OnInstallEngineClicked(object sender, RoutedEventArgs e)
    {
        if (_installer == null) return;

        BtnInstallEngine.IsEnabled = false;
        BtnLaunchEngine.IsEnabled = false;
        EngineProgressBar.Visibility = Visibility.Visible;
        EngineProgressBar.IsIndeterminate = false;
        EngineProgressBar.Value = 0;

        EngineStatusTextBlock.Text = "⏳ Đang kết nối tải VOICEVOX Engine package...";
        EngineStatusTextBlock.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#2563EB"));

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                EngineProgressBar.Value = p;
                EngineStatusTextBlock.Text = $"⏳ Đang tải VOICEVOX Engine... {p:F1}%";
            });
        });

        try
        {
            var success = await _installer.InstallEngineAsync(progress);
            if (success)
            {
                EngineStatusTextBlock.Text = "⏳ Đang giải nén & khởi chạy VOICEVOX Engine...";
                EngineProgressBar.IsIndeterminate = true;
                _installer.LaunchEngineProcess();

                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã tải & khởi chạy VOICEVOX Engine thành công!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("Tải VOICEVOX Engine thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi tải Engine", MessageBoxButton.OK, MessageBoxImage.Warning);
                RefreshData();
            }
        }
        finally
        {
            BtnInstallEngine.IsEnabled = true;
            BtnLaunchEngine.IsEnabled = true;
            EngineProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnLaunchEngineClicked(object sender, RoutedEventArgs e)
    {
        if (_installer == null) return;

        BtnInstallEngine.IsEnabled = false;
        BtnLaunchEngine.IsEnabled = false;
        EngineProgressBar.Visibility = Visibility.Visible;
        EngineProgressBar.IsIndeterminate = true;
        EngineStatusTextBlock.Text = "⏳ Đang quét & khởi chạy VOICEVOX Engine local...";

        try
        {
            var launched = _installer.LaunchEngineProcess();
            if (launched)
            {
                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã phát lệnh khởi chạy VOICEVOX Engine (port 50021).", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("Chưa tìm thấy bản VOICEVOX Engine đã cài. Vui lòng bấm nút 'Tải & Tự động cài VOICEVOX Engine'.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Warning);
                RefreshData();
            }
        }
        finally
        {
            BtnInstallEngine.IsEnabled = true;
            BtnLaunchEngine.IsEnabled = true;
            EngineProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private void OnRefreshClicked(object sender, RoutedEventArgs e)
    {
        RefreshData();
    }

    private async void OnApprovePairingClicked(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.Tag is string pairingId && _pairingManager != null)
        {
            await _pairingManager.ApprovePairingAsync(pairingId);
            RefreshData();
            MessageBox.Show("Đã phê duyệt yêu cầu ghép nối!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    public async void RefreshData()
    {
        if (_pairingManager == null) return;
        var pending = _pairingManager.ListPairings().Where(p => !p.Approved).ToList();
        PairingListBox.ItemsSource = pending;

        if (_voicevoxAdapter != null)
        {
            var health = await _voicevoxAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                EngineStatusTextBlock.Text = $"🟢 Sẵn sàng (Port 50021 • v{health.Version ?? "0.14.4"})";
                EngineStatusTextBlock.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#4ADE80"));
            }
            else
            {
                EngineStatusTextBlock.Text = "🟡 Chưa bật Engine (Port 50021 offline)";
                EngineStatusTextBlock.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F59E0B"));
            }
        }
    }
}