import 'package:flutter/material.dart';

class AppColors {
  // Primary Green Colors (neon)
  static const Color primaryGreen = Color(0xFF00FF88);
  static const Color mediumGreen = Color(0xFF00D977);
  static const Color darkGreen = Color(0xFF00AA55);
  
  // Background Colors (dark futuristic)
  static const Color background = Color(0xFF0A0A1A);
  static const Color surface = Color(0xFF0F1B2D);
  static const Color cardBackground = Color(0xFF12192B);
  
  // Text Colors (light for dark theme)
  static const Color textPrimary = Color(0xFFE8E8E8);
  static const Color textSecondary = Color(0xFFCCCCCC);
  static const Color textTertiary = Color(0xFFBBBBBB);
  static const Color textLight = Color(0x8AFFFFFF); // white54
  
  // Status Colors
  static const Color error = Color(0xFFFF4444);
  static const Color success = Color(0xFF00FF88);
  static const Color warning = Color(0xFFFFA500);
  
  // Border Colors
  static const Color borderLight = Color(0xFF1E2D42);
  
  // Gradients
  static const List<Color> primaryGradient = [
    Color(0xFF00FF88),
    Color(0xFF00AA55),
  ];
  
  static const List<Color> mediumGradient = [
    Color(0xFF00FF88),
    Color(0xFF00D977),
  ];

  // Dark glassmorphism helpers
  static Color get glassBackground => Colors.white.withOpacity(0.05);
  static Color get glassBorder => Colors.white.withOpacity(0.08);
}
