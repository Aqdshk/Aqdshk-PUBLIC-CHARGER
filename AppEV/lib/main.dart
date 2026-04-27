import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/splash_screen.dart';
import 'providers/auth_provider.dart';
import 'providers/charger_provider.dart';
import 'providers/payment_provider.dart';
import 'providers/session_provider.dart';
import 'providers/locale_provider.dart';
import 'providers/theme_provider.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // ── Immersive status & navigation bars (native only) ──────────────────
  // On web, status bar colour is controlled via meta tags in web/index.html
  // (theme-color + apple-mobile-web-app-status-bar-style). Calling
  // SystemChrome on web can throw in release builds on some platforms.
  if (!kIsWeb) {
    SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,   // Android: white icons
      statusBarBrightness: Brightness.dark,        // iOS: white icons
      systemNavigationBarColor: Color(0xFF0A0A1A), // match scaffold bg
      systemNavigationBarIconBrightness: Brightness.light,
    ));
  }

  ErrorWidget.builder = (FlutterErrorDetails details) {
    // Log full error to console for debugging
    // ignore: avoid_print
    print('!!! FLUTTER ERROR: ${details.exception}');
    // ignore: avoid_print
    print('!!! STACK: ${details.stack}');
    return Container(
      color: const Color(0xFF0A0A1A),
      padding: const EdgeInsets.all(24),
      alignment: Alignment.center,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: Colors.orange, size: 48),
            const SizedBox(height: 12),
            const Text('Something went wrong',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text('${details.exception}',
                style: const TextStyle(color: Colors.white70, fontSize: 12),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  };
  runApp(const MyApp());
}

// ── Shared page transition (Cupertino slide everywhere) ──
const _pageTransitions = PageTransitionsTheme(
  builders: {
    TargetPlatform.android : CupertinoPageTransitionsBuilder(),
    TargetPlatform.iOS     : CupertinoPageTransitionsBuilder(),
    TargetPlatform.linux   : CupertinoPageTransitionsBuilder(),
    TargetPlatform.macOS   : CupertinoPageTransitionsBuilder(),
    TargetPlatform.windows : CupertinoPageTransitionsBuilder(),
    TargetPlatform.fuchsia : CupertinoPageTransitionsBuilder(),
  },
);

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // ── DARK theme ──────────────────────────────────────────────────────────
  static ThemeData _darkTheme() => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: const Color(0xFF0A0A1A),
    primaryColor: const Color(0xFF00FF88),
    fontFamily: GoogleFonts.rajdhani().fontFamily,
    pageTransitionsTheme: _pageTransitions,
    colorScheme: const ColorScheme.dark(
      primary   : Color(0xFF00FF88),
      secondary : Color(0xFF00D977),
      tertiary  : Color(0xFF00AA55),
      surface   : Color(0xFF0F1B2D),
      error     : Color(0xFFFF4444),
      onPrimary   : Color(0xFF0A0A1A),
      onSecondary : Color(0xFF0A0A1A),
      onSurface   : Color(0xFFE8E8E8),
      onError     : Colors.white,
    ),
    appBarTheme: AppBarTheme(
      centerTitle : true,
      elevation   : 0,
      backgroundColor : Colors.transparent,
      foregroundColor : const Color(0xFF00FF88),
      titleTextStyle  : GoogleFonts.rajdhani(
        color: const Color(0xFF00FF88), fontSize: 22,
        fontWeight: FontWeight.bold, letterSpacing: 1.2,
      ),
    ),
    cardTheme: CardThemeData(
      color: const Color(0xFF12192B),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFF1E2D42), width: 1),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: const Color(0xFF12192B),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: Color(0xFF1E2D42), width: 1),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Color(0xFF12192B),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor : const Color(0xFF00FF88),
        foregroundColor : const Color(0xFF0A0A1A),
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: GoogleFonts.rajdhani(
          fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1,
        ),
      ),
    ),
    textTheme: GoogleFonts.rajdhaniTextTheme(const TextTheme(
      displayLarge  : TextStyle(color: Color(0xFF00FF88), fontSize: 32, fontWeight: FontWeight.bold, letterSpacing: 1.5),
      displayMedium : TextStyle(color: Color(0xFFE8E8E8), fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: 1),
      titleLarge    : TextStyle(color: Color(0xFFE8E8E8), fontSize: 20, fontWeight: FontWeight.w600, letterSpacing: 0.5),
      bodyLarge     : TextStyle(color: Color(0xFFE8E8E8), fontSize: 16),
      bodyMedium    : TextStyle(color: Color(0xFFBBBBBB), fontSize: 14),
    )),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF0F1B2D),
      labelStyle: const TextStyle(color: Color(0xFFBBBBBB)),
      hintStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
      border         : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF1E2D42))),
      enabledBorder  : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF1E2D42))),
      focusedBorder  : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF00FF88))),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor   : const Color(0xFF12192B),
      contentTextStyle  : const TextStyle(color: Color(0xFFE8E8E8)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      behavior: SnackBarBehavior.floating,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? const Color(0xFF00FF88) : const Color(0xFF4A5570)),
      trackColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? const Color(0xFF00FF88).withOpacity(0.3) : const Color(0xFF1E2D42)),
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor  : const Color(0xFF00FF88),
      inactiveTrackColor: const Color(0xFF1E2D42),
      thumbColor  : const Color(0xFF00FF88),
      overlayColor: const Color(0xFF00FF88).withOpacity(0.2),
    ),
  );

  // ── NAVY theme (user-facing "light" / blue variant) ────────────────────
  // Navy blue backgrounds — same green accents & white text as dark mode.
  // Using Brightness.dark internally so Material widgets keep dark styling.
  static ThemeData _lightTheme() => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: const Color(0xFF0D1F35),
    primaryColor: const Color(0xFF00FF88),
    fontFamily: GoogleFonts.rajdhani().fontFamily,
    pageTransitionsTheme: _pageTransitions,
    colorScheme: const ColorScheme.dark(
      primary   : Color(0xFF00FF88),
      secondary : Color(0xFF00D977),
      tertiary  : Color(0xFF00AA55),
      surface   : Color(0xFF142840),
      error     : Color(0xFFFF4444),
      onPrimary   : Color(0xFF0A0A1A),
      onSecondary : Color(0xFF0A0A1A),
      onSurface   : Color(0xFFE8E8E8),
      onError     : Colors.white,
    ),
    appBarTheme: AppBarTheme(
      centerTitle : true,
      elevation   : 0,
      backgroundColor : Colors.transparent,
      foregroundColor : const Color(0xFF00FF88),
      titleTextStyle  : GoogleFonts.rajdhani(
        color: const Color(0xFF00FF88), fontSize: 22,
        fontWeight: FontWeight.bold, letterSpacing: 1.2,
      ),
    ),
    cardTheme: CardThemeData(
      color: const Color(0xFF1A3350),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFF284868), width: 1),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: const Color(0xFF1A3350),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: Color(0xFF284868), width: 1),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Color(0xFF1A3350),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor : const Color(0xFF00FF88),
        foregroundColor : const Color(0xFF0A0A1A),
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: GoogleFonts.rajdhani(
          fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1,
        ),
      ),
    ),
    textTheme: GoogleFonts.rajdhaniTextTheme(const TextTheme(
      displayLarge  : TextStyle(color: Color(0xFF00FF88), fontSize: 32, fontWeight: FontWeight.bold, letterSpacing: 1.5),
      displayMedium : TextStyle(color: Color(0xFFE8E8E8), fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: 1),
      titleLarge    : TextStyle(color: Color(0xFFE8E8E8), fontSize: 20, fontWeight: FontWeight.w600, letterSpacing: 0.5),
      bodyLarge     : TextStyle(color: Color(0xFFE8E8E8), fontSize: 16),
      bodyMedium    : TextStyle(color: Color(0xFFCCCCCC), fontSize: 14),
    )),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF142840),
      labelStyle: const TextStyle(color: Color(0xFFBBBBBB)),
      hintStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
      border         : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF284868))),
      enabledBorder  : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF284868))),
      focusedBorder  : OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF00FF88))),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor   : const Color(0xFF1A3350),
      contentTextStyle  : const TextStyle(color: Color(0xFFE8E8E8)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      behavior: SnackBarBehavior.floating,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? const Color(0xFF00FF88) : const Color(0xFF4A5570)),
      trackColor: WidgetStateProperty.resolveWith((s) =>
          s.contains(WidgetState.selected) ? const Color(0xFF00FF88).withOpacity(0.3) : const Color(0xFF284868)),
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor  : const Color(0xFF00FF88),
      inactiveTrackColor: const Color(0xFF284868),
      thumbColor  : const Color(0xFF00FF88),
      overlayColor: const Color(0xFF00FF88).withOpacity(0.2),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChargerProvider()),
        ChangeNotifierProvider(create: (_) => PaymentProvider()),
        ChangeNotifierProvider(create: (_) => SessionProvider()),
        ChangeNotifierProvider(create: (_) => LocaleProvider()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
      ],
      child: Consumer2<LocaleProvider, ThemeProvider>(
        builder: (context, localeProvider, themeProvider, child) => MaterialApp(
          title: 'PlagSini EV',
          debugShowCheckedModeBanner: false,
          locale: localeProvider.locale,
          supportedLocales: const [Locale('en'), Locale('ms')],
          localizationsDelegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          theme     : _darkTheme(),
          darkTheme : _darkTheme(),
          themeMode : ThemeMode.dark,
          home: const SplashScreen(),
        ),
      ),
    );
  }
}
