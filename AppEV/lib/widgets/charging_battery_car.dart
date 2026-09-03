import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../constants/app_colors.dart';

/// Car silhouette with a battery pack that fills to the vehicle's state of
/// charge, drawn rather than imported so the artwork is ours.
///
/// [soc] is null whenever the charger has never reported a state of charge.
/// Many units do not, so the widget must read correctly without it: it then
/// shows the pack gently animating and no percentage, instead of a hard 0%
/// that would tell the driver their battery is empty.
class ChargingBatteryCar extends StatefulWidget {
  const ChargingBatteryCar({
    super.key,
    required this.soc,
    required this.isCharging,
    this.energyKwh = 0,
    this.powerKw = 0,
  });

  /// Vehicle state of charge, 0 to 100. Null when unreported.
  final double? soc;

  /// Whether energy is actually flowing. Drives the animation, so a paused or
  /// finished session settles rather than pulsing forever.
  final bool isCharging;

  final double energyKwh;
  final double powerKw;

  @override
  State<ChargingBatteryCar> createState() => _ChargingBatteryCarState();
}

class _ChargingBatteryCarState extends State<ChargingBatteryCar>
    with SingleTickerProviderStateMixin {
  late final AnimationController _flow;

  // Animated so the pack glides to a new reading. Meter values arrive every
  // ten seconds or so, and snapping between them looks like a fault.
  double _shownSoc = 0;

  @override
  void initState() {
    super.initState();
    _flow = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    );
    if (widget.isCharging) _flow.repeat();
    _shownSoc = widget.soc ?? 0;
  }

  @override
  void didUpdateWidget(covariant ChargingBatteryCar old) {
    super.didUpdateWidget(old);
    if (widget.isCharging && !_flow.isAnimating) {
      _flow.repeat();
    } else if (!widget.isCharging && _flow.isAnimating) {
      _flow.stop();
    }
  }

  @override
  void dispose() {
    _flow.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final target = (widget.soc ?? 0).clamp(0, 100).toDouble();

    return TweenAnimationBuilder<double>(
      tween: Tween(begin: _shownSoc, end: target),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutCubic,
      onEnd: () => _shownSoc = target,
      builder: (context, soc, _) {
        return AnimatedBuilder(
          animation: _flow,
          builder: (context, __) {
            return AspectRatio(
              aspectRatio: 16 / 10,
              child: CustomPaint(
                painter: _CarPainter(
                  soc: soc,
                  hasSoc: widget.soc != null,
                  phase: _flow.value,
                  charging: widget.isCharging,
                ),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const SizedBox(height: 8),
                      if (widget.soc != null)
                        Text(
                          '${soc.round()}%',
                          style: const TextStyle(
                            fontSize: 44,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                            letterSpacing: -1,
                          ),
                        )
                      else
                        Text(
                          widget.energyKwh.toStringAsFixed(2),
                          style: const TextStyle(
                            fontSize: 44,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                            letterSpacing: -1,
                          ),
                        ),
                      Text(
                        widget.soc != null ? 'BATTERY' : 'kWh DELIVERED',
                        style: TextStyle(
                          fontSize: 11,
                          letterSpacing: 3,
                          color: AppColors.textTertiary.withOpacity(0.8),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _CarPainter extends CustomPainter {
  _CarPainter({
    required this.soc,
    required this.hasSoc,
    required this.phase,
    required this.charging,
  });

  final double soc;
  final bool hasSoc;
  final double phase; // 0..1, drives the travelling charge pulse
  final bool charging;

  static const int _cells = 9;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    _drawGround(canvas, w, h);
    _drawBody(canvas, w, h);
    _drawPack(canvas, w, h);
    _drawWheels(canvas, w, h);
    _drawCable(canvas, w, h);
  }

  /// Soft ellipse under the car so it does not float on the background.
  void _drawGround(Canvas canvas, double w, double h) {
    final rect = Rect.fromCenter(
      center: Offset(w * 0.5, h * 0.80),
      width: w * 0.78,
      height: h * 0.16,
    );
    canvas.drawOval(
      rect,
      Paint()
        ..shader = RadialGradient(
          colors: [
            AppColors.primaryGreen.withOpacity(charging ? 0.16 : 0.06),
            Colors.transparent,
          ],
        ).createShader(rect),
    );
  }

  /// Cabin and bonnet as one continuous silhouette.
  void _drawBody(Canvas canvas, double w, double h) {
    final body = Path()
      ..moveTo(w * 0.14, h * 0.66)
      ..lineTo(w * 0.19, h * 0.50)
      ..quadraticBezierTo(w * 0.24, h * 0.44, w * 0.34, h * 0.42)
      ..quadraticBezierTo(w * 0.42, h * 0.24, w * 0.54, h * 0.24)
      ..quadraticBezierTo(w * 0.68, h * 0.24, w * 0.74, h * 0.42)
      ..quadraticBezierTo(w * 0.84, h * 0.45, w * 0.87, h * 0.53)
      ..lineTo(w * 0.89, h * 0.66)
      ..quadraticBezierTo(w * 0.89, h * 0.70, w * 0.85, h * 0.70)
      ..lineTo(w * 0.18, h * 0.70)
      ..quadraticBezierTo(w * 0.14, h * 0.70, w * 0.14, h * 0.66)
      ..close();

    canvas.drawPath(
      body,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.cardBackground.withOpacity(0.95),
            AppColors.surface.withOpacity(0.85),
          ],
        ).createShader(Rect.fromLTWH(0, 0, w, h)),
    );

    canvas.drawPath(
      body,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..color = AppColors.primaryGreen.withOpacity(charging ? 0.55 : 0.28),
    );

    // Windows, kept dim so the battery remains the focal point.
    final glass = Path()
      ..moveTo(w * 0.37, h * 0.42)
      ..quadraticBezierTo(w * 0.44, h * 0.29, w * 0.54, h * 0.29)
      ..quadraticBezierTo(w * 0.65, h * 0.29, w * 0.70, h * 0.42)
      ..close();
    canvas.drawPath(
      glass,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.07),
    );
  }

  /// The battery pack: discrete cells that light up with state of charge.
  void _drawPack(Canvas canvas, double w, double h) {
    final left = w * 0.24;
    final right = w * 0.78;
    final top = h * 0.54;
    final bottom = h * 0.66;

    final shell = RRect.fromRectAndRadius(
      Rect.fromLTRB(left, top, right, bottom),
      const Radius.circular(4),
    );
    canvas.drawRRect(
      shell,
      Paint()..color = AppColors.background.withOpacity(0.85),
    );

    final gap = (right - left) * 0.012;
    final cellW = ((right - left) - gap * (_cells - 1)) / _cells;

    // How many cells the current charge lights, including the partial one at
    // the leading edge, so movement is visible between whole cells.
    final lit = hasSoc ? (soc / 100.0) * _cells : _cells * 0.55;

    for (var i = 0; i < _cells; i++) {
      final x = left + i * (cellW + gap);
      final cell = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, top + 1.5, cellW, (bottom - top) - 3),
        const Radius.circular(2),
      );

      final fill = (lit - i).clamp(0.0, 1.0);
      if (fill <= 0) {
        canvas.drawRRect(
          cell,
          Paint()..color = AppColors.textTertiary.withOpacity(0.08),
        );
        continue;
      }

      // A pulse travels along the lit cells while energy is flowing. It is a
      // slow highlight rather than a blink, which reads as movement without
      // demanding attention.
      var glow = 0.0;
      if (charging) {
        final head = phase * _cells;
        final d = (i - head).abs();
        glow = math.max(0.0, 1.0 - d / 1.8);
      }

      final base = Color.lerp(
        AppColors.darkGreen,
        AppColors.primaryGreen,
        0.35 + 0.65 * fill,
      )!;

      canvas.drawRRect(
        cell,
        Paint()..color = base.withOpacity(0.55 + 0.45 * fill),
      );

      if (glow > 0.02) {
        canvas.drawRRect(
          cell,
          Paint()
            ..color = AppColors.primaryGreen.withOpacity(0.45 * glow)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
        );
      }
    }

    canvas.drawRRect(
      shell,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = AppColors.primaryGreen.withOpacity(0.35),
    );
  }

  void _drawWheels(Canvas canvas, double w, double h) {
    for (final cx in [w * 0.31, w * 0.71]) {
      final c = Offset(cx, h * 0.70);
      canvas.drawCircle(
        c,
        h * 0.085,
        Paint()..color = AppColors.background,
      );
      canvas.drawCircle(
        c,
        h * 0.085,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = AppColors.primaryGreen.withOpacity(0.45),
      );
      canvas.drawCircle(
        c,
        h * 0.032,
        Paint()..color = AppColors.primaryGreen.withOpacity(0.25),
      );
    }
  }

  /// Charging cable entering the port on the right.
  void _drawCable(Canvas canvas, double w, double h) {
    final path = Path()
      ..moveTo(w * 0.885, h * 0.56)
      ..cubicTo(w * 0.97, h * 0.56, w * 0.97, h * 0.86, w * 1.02, h * 0.86);

    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.4
        ..strokeCap = StrokeCap.round
        ..color = AppColors.primaryGreen.withOpacity(charging ? 0.7 : 0.3),
    );

    // Port indicator, brightening in step with the pack pulse.
    final portGlow = charging ? 0.45 + 0.35 * math.sin(phase * math.pi * 2) : 0.2;
    canvas.drawCircle(
      Offset(w * 0.885, h * 0.56),
      4.5,
      Paint()..color = AppColors.primaryGreen.withOpacity(portGlow.clamp(0.0, 1.0)),
    );
  }

  @override
  bool shouldRepaint(covariant _CarPainter old) =>
      old.soc != soc ||
      old.phase != phase ||
      old.charging != charging ||
      old.hasSoc != hasSoc;
}
