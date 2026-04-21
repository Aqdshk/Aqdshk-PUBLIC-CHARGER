import 'package:flutter/material.dart';

// Kept as a stub so existing Consumer<ThemeProvider> references compile.
// App is dark-only — no toggle functionality.
class ThemeProvider extends ChangeNotifier {
  bool get isDark => true;
  ThemeMode get themeMode => ThemeMode.dark;
}
