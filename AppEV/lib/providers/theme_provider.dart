import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/app_colors.dart';

/// Light, dark, or follow the device.
///
/// Was a stub returning dark unconditionally. The palette now switches with
/// it, so this has to run before the first frame of a new theme: see
/// [_sync], which pushes the choice into [AppColors].
class ThemeProvider extends ChangeNotifier {
  static const _key = 'theme_mode';

  ThemeMode _mode = ThemeMode.dark;
  Brightness _platform = Brightness.dark;

  ThemeProvider() {
    _load();
  }

  ThemeMode get themeMode => _mode;

  /// The brightness actually in effect, with [ThemeMode.system] resolved
  /// against the device setting.
  Brightness get brightness {
    switch (_mode) {
      case ThemeMode.light:
        return Brightness.light;
      case ThemeMode.dark:
        return Brightness.dark;
      case ThemeMode.system:
        return _platform;
    }
  }

  bool get isDark => brightness == Brightness.dark;

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_key);
      if (saved == 'light') {
        _mode = ThemeMode.light;
      } else if (saved == 'system') {
        _mode = ThemeMode.system;
      } else {
        _mode = ThemeMode.dark;
      }
    } catch (_) {
      // A browser with site data blocked, or a first run. Dark is the default
      // the app shipped with, so falling back to it changes nothing.
    }
    _sync();
    notifyListeners();
  }

  Future<void> setMode(ThemeMode mode) async {
    if (mode == _mode) return;
    _mode = mode;
    _sync();
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _key,
        mode == ThemeMode.light
            ? 'light'
            : mode == ThemeMode.system
                ? 'system'
                : 'dark',
      );
    } catch (_) {
      // Persisting is a convenience; the session still works without it.
    }
  }

  /// Straight swap between the two explicit modes, for the switch in Settings.
  Future<void> toggle() =>
      setMode(isDark ? ThemeMode.light : ThemeMode.dark);

  /// Keeps [ThemeMode.system] honest when the device flips light/dark while
  /// the app is open.
  void updatePlatformBrightness(Brightness b) {
    if (b == _platform) return;
    _platform = b;
    if (_mode == ThemeMode.system) {
      _sync();
      notifyListeners();
    }
  }

  void _sync() => AppColors.apply(brightness);
}
