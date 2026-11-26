import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../constants/app_colors.dart';
import 'package:provider/provider.dart';
import '../providers/theme_provider.dart';

/// Car silhouette with a battery pack that fills to the vehicle's state of
/// charge, drawn rather than imported so the artwork is ours.
///
/// The readout sits above the car rather than on top of it. Overlaying the
/// number on the roof was unreadable at phone width, which is the whole point
/// of the panel.
///
/// [soc] is null whenever the charger has never reported a state of charge.
/// Many units do not, so the widget must read correctly without it: it shows
/// energy delivered instead, never a 0% that would suggest a flat battery.
class ChargingBatteryCar extends StatefulWidget {
  const ChargingBatteryCar({
    super.key,
    required this.soc,
    required this.isCharging,
    this.energyKwh = 0,
    this.assetPath = 'assets/images/ev_car.png',
    this.packRect = const Rect.fromLTRB(0.335, 0.560, 0.660, 0.665),
    this.artworkAspect = 2.35,
  });

  /// Vehicle state of charge, 0 to 100. Null when unreported.
  final double? soc;

  /// Whether energy is actually flowing. A stopped session settles rather
  /// than pulsing forever.
  final bool isCharging;

  final double energyKwh;

  /// Rendered car artwork. Drop a transparent PNG at this path and it is used
  /// automatically; the drawn vector car below is the fallback, so a missing
  /// file degrades quietly rather than leaving a hole in the screen.
  ///
  /// Author it at [artworkAspect], with the car filling the frame and the
  /// battery pack where [packRect] expects it. Nothing else needs changing.
  final String assetPath;

  /// Where the battery pack sits inside the artwork, in fractions of the
  /// frame. The animated cells are drawn over this rectangle, so it is the one
  /// value to adjust if a new PNG places the pack differently.
  final Rect packRect;

  /// Width to height of the artwork frame. Must match the PNG, or BoxFit
  /// letterboxes it and the pack overlay drifts off the pack.
  final double artworkAspect;

  @override
  State<ChargingBatteryCar> createState() => _ChargingBatteryCarState();
}

class _ChargingBatteryCarState extends State<ChargingBatteryCar>
    with SingleTickerProviderStateMixin {
  late final AnimationController _flow;
  double _shownSoc = 0;

  /// null while the asset is still resolving, then whether it exists. Resolved
  /// once up front rather than per frame, so the fallback never flickers.
  bool? _hasArtwork;

  @override
  void initState() {
    super.initState();
    _flow = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    );
    if (widget.isCharging) _flow.repeat();
    _shownSoc = widget.soc ?? 0;
    _resolveArtwork();
  }

  void _resolveArtwork() {
    final stream =
        AssetImage(widget.assetPath).resolve(const ImageConfiguration());
    late final ImageStreamListener listener;
    listener = ImageStreamListener(
      (_, __) {
        if (mounted) setState(() => _hasArtwork = true);
        stream.removeListener(listener);
      },
      onError: (_, __) {
        // No PNG supplied yet. Fall back to the drawn car rather than
        // showing a broken image box.
        if (mounted) setState(() => _hasArtwork = false);
        stream.removeListener(listener);
      },
    );
    stream.addListener(listener);
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
    // Rebuild when the palette swaps: AppColors is global, so
    // nothing else would tell this widget its colours changed.
    context.watch<ThemeProvider>();
    final target = (widget.soc ?? 0).clamp(0, 100).toDouble();
    final hasSoc = widget.soc != null;

    return LayoutBuilder(
      builder: (context, box) {
        // Type scales with the space actually given, so the panel is legible
        // on a small phone and does not look lost on a large one.
        final unit = math.min(box.maxWidth, box.maxHeight <= 0 ? box.maxWidth : box.maxHeight);
        final numberSize = (unit * 0.30).clamp(34.0, 64.0);

        return TweenAnimationBuilder<double>(
          tween: Tween(begin: _shownSoc, end: target),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOutCubic,
          onEnd: () => _shownSoc = target,
          builder: (context, soc, _) {
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Readout, then the car. Separated so neither crowds the other.
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      hasSoc
                          ? soc.round().toString()
                          : widget.energyKwh.toStringAsFixed(2),
                      style: TextStyle(
                        fontSize: numberSize,
                        height: 1.0,
                        fontWeight: FontWeight.w300,
                        color: AppColors.textPrimary,
                        letterSpacing: -1.5,
                      ),
                    ),
                    Padding(
                      padding: EdgeInsets.only(top: numberSize * 0.16, left: 4),
                      child: Text(
                        hasSoc ? '%' : 'kWh',
                        style: TextStyle(
                          fontSize: numberSize * 0.32,
                          fontWeight: FontWeight.w400,
                          color: AppColors.primaryGreen,
                        ),
                      ),
                    ),
                  ],
                ),
                SizedBox(height: unit * 0.02),
                Text(
                  hasSoc ? 'VEHICLE BATTERY' : 'ENERGY DELIVERED',
                  style: TextStyle(
                    fontSize: 10,
                    letterSpacing: 2.5,
                    color: AppColors.textTertiary.withOpacity(0.7),
                  ),
                ),
                SizedBox(height: unit * 0.05),
                Flexible(
                  child: AnimatedBuilder(
                    animation: _flow,
                    builder: (context, __) => AspectRatio(
                      aspectRatio: widget.artworkAspect,
                      child: _hasArtwork == true
                          // Rendered car, with only the pack animated over it.
                          ? Stack(
                              fit: StackFit.expand,
                              children: [
                                Image.asset(widget.assetPath,
                                    fit: BoxFit.contain),
                                CustomPaint(
                                  painter: _PackOverlayPainter(
                                    soc: hasSoc ? soc : 55,
                                    phase: _flow.value,
                                    charging: widget.isCharging,
                                    rect: widget.packRect,
                                  ),
                                ),
                              ],
                            )
                          : CustomPaint(
                              painter: _CarPainter(
                                soc: hasSoc ? soc : 55,
                                phase: _flow.value,
                                charging: widget.isCharging,
                              ),
                            ),
                    ),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

/// The animated cells alone, positioned over a rendered car image.
///
/// Kept separate from [_CarPainter] because the artwork already draws the
/// vehicle: painting the vector car underneath would show through the PNG's
/// transparent areas.
class _PackOverlayPainter extends CustomPainter {
  _PackOverlayPainter({
    required this.soc,
    required this.phase,
    required this.charging,
    required this.rect,
  });

  final double soc;
  final double phase;
  final bool charging;
  final Rect rect; // fractions of the frame

  @override
  void paint(Canvas canvas, Size size) {
    _paintCells(
      canvas,
      Rect.fromLTRB(
        rect.left * size.width,
        rect.top * size.height,
        rect.right * size.width,
        rect.bottom * size.height,
      ),
      soc: soc,
      phase: phase,
      charging: charging,
      drawShell: false, // the artwork supplies the housing
    );
  }

  @override
  bool shouldRepaint(covariant _PackOverlayPainter old) =>
      old.soc != soc ||
      old.phase != phase ||
      old.charging != charging ||
      old.rect != rect;
}

/// Battery cells filling to [soc], with a slow highlight travelling along the
/// lit ones while energy flows. Shared so the drawn car and the rendered
/// artwork animate identically.
void _paintCells(
  Canvas canvas,
  Rect box, {
  required double soc,
  required double phase,
  required bool charging,
  bool drawShell = true,
  int cells = 8,
}) {
  final shell = RRect.fromRectAndRadius(box, const Radius.circular(3));
  if (drawShell) {
    canvas.drawRRect(shell, Paint()..color = AppColors.background.withOpacity(0.9));
  }

  final gap = box.width * 0.014;
  final cellW = (box.width - gap * (cells - 1)) / cells;
  final lit = (soc / 100.0) * cells;

  for (var i = 0; i < cells; i++) {
    final x = box.left + i * (cellW + gap);
    final cell = RRect.fromRectAndRadius(
      Rect.fromLTWH(x + 1, box.top + 2, cellW - 2, box.height - 4),
      const Radius.circular(1.5),
    );

    final fill = (lit - i).clamp(0.0, 1.0);
    if (fill <= 0.02) {
      canvas.drawRRect(
        cell,
        Paint()..color = AppColors.textTertiary.withOpacity(0.10),
      );
      continue;
    }

    var glow = 0.0;
    if (charging) {
      final head = phase * cells;
      glow = math.max(0.0, 1.0 - (i - head).abs() / 1.6);
    }

    canvas.drawRRect(
      cell,
      Paint()
        ..color = Color.lerp(
          AppColors.darkGreen,
          AppColors.primaryGreen,
          0.30 + 0.70 * fill,
        )!
            .withOpacity(0.60 + 0.40 * fill),
    );

    if (glow > 0.02) {
      canvas.drawRRect(
        cell,
        Paint()
          ..color = AppColors.primaryGreen.withOpacity(0.5 * glow)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
      );
    }
  }

  if (drawShell) {
    canvas.drawRRect(
      shell,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1
        ..color = AppColors.primaryGreen.withOpacity(0.38),
    );
  }
}

class _CarPainter extends CustomPainter {
  _CarPainter({
    required this.soc,
    required this.phase,
    required this.charging,
  });

  final double soc;
  final double phase; // 0..1, drives the travelling charge pulse
  final bool charging;

  static const int _cells = 8;

  // Layout constants, as fractions of the paint box. Named so the geometry is
  // adjustable in one place rather than scattered through the path.
  static const double _groundY = 0.90;
  static const double _sillY = 0.72; // underside of the body
  static const double _wheelY = 0.745;
  static const double _wheelR = 0.145;
  static const double _frontAxle = 0.255;
  static const double _rearAxle = 0.755;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    _drawGlow(canvas, w, h);
    _drawBody(canvas, w, h);
    _drawPack(canvas, w, h);
    // After the body, or the filled shell hides them and the car appears to
    // float on two faint rings.
    _drawWheels(canvas, w, h);
    _drawCable(canvas, w, h);
  }

  void _drawGlow(Canvas canvas, double w, double h) {
    final rect = Rect.fromCenter(
      center: Offset(w * 0.5, h * _groundY),
      width: w * 0.86,
      height: h * 0.22,
    );
    canvas.drawOval(
      rect,
      Paint()
        ..shader = RadialGradient(
          colors: [
            AppColors.primaryGreen.withOpacity(charging ? 0.20 : 0.07),
            Colors.transparent,
          ],
        ).createShader(rect),
    );
  }

  void _drawWheels(Canvas canvas, double w, double h) {
    for (final cx in [w * _frontAxle, w * _rearAxle]) {
      final c = Offset(cx, h * _wheelY);
      final r = h * _wheelR;
      canvas.drawCircle(c, r, Paint()..color = AppColors.background);
      canvas.drawCircle(
        c,
        r,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2
          ..color = AppColors.primaryGreen.withOpacity(0.55),
      );
      canvas.drawCircle(
        c,
        r * 0.36,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4
          ..color = AppColors.primaryGreen.withOpacity(0.30),
      );
    }
  }

  /// One continuous silhouette: nose, bonnet, glasshouse, tail, then a sill
  /// that arches over each wheel so the car sits on them rather than in front
  /// of them.
  void _drawBody(Canvas canvas, double w, double h) {
    const archTop = 0.47; // control height; peaks just above the tyre crown

    final p = Path()
      // nose
      ..moveTo(w * 0.045, h * _sillY)
      ..lineTo(w * 0.042, h * 0.585)
      ..quadraticBezierTo(w * 0.048, h * 0.525, w * 0.115, h * 0.505)
      // bonnet
      ..lineTo(w * 0.265, h * 0.470)
      // windscreen
      ..quadraticBezierTo(w * 0.330, h * 0.215, w * 0.450, h * 0.198)
      // roof
      ..lineTo(w * 0.600, h * 0.198)
      // tailgate
      ..quadraticBezierTo(w * 0.715, h * 0.215, w * 0.780, h * 0.470)
      ..lineTo(w * 0.910, h * 0.505)
      ..quadraticBezierTo(w * 0.958, h * 0.525, w * 0.958, h * 0.590)
      ..lineTo(w * 0.955, h * _sillY)
      // sill, right to left, arching over the rear then front wheel
      ..lineTo(w * (_rearAxle + 0.105), h * _sillY)
      ..quadraticBezierTo(
          w * _rearAxle, h * archTop, w * (_rearAxle - 0.105), h * _sillY)
      ..lineTo(w * (_frontAxle + 0.105), h * _sillY)
      ..quadraticBezierTo(
          w * _frontAxle, h * archTop, w * (_frontAxle - 0.105), h * _sillY)
      ..close();

    canvas.drawPath(
      p,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.cardBackground,
            AppColors.surface.withOpacity(0.6),
          ],
        ).createShader(Rect.fromLTWH(0, 0, w, h)),
    );

    canvas.drawPath(
      p,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.8
        ..strokeJoin = StrokeJoin.round
        ..color = AppColors.primaryGreen.withOpacity(charging ? 0.6 : 0.32),
    );

    // Glazing, dim so the pack stays the focal point.
    final glass = Path()
      ..moveTo(w * 0.300, h * 0.450)
      ..quadraticBezierTo(w * 0.352, h * 0.245, w * 0.458, h * 0.232)
      ..lineTo(w * 0.592, h * 0.232)
      ..quadraticBezierTo(w * 0.692, h * 0.245, w * 0.748, h * 0.450)
      ..close();
    canvas.drawPath(glass, Paint()..color = AppColors.primaryGreen.withOpacity(0.07));

    // B pillar, enough to stop the glass reading as one flat pane.
    canvas.drawLine(
      Offset(w * 0.510, h * 0.234),
      Offset(w * 0.510, h * 0.446),
      Paint()
        ..strokeWidth = 1.3
        ..color = AppColors.primaryGreen.withOpacity(0.20),
    );
  }

  void _drawPack(Canvas canvas, double w, double h) {
    _paintCells(
      canvas,
      Rect.fromLTRB(
        w * (_frontAxle + 0.095),
        h * 0.615,
        w * (_rearAxle - 0.095),
        h * 0.705,
      ),
      soc: soc,
      phase: phase,
      charging: charging,
      cells: _cells,
    );
  }

  /// Cable into the port on the rear flank, with charge travelling along it.
  void _drawCable(Canvas canvas, double w, double h) {
    final port = Offset(w * 0.945, h * 0.560);
    final path = Path()
      ..moveTo(port.dx, port.dy)
      ..cubicTo(w * 0.995, h * 0.60, w * 0.975, h * 0.86, w * 0.998, h * 0.905);

    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.2
        ..strokeCap = StrokeCap.round
        ..color = AppColors.primaryGreen.withOpacity(charging ? 0.65 : 0.28),
    );

    final pulse = charging ? 0.45 + 0.35 * math.sin(phase * math.pi * 2) : 0.22;
    canvas.drawCircle(
      port,
      4.0,
      Paint()..color = AppColors.primaryGreen.withOpacity(pulse.clamp(0.0, 1.0)),
    );
    if (charging) {
      canvas.drawCircle(
        port,
        7.5,
        Paint()
          ..color = AppColors.primaryGreen.withOpacity(0.30 * pulse)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _CarPainter old) =>
      old.soc != soc || old.phase != phase || old.charging != charging;
}
