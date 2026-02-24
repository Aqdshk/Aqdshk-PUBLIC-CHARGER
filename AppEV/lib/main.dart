import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/splash_screen.dart';
import 'providers/auth_provider.dart';
import 'providers/charger_provider.dart';
import 'providers/payment_provider.dart';
import 'providers/session_provider.dart';

void main() {
  // Prevent uncaught errors from crashing the app (e.g. Google Maps API not loaded)
  ErrorWidget.builder = (FlutterErrorDetails details) {
    return Container(
      alignment: Alignment.center,
      child: Text(
        'Something went wrong',
        style: TextStyle(color: Colors.white54, fontSize: 14),
        textAlign: TextAlign.center,
      ),
    );
  };
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChargerProvider()),
        ChangeNotifierProvider(create: (_) => PaymentProvider()),
        ChangeNotifierProvider(create: (_) => SessionProvider()),
      ],
      child: MaterialApp(
        title: 'EV Charging App',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0A0A1A),
          primaryColor: const Color(0xFF00FF88),
          fontFamily: GoogleFonts.rajdhani().fontFamily,
          // Slide transition for all page navigations (like iOS)
          pageTransitionsTheme: const PageTransitionsTheme(
            builders: {
              TargetPlatform.android: CupertinoPageTransitionsBuilder(),
              TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
              TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
              TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
              TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
              TargetPlatform.fuchsia: CupertinoPageTransitionsBuilder(),
            },
          ),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF00FF88),
            secondary: Color(0xFF00D977),
            tertiary: Color(0xFF00AA55),
            surface: Color(0xFF0F1B2D),
            background: Color(0xFF0A0A1A),
            error: Color(0xFFFF4444),
            onPrimary: Color(0xFF0A0A1A),
            onSecondary: Color(0xFF0A0A1A),
            onSurface: Color(0xFFE8E8E8),
            onBackground: Color(0xFFE8E8E8),
            onError: Colors.white,
          ),
          appBarTheme: AppBarTheme(
            centerTitle: true,
            elevation: 0,
            backgroundColor: Colors.transparent,
            foregroundColor: const Color(0xFF00FF88),
            titleTextStyle: GoogleFonts.rajdhani(
              color: const Color(0xFF00FF88),
              fontSize: 22,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
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
              backgroundColor: const Color(0xFF00FF88),
              foregroundColor: const Color(0xFF0A0A1A),
              elevation: 0,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              textStyle: GoogleFonts.rajdhani(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
              ),
            ),
          ),
          textTheme: GoogleFonts.rajdhaniTextTheme(const TextTheme(
            displayLarge: TextStyle(
              color: Color(0xFF00FF88),
              fontSize: 32,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.5,
            ),
            displayMedium: TextStyle(
              color: Color(0xFFE8E8E8),
              fontSize: 24,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
            titleLarge: TextStyle(
              color: Color(0xFFE8E8E8),
              fontSize: 20,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
            bodyLarge: TextStyle(
              color: Color(0xFFE8E8E8),
              fontSize: 16,
            ),
            bodyMedium: TextStyle(
              color: Color(0xFFBBBBBB),
              fontSize: 14,
            ),
          )),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: const Color(0xFF0F1B2D),
            labelStyle: const TextStyle(color: Color(0xFFBBBBBB)),
            hintStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xFF1E2D42)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xFF1E2D42)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xFF00FF88)),
            ),
          ),
          snackBarTheme: SnackBarThemeData(
            backgroundColor: const Color(0xFF12192B),
            contentTextStyle: const TextStyle(color: Color(0xFFE8E8E8)),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            behavior: SnackBarBehavior.floating,
          ),
          switchTheme: SwitchThemeData(
            thumbColor: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.selected)) return const Color(0xFF00FF88);
              return const Color(0xFF4A5570);
            }),
            trackColor: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.selected)) return const Color(0xFF00FF88).withOpacity(0.3);
              return const Color(0xFF1E2D42);
            }),
          ),
          sliderTheme: SliderThemeData(
            activeTrackColor: const Color(0xFF00FF88),
            inactiveTrackColor: const Color(0xFF1E2D42),
            thumbColor: const Color(0xFF00FF88),
            overlayColor: const Color(0xFF00FF88).withOpacity(0.2),
          ),
        ),
        home: const SplashScreen(),
      ),
    );
  }
}
