import 'package:flutter/material.dart';

/// One palette per brightness, behind the same `AppColors.x` names the app
/// already uses in about 1,300 places.
///
/// Switching by swapping the active palette rather than threading
/// `Theme.of(context)` through every widget keeps the change to this file and
/// the app shell. The cost is that these can no longer be `const`, which is
/// why call sites lost the `const` keyword where they built a colour directly.
@immutable
class _Palette {
  const _Palette({
    required this.primaryGreen,
    required this.mediumGreen,
    required this.darkGreen,
    required this.premiumGold,
    required this.premiumGoldMuted,
    required this.background,
    required this.surface,
    required this.cardBackground,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.textLight,
    required this.error,
    required this.warning,
    required this.borderHairline,
    required this.borderLight,
    required this.glassBackground,
    required this.glassBorder,
  });

  final Color primaryGreen;
  final Color mediumGreen;
  final Color darkGreen;
  final Color premiumGold;
  final Color premiumGoldMuted;
  final Color background;
  final Color surface;
  final Color cardBackground;
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textLight;
  final Color error;
  final Color warning;
  final Color borderHairline;
  final Color borderLight;
  final Color glassBackground;
  final Color glassBorder;
}

const _dark = _Palette(
  primaryGreen: Color(0xFF00FF88),
  mediumGreen: Color(0xFF00D977),
  darkGreen: Color(0xFF00AA55),
  premiumGold: Color(0xFFC9A461),
  premiumGoldMuted: Color(0xFF8A7544),
  background: Color(0xFF0A0B0D),
  surface: Color(0xFF101216),
  cardBackground: Color(0xFF13151A),
  textPrimary: Color(0xFFE8E8E8),
  textSecondary: Color(0xFFCCCCCC),
  textTertiary: Color(0xFFBBBBBB),
  textLight: Color(0x8AFFFFFF),
  error: Color(0xFFFF4444),
  warning: Color(0xFFFFA500),
  borderHairline: Color(0x0FFFFFFF),
  borderLight: Color(0xFF1E2D42),
  glassBackground: Color(0x0DFFFFFF),
  glassBorder: Color(0x14FFFFFF),
);

/// The neon green is deliberately not reused here. #00FF88 on white sits at
/// roughly 1.4:1 contrast, so labels and icons in that colour become
/// unreadable in daylight. Light mode uses a deeper green that keeps the brand
/// hue while passing contrast against white.
const _light = _Palette(
  primaryGreen: Color(0xFF00A65A),
  mediumGreen: Color(0xFF00934F),
  darkGreen: Color(0xFF007A41),
  premiumGold: Color(0xFF8A6D2F),
  premiumGoldMuted: Color(0xFFA8925F),
  background: Color(0xFFF4F6F7),
  surface: Color(0xFFFFFFFF),
  cardBackground: Color(0xFFFFFFFF),
  textPrimary: Color(0xFF14181C),
  textSecondary: Color(0xFF3C464F),
  textTertiary: Color(0xFF667079),
  textLight: Color(0x8A000000),
  error: Color(0xFFD32F2F),
  warning: Color(0xFFB26A00),
  borderHairline: Color(0x14000000),
  borderLight: Color(0xFFDCE3E8),
  glassBackground: Color(0x0A000000),
  glassBorder: Color(0x14000000),
);

class AppColors {
  static _Palette _p = _dark;

  /// Whether the dark palette is active. Widgets that need a different asset
  /// or shadow strength per theme can branch on this.
  static bool get isDark => identical(_p, _dark);

  /// Swap the palette. Called by the app shell before the first frame of a
  /// new theme, so a rebuild picks up the new values.
  static void apply(Brightness brightness) {
    _p = brightness == Brightness.dark ? _dark : _light;
  }

  // ── Brand ──
  static Color get primaryGreen => _p.primaryGreen;
  static Color get mediumGreen => _p.mediumGreen;
  static Color get darkGreen => _p.darkGreen;
  static Color get accentGreen => _p.primaryGreen;
  static Color get success => _p.primaryGreen;

  // ── Premium accent — brand mark, bullets, dividers. Not for primary CTAs.
  static Color get premiumGold => _p.premiumGold;
  static Color get premiumGoldMuted => _p.premiumGoldMuted;

  // ── Backgrounds ──
  static Color get background => _p.background;
  static Color get surface => _p.surface;
  static Color get cardBackground => _p.cardBackground;

  // ── Text ──
  static Color get textPrimary => _p.textPrimary;
  static Color get textSecondary => _p.textSecondary;
  static Color get textTertiary => _p.textTertiary;
  static Color get textLight => _p.textLight;

  // ── Status ──
  static Color get error => _p.error;
  static Color get warning => _p.warning;

  // ── Borders ──
  static Color get borderHairline => _p.borderHairline;
  static Color get borderLight => _p.borderLight;

  // ── Gradients ──
  static List<Color> get primaryGradient => [_p.primaryGreen, _p.darkGreen];
  static List<Color> get mediumGradient => [_p.primaryGreen, _p.mediumGreen];

  // ── Glassmorphism ──
  static Color get glassBackground => _p.glassBackground;
  static Color get glassBorder => _p.glassBorder;
}
