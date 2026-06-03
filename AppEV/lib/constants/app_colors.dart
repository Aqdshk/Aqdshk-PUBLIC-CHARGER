import 'package:flutter/material.dart';

class AppColors {
  // ── Brand greens — always the same ──
  static const Color primaryGreen = Color(0xFF00FF88);
  static const Color mediumGreen  = Color(0xFF00D977);
  static const Color darkGreen    = Color(0xFF00AA55);

  // ── Premium accent (Tesla-style warm gold) — use sparingly: brand mark,
  // section bullets, dividers. NOT for primary CTAs (those stay green).
  static const Color premiumGold       = Color(0xFFC9A461);
  static const Color premiumGoldMuted  = Color(0xFF8A7544);

  // ── Backgrounds — near-black, slightly cooler than pure 0,0,0 ──
  static const Color background     = Color(0xFF0A0B0D);
  static const Color surface        = Color(0xFF101216);
  static const Color cardBackground = Color(0xFF13151A);

  // ── Text ──
  static const Color textPrimary   = Color(0xFFE8E8E8);
  static const Color textSecondary = Color(0xFFCCCCCC);
  static const Color textTertiary  = Color(0xFFBBBBBB);
  static       Color get textLight => Colors.white.withOpacity(0.54);

  // ── Status colours ──
  static const Color error   = Color(0xFFFF4444);
  static const Color success = Color(0xFF00FF88);
  static const Color warning = Color(0xFFFFA500);

  // ── Border — hairline at low opacity ──
  static Color get borderHairline => Colors.white.withOpacity(0.06);
  static const Color borderLight  = Color(0xFF1E2D42);

  // ── Accent ──
  static const Color accentGreen = primaryGreen;

  // ── Gradients ──
  static const List<Color> primaryGradient = [Color(0xFF00FF88), Color(0xFF00AA55)];
  static const List<Color> mediumGradient  = [Color(0xFF00FF88), Color(0xFF00D977)];

  // ── Glassmorphism ──
  static Color get glassBackground => Colors.white.withOpacity(0.05);
  static Color get glassBorder     => Colors.white.withOpacity(0.08);
}
