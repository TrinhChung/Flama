using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Media;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Flama.Audio.Core.Interfaces;
using Flama.Audio.Core.Models;
using Flama.Audio.Infrastructure.Services;

namespace Flama.Audio.App;

public partial class MainWindow : Window
{
    private readonly IPairingManager? _pairingManager;
    private readonly IEngineRouter? _engineRouter;
    private readonly VoicevoxEngineInstaller? _voicevoxInstaller;
    private readonly KokoroEngineInstaller? _kokoroInstaller;

    private string _currentDetailEngineId = "voicevox";
    private bool _isPopulatingLanguages = false;

    public MainWindow()
    {
        InitializeComponent();
    }

    public MainWindow(
        IPairingManager pairingManager,
        IEngineRouter engineRouter,
        VoicevoxEngineInstaller voicevoxInstaller,
        KokoroEngineInstaller kokoroInstaller) : this()
    {
        _pairingManager = pairingManager;
        _engineRouter = engineRouter;
        _voicevoxInstaller = voicevoxInstaller;
        _kokoroInstaller = kokoroInstaller;

        if (_pairingManager != null)
        {
            _pairingManager.OnPairingRequested += (s, e) =>
            {
                Dispatcher.Invoke(() =>
                {
                    RefreshData();
                    if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;
                    Activate();
                });
            };
        }

        // Live log streaming to LogOutputTextBox
        AppLogStore.Instance.OnLogAdded += entry =>
        {
            Dispatcher.Invoke(() =>
            {
                if (ViewLogs.Visibility == Visibility.Visible)
                {
                    RefreshLogDisplay();
                }
            });
        };

        ShowInstalledView();
        RefreshData();
    }

    // --- NAVIGATION LOGIC ---

    private void OnNavInstalledClicked(object sender, RoutedEventArgs e) => ShowInstalledView();
    private void OnNavUninstalledClicked(object sender, RoutedEventArgs e) => ShowUninstalledView();
    private void OnNavPairingClicked(object sender, RoutedEventArgs e) => ShowPairingView();
    private void OnNavLogsClicked(object sender, RoutedEventArgs e) => ShowLogsView();
    private void OnBackToListClicked(object sender, RoutedEventArgs e) => ShowInstalledView();

    private void ShowInstalledView()
    {
        ViewInstalledEngines.Visibility = Visibility.Visible;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Quản lý TTS Engines • Các Engine đã sẵn sàng";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavInstalled);
        RefreshData();
    }

    private void ShowUninstalledView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Visible;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Cài đặt TTS Engines mới";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavUninstalled);
        RefreshData();
    }

    private void ShowPairingView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Visible;
        ViewLogs.Visibility = Visibility.Collapsed;

        ViewTitleTextBlock.Text = "Yêu cầu Ghép nối từ Flama Web Client";
        BtnBackToList.Visibility = Visibility.Collapsed;

        HighlightTabButton(BtnNavPairing);
        RefreshData();
    }

    private void ShowLogsView()
    {
        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Collapsed;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;
        ViewLogs.Visibility = Visibility.Visible;

        ViewTitleTextBlock.Text = "Nhật ký Hoạt động & Log Lỗi Service Debug";
        BtnBackToList.Visibility = Visibility.Visible;

        ResetTabButtonHighlights();
        RefreshLogDisplay();
    }

    // --- TOP MENU HANDLERS ---

    private void OnExitClicked(object sender, RoutedEventArgs e)
    {
        Application.Current.Shutdown();
    }

    private void OnOpenWebClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "http://localhost:5173",
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể mở trình duyệt: {ex.Message}", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private void OnAboutClicked(object sender, RoutedEventArgs e)
    {
        MessageBox.Show(
            "Flama Audio Local Service v1.1.0\n\n" +
            "Trợ lý tổng hợp phát âm đa ngôn ngữ cho hệ sinh thái Flama.\n" +
            "• Tiếng Nhật: VOICEVOX Engine (Port 50021)\n" +
            "• Tiếng Anh & Trung: Kokoro-82M Neural Engine (C# Native + ONNX Runtime CPU)\n\n" +
            "Flama G2P\n" +
            "Source Available\n" +
            "Free for non-commercial use under PolyForm Noncommercial 1.0.0.\n" +
            "Commercial use requires a separate Flama license.\n\n" +
            "See the licenses directory for license and third-party notices.\n\n" +
            "Phát triển bởi đội ngũ Flama.",
            "Về Flama Audio",
            MessageBoxButton.OK,
            MessageBoxImage.Information
        );
    }

    private void ShowEngineDetailView(string engineId)
    {
        _currentDetailEngineId = engineId;

        ViewInstalledEngines.Visibility = Visibility.Collapsed;
        ViewEngineDetail.Visibility = Visibility.Visible;
        ViewUninstalledEngines.Visibility = Visibility.Collapsed;
        ViewPairing.Visibility = Visibility.Collapsed;

        BtnBackToList.Visibility = Visibility.Visible;
        ResetTabButtonHighlights();

        if (engineId == "kokoro")
        {
            DetailEngineTitle.Text = "🇺🇸/🌐 Kokoro-82M Neural Engine";
            DetailEngineBadgeText.Text = "Đa Ngôn Ngữ (Multi-Language)";
            DetailEngineBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#EFF6FF"));
            DetailEngineBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#93C5FD"));
            DetailEngineBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1D4ED8"));

            DetailEngineDescription.Text = "Mô hình TTS Kokoro-82M hỗ trợ đa ngôn ngữ offline (Tiếng Anh, Trung, Tây Ban Nha, Pháp, Ý, Bồ Đào Nha...).";
            ViewTitleTextBlock.Text = "Chi tiết Engine & Test Voice > Kokoro-82M (Đa Ngôn Ngữ)";
        }
        else
        {
            DetailEngineTitle.Text = "🇯🇵 VOICEVOX Local Engine";
            DetailEngineBadgeText.Text = "Tiếng Nhật (Japanese)";
            DetailEngineBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFF1E7"));
            DetailEngineBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEA46B"));
            DetailEngineBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));

            DetailEngineDescription.Text = "Bộ tổng hợp phát âm tiếng Nhật VOICEVOX Engine Standalone CPU (Port 50021). Hỗ trợ giọng đọc Zundamon, Metan và hơn 20 nhân vật khác.";
            ViewTitleTextBlock.Text = "Chi tiết Engine & Test Voice > VOICEVOX (Japanese)";
        }

        // Populate Language Selector
        _isPopulatingLanguages = true;
        TestLanguageComboBox.Items.Clear();
        if (engineId == "voicevox")
        {
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇯🇵 Tiếng Nhật (Japanese)", Tag = "ja-JP" });
        }
        else
        {
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇺🇸 Tiếng Anh - Mỹ (English US)", Tag = "en-US" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇬🇧 Tiếng Anh - Anh (English UK)", Tag = "en-GB" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇨🇳 Tiếng Trung (Mandarin Chinese)", Tag = "zh-CN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇪🇸 Tiếng Tây Ban Nha (Spanish)", Tag = "es-ES" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇫🇷 Tiếng Pháp (French)", Tag = "fr-FR" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇮🇳 Tiếng Hindi", Tag = "hi-IN" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇮🇹 Tiếng Ý (Italian)", Tag = "it-IT" });
            TestLanguageComboBox.Items.Add(new ComboBoxItem { Content = "🇧🇷 Tiếng Bồ Đào Nha (Portuguese)", Tag = "pt-BR" });
        }
        _isPopulatingLanguages = false;

        TestLanguageComboBox.SelectedIndex = 0;
    }

    private void HighlightTabButton(Button activeButton)
    {
        ResetTabButtonHighlights();
        activeButton.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFF1E7"));
        activeButton.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEA46B"));
        activeButton.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));
    }

    private void ResetTabButtonHighlights()
    {
        var inactiveBg = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFFFFF"));
        var inactiveBorder = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E9DDD4"));
        var inactiveText = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1F1A17"));

        BtnNavInstalled.Background = inactiveBg;
        BtnNavInstalled.BorderBrush = inactiveBorder;
        BtnNavInstalled.Foreground = inactiveText;

        BtnNavUninstalled.Background = inactiveBg;
        BtnNavUninstalled.BorderBrush = inactiveBorder;
        BtnNavUninstalled.Foreground = inactiveText;

        BtnNavPairing.Background = inactiveBg;
        BtnNavPairing.BorderBrush = inactiveBorder;
        BtnNavPairing.Foreground = inactiveText;
    }

    // --- LOG MANAGEMENT & DEBUGGING ---

    private void RefreshLogDisplay()
    {
        if (LogOutputTextBox == null) return;

        string tag = (LogFilterComboBox?.SelectedItem as ComboBoxItem)?.Tag as string ?? "All";
        LogSeverity? minSeverity = tag switch
        {
            "Error" => LogSeverity.Error,
            "Warning" => LogSeverity.Warning,
            "Info" => LogSeverity.Info,
            _ => null
        };

        string logs = AppLogStore.Instance.GetFormattedLogs(minSeverity);
        LogOutputTextBox.Text = string.IsNullOrEmpty(logs) ? "[Chưa có log nhật ký nào]" : logs;
        LogOutputTextBox.ScrollToEnd();
    }

    private void OnLogFilterChanged(object sender, SelectionChangedEventArgs e)
    {
        RefreshLogDisplay();
    }

    private void OnCopyAllLogsClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string logs = AppLogStore.Instance.GetFormattedLogs();
            if (string.IsNullOrWhiteSpace(logs))
            {
                MessageBox.Show("Hiện chưa có log nào để copy.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            Clipboard.SetText(logs);
            MessageBox.Show("📋 Đã copy toàn bộ Nhật ký & Log vào Clipboard thành công!\nBạn có thể dán (Ctrl+V) để gửi cho đội hỗ trợ.", "Đã Copy Log", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể copy log vào Clipboard: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnCopyErrorLogsClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string errors = AppLogStore.Instance.GetFormattedErrorsOnly();
            if (string.IsNullOrWhiteSpace(errors))
            {
                MessageBox.Show("🎉 Hiện không có log lỗi nào!", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            Clipboard.SetText(errors);
            MessageBox.Show("🚨 Đã copy tất cả Log Lỗi (Errors & Stack Traces) vào Clipboard!", "Đã Copy Log Lỗi", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể copy log lỗi vào Clipboard: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnOpenLogFolderClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            string logPath = AppLogStore.Instance.LogFilePath;
            string logDir = Path.GetDirectoryName(logPath) ?? "";
            if (Directory.Exists(logDir))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = logDir,
                    UseShellExecute = true
                });
            }
            else
            {
                MessageBox.Show($"Thư mục log chưa được tạo tại: {logDir}", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể mở thư mục log: {ex.Message}", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnClearLogsClicked(object sender, RoutedEventArgs e)
    {
        AppLogStore.Instance.Clear();
        RefreshLogDisplay();
    }

    // --- ENGINE ACTIONS & VOICE TESTING ---

    private void OnOpenEngineDetailClicked(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string engineId)
        {
            ShowEngineDetailView(engineId);
        }
    }

    private async void OnTestLanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_isPopulatingLanguages) return;

        var selectedItem = TestLanguageComboBox.SelectedItem as ComboBoxItem;
        var langTag = selectedItem?.Tag as string;
        if (string.IsNullOrEmpty(langTag)) return;

        // 1. Update Sample Text corresponding to language
        UpdateSampleText(langTag);

        // 2. Populate Voice Selector filtered by language tag
        await PopulateVoiceSelectorAsync(_currentDetailEngineId, langTag);
    }

    private void UpdateSampleText(string langTag)
    {
        TestSampleTextBox.Text = langTag switch
        {
            "ja-JP" => "こんにちは！FLAMA AUDIOへようこそ！",
            "en-US" => "Hello, welcome to Flama Audio US English local TTS!",
            "en-GB" => "Good day, welcome to Flama Audio British English local TTS!",
            "zh-CN" => "你好，欢迎使用 Flama Audio 本地中文语音合成！",
            "es-ES" => "¡Hola! Bienvenido a la síntesis de voz local de Flama Audio.",
            "fr-FR" => "Bonjour, bienvenue sur la synthèse vocale locale de Flama Audio.",
            "hi-IN" => "नमस्ते, फ्लामा ऑडियो लोकल स्पीच सिंथेसिस में आपका स्वागत है।",
            "it-IT" => "Ciao, benvenuto nella sintesi vocale locale di Flama Audio.",
            "pt-BR" => "Olá, bem-vindo à síntese de voz local do Flama Audio.",
            _ => "Hello, welcome to Flama Audio!"
        };
    }

    private async Task PopulateVoiceSelectorAsync(string engineId, string langTag)
    {
        TestVoiceComboBox.Items.Clear();

        var adapter = _engineRouter?.GetAdapter(engineId);
        if (adapter != null)
        {
            try
            {
                var voices = await adapter.ListVoicesAsync();
                var filtered = voices.Where(v => v.Locale.Equals(langTag, StringComparison.OrdinalIgnoreCase)).ToList();

                foreach (var voice in filtered)
                {
                    TestVoiceComboBox.Items.Add(new ComboBoxItem
                    {
                        Content = voice.Name,
                        Tag = voice.VoiceId
                    });
                }

                if (TestVoiceComboBox.Items.Count > 0)
                {
                    TestVoiceComboBox.SelectedIndex = 0;
                }
                else
                {
                    TestVoiceComboBox.Items.Add(new ComboBoxItem { Content = "Không tìm thấy giọng đọc phù hợp", Tag = "" });
                    TestVoiceComboBox.SelectedIndex = 0;
                }
            }
            catch (Exception ex)
            {
                TestVoiceComboBox.Items.Add(new ComboBoxItem { Content = $"Lỗi đọc danh sách giọng: {ex.Message}", Tag = "" });
                TestVoiceComboBox.SelectedIndex = 0;
            }
        }
    }

    private void OnTestSpeedSliderChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (TestSpeedValueText != null)
        {
            TestSpeedValueText.Text = $"{e.NewValue:F1}x";
        }
    }

    private async void OnPlayVoiceTestClicked(object sender, RoutedEventArgs e)
    {
        string text = TestSampleTextBox.Text?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(text))
        {
            MessageBox.Show("Vui lòng nhập văn bản thử nghiệm.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string voiceId = (TestVoiceComboBox.SelectedItem as ComboBoxItem)?.Tag as string ?? "";
        if (string.IsNullOrEmpty(voiceId))
        {
            MessageBox.Show("Vui lòng chọn giọng đọc.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var adapter = _engineRouter?.GetAdapter(_currentDetailEngineId);
        if (adapter == null)
        {
            MessageBox.Show("Engine không khả dụng.", "Lỗi", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        BtnPlayVoiceTest.IsEnabled = false;
        TestStatusText.Text = "⏳ Đang tổng hợp âm thanh...";
        TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E05C07"));

        try
        {
            var selectedItem = TestLanguageComboBox.SelectedItem as ComboBoxItem;
            string langTag = selectedItem?.Tag as string ?? (_currentDetailEngineId == "kokoro" ? "en-US" : "ja-JP");

            double speed = TestSpeedSlider.Value;
            var request = new TtsRequest(
                RequestId: $"test_{DateTime.Now.Ticks}",
                EngineId: _currentDetailEngineId,
                Language: langTag,
                VoiceId: voiceId,
                Text: text,
                Options: new TtsOptions(Speed: speed)
            );

            var result = await Task.Run(() => adapter.SynthesizeAsync(request));

            if (result?.AudioData != null && result.AudioData.Length > 0)
            {
                TestStatusText.Text = "🔊 Đang phát âm thanh...";
                TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#16A34A"));

                await Task.Run(() =>
                {
                    using var ms = new MemoryStream(result.AudioData);
                    using var player = new SoundPlayer(ms);
                    player.PlaySync();
                });

                TestStatusText.Text = "✅ Phát âm xong!";
            }
            else
            {
                TestStatusText.Text = "❌ Không nhận được dữ liệu âm thanh";
                TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DC2626"));
            }
        }
        catch (Exception ex)
        {
            TestStatusText.Text = $"❌ Lỗi: {ex.Message}";
            TestStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DC2626"));
        }
        finally
        {
            BtnPlayVoiceTest.IsEnabled = true;
        }
    }

    // --- INSTALLER ACTIONS ---

    private async void OnInstallKokoroClicked(object sender, RoutedEventArgs e)
    {
        if (_kokoroInstaller == null) return;

        BtnInstallKokoro.IsEnabled = false;
        KokoroInstallProgressBar.Visibility = Visibility.Visible;
        KokoroInstallProgressBar.IsIndeterminate = false;
        KokoroInstallProgressBar.Value = 0;

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                KokoroInstallProgressBar.Value = p;
            });
        });

        try
        {
            var success = await _kokoroInstaller.InstallEngineAsync(progress);
            if (success)
            {
                RefreshData();
                MessageBox.Show("Tải và cài đặt Kokoro-82M English Engine thành công!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
                ShowInstalledView();
            }
            else
            {
                MessageBox.Show("Tải Kokoro Engine thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi cài đặt", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnInstallKokoro.IsEnabled = true;
            KokoroInstallProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnInstallVoicevoxClicked(object sender, RoutedEventArgs e)
    {
        if (_voicevoxInstaller == null) return;

        BtnInstallVoicevox.IsEnabled = false;
        VoicevoxInstallProgressBar.Visibility = Visibility.Visible;
        VoicevoxInstallProgressBar.IsIndeterminate = false;
        VoicevoxInstallProgressBar.Value = 0;

        var progress = new Progress<double>(p =>
        {
            Dispatcher.Invoke(() =>
            {
                VoicevoxInstallProgressBar.Value = p;
            });
        });

        try
        {
            var success = await _voicevoxInstaller.InstallEngineAsync(progress);
            if (success)
            {
                VoicevoxInstallProgressBar.IsIndeterminate = true;
                _voicevoxInstaller.LaunchEngineProcess();

                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã tải & khởi chạy VOICEVOX Engine thành công!", "Thành công", MessageBoxButton.OK, MessageBoxImage.Information);
                ShowInstalledView();
            }
            else
            {
                MessageBox.Show("Tải VOICEVOX Engine thất bại. Vui lòng kiểm tra kết nối mạng.", "Lỗi cài đặt", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnInstallVoicevox.IsEnabled = true;
            VoicevoxInstallProgressBar.Visibility = Visibility.Collapsed;
        }
    }

    private async void OnLaunchVoicevoxClicked(object sender, RoutedEventArgs e)
    {
        if (_voicevoxInstaller == null) return;

        BtnLaunchVoicevox.IsEnabled = false;
        try
        {
            var launched = _voicevoxInstaller.LaunchEngineProcess();
            if (launched)
            {
                await Task.Delay(2000);
                RefreshData();
                MessageBox.Show("Đã phát lệnh khởi chạy VOICEVOX Engine (port 50021).", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("Chưa tìm thấy bản VOICEVOX Engine đã cài. Vui lòng bấm tab 'Engine Chưa Cài đặt' để tải về.", "Thông báo", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            BtnLaunchVoicevox.IsEnabled = true;
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
        // 1. Update Pairing List
        if (_pairingManager != null)
        {
            var pending = _pairingManager.ListPairings().Where(p => !p.Approved).ToList();
            PairingListBox.ItemsSource = pending;

            BtnNavPairing.Content = pending.Count > 0
                ? $"🔗 Ghép nối ({pending.Count} chờ)"
                : "🔗 Ghép nối Web Client";
        }

        // 2. Check VOICEVOX Status
        var voicevoxAdapter = _engineRouter?.GetAdapter("voicevox");
        if (voicevoxAdapter != null)
        {
            var health = await voicevoxAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                VoicevoxStatusBadgeText.Text = "🟢 Sẵn sàng";
                VoicevoxStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
                VoicevoxStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
                VoicevoxStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));

                VoicevoxDetailTextBlock.Text = $"VOICEVOX Engine Active (Port 50021 • v{health.Version ?? "0.14.4"})";
                BtnLaunchVoicevox.Visibility = Visibility.Collapsed;
            }
            else
            {
                VoicevoxStatusBadgeText.Text = "🟡 Chưa bật";
                VoicevoxStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FEF3C7"));
                VoicevoxStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#FDE68A"));
                VoicevoxStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#B45309"));

                VoicevoxDetailTextBlock.Text = "VOICEVOX Engine chưa chạy trên Port 50021. Bấm 'Bật Engine' để kích hoạt.";
                BtnLaunchVoicevox.Visibility = Visibility.Visible;
            }
        }

        // 3. Check Kokoro Status
        var kokoroAdapter = _engineRouter?.GetAdapter("kokoro");
        if (kokoroAdapter != null)
        {
            var health = await kokoroAdapter.GetHealthAsync();
            if (health.Status == "ready")
            {
                KokoroStatusBadgeText.Text = "🟢 Sẵn sàng";
                KokoroStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DCFCE7"));
                KokoroStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#86EFAC"));
                KokoroStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803D"));

                KokoroDetailTextBlock.Text = "Neural Engine Kokoro-82M Active (C# Native + ONNX Runtime CPU)";
                KokoroInstallCard.Visibility = Visibility.Collapsed;
            }
            else
            {
                KokoroStatusBadgeText.Text = "⚪ Chưa cài đặt";
                KokoroStatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F3F4F6"));
                KokoroStatusBadge.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E5E7EB"));
                KokoroStatusBadgeText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#4B5563"));

                KokoroDetailTextBlock.Text = "Chưa cài đặt mô hình Kokoro-82M (~120MB). Bấm 'Engine Chưa Cài đặt' để tải về.";
                KokoroInstallCard.Visibility = Visibility.Visible;
            }
        }

        // 4. Update Uninstalled Tab Empty State
        bool isVoicevoxInstalled = _voicevoxInstaller?.IsEngineInstalled() ?? false;
        bool isKokoroInstalled = _kokoroInstaller?.IsEngineInstalled() ?? false;

        VoicevoxInstallCard.Visibility = isVoicevoxInstalled ? Visibility.Collapsed : Visibility.Visible;
        KokoroInstallCard.Visibility = isKokoroInstalled ? Visibility.Collapsed : Visibility.Visible;

        UninstalledEmptyText.Visibility = (isVoicevoxInstalled && isKokoroInstalled)
            ? Visibility.Visible
            : Visibility.Collapsed;
    }
}