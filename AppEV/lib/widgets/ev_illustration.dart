import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../constants/app_colors.dart';

/// Flat minimalist 2D illustration of a person charging an EV car
class EVChargingIllustration extends StatelessWidget {
  final double height;

  const EVChargingIllustration({super.key, this.height = 200});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: height,
      child: CustomPaint(
        painter: _EVChargingPainter(),
      ),
    );
  }
}

class _EVChargingPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height;
    final scale = size.height / 200;
    final groundY = cy - 18 * scale;

    // ===== BACKGROUND ELEMENTS =====
    _drawCityBackground(canvas, size, scale);

    // ===== GROUND =====
    final groundPaint = Paint()..color = const Color(0xFF0F1B2D);
    canvas.drawRect(
      Rect.fromLTWH(0, groundY, size.width, 18 * scale),
      groundPaint,
    );
    // Ground line
    canvas.drawLine(
      Offset(0, groundY),
      Offset(size.width, groundY),
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.3)
        ..strokeWidth = 1.5 * scale,
    );
    // Ground glow dots
    for (int i = 0; i < 6; i++) {
      final dotX = size.width * (i + 1) / 7;
      canvas.drawCircle(
        Offset(dotX, groundY),
        3 * scale,
        Paint()
          ..color = AppColors.primaryGreen.withOpacity(0.15)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 4 * scale),
      );
      canvas.drawCircle(
        Offset(dotX, groundY),
        1.5 * scale,
        Paint()..color = AppColors.primaryGreen.withOpacity(0.4),
      );
    }

    // Layout: Person(left) → Car(center-left) → Station(center-right) → Cable connects them
    final personX = cx - 68 * scale;
    final carX = cx - 10 * scale;       // car center
    final stationX = cx + 55 * scale;   // station center

    // ===== EV CAR =====
    _drawEVCar(canvas, carX, groundY, scale);

    // ===== CHARGING STATION =====
    _drawChargingStation(canvas, stationX, groundY, scale);

    // ===== CHARGING CABLE (station to car) =====
    // Cable from station left side to car right side
    final cableStartX = stationX - 8 * scale;  // station left edge
    final cableStartY = groundY - 40 * scale;
    final cableEndX = carX + 35 * scale;        // car right side
    final cableEndY = groundY - 28 * scale;
    _drawChargingCable(canvas, cableStartX, cableStartY, cableEndX, cableEndY, groundY, scale);

    // ===== PERSON (left side) =====
    _drawPerson(canvas, personX, groundY, scale);

    // ===== SPARKLE PARTICLES =====
    _drawSparkles(canvas, size, scale);
  }

  void _drawCityBackground(Canvas canvas, Size size, double scale) {
    final buildingColor1 = const Color(0xFF0E1525).withOpacity(0.7);
    final buildingColor2 = const Color(0xFF111D30).withOpacity(0.6);
    final windowColor = AppColors.primaryGreen.withOpacity(0.15);

    // Far buildings
    final buildings = [
      [0.05, 0.55, 0.12],
      [0.15, 0.45, 0.08],
      [0.22, 0.60, 0.10],
      [0.35, 0.40, 0.07],
      [0.55, 0.50, 0.09],
      [0.65, 0.65, 0.11],
      [0.78, 0.42, 0.08],
      [0.88, 0.55, 0.10],
      [0.95, 0.48, 0.07],
    ];

    for (var b in buildings) {
      final bx = size.width * b[0];
      final bh = size.height * b[1];
      final bw = size.width * b[2];
      final by = size.height - 18 * scale - bh;

      final bPaint = Paint()..color = buildings.indexOf(b) % 2 == 0 ? buildingColor1 : buildingColor2;
      final rrect = RRect.fromRectAndCorners(
        Rect.fromLTWH(bx, by, bw, bh),
        topLeft: Radius.circular(3 * scale),
        topRight: Radius.circular(3 * scale),
      );
      canvas.drawRRect(rrect, bPaint);

      // Windows
      final wPaint = Paint()..color = windowColor;
      final wSize = 3.0 * scale;
      final wGap = 6.0 * scale;
      for (double wy = by + 8 * scale; wy < by + bh - 8 * scale; wy += wGap) {
        for (double wx = bx + 4 * scale; wx < bx + bw - 4 * scale; wx += wGap) {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(wx, wy, wSize, wSize),
              Radius.circular(0.5 * scale),
            ),
            wPaint,
          );
        }
      }
    }

    // Moon / sun glow
    final moonCenter = Offset(size.width * 0.82, size.height * 0.15);
    final moonGlow = Paint()
      ..color = AppColors.primaryGreen.withOpacity(0.05)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 20 * scale);
    canvas.drawCircle(moonCenter, 25 * scale, moonGlow);
    canvas.drawCircle(
      moonCenter,
      10 * scale,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.2),
    );
    canvas.drawCircle(
      moonCenter,
      7 * scale,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.35),
    );
  }

  void _drawEVCar(Canvas canvas, double x, double groundY, double scale) {
    // Car body — compact sleek EV
    final carLeft = x - 35 * scale;
    final carRight = x + 35 * scale;
    final carTop = groundY - 38 * scale;
    final carBottom = groundY - 8 * scale;

    // Main body path
    final carBody = Path();
    carBody.moveTo(carLeft + 4 * scale, carBottom);
    carBody.lineTo(carLeft, carBottom - 10 * scale);
    carBody.lineTo(carLeft + 8 * scale, carTop + 12 * scale);
    // Roof curve
    carBody.quadraticBezierTo(
      carLeft + 18 * scale, carTop - 2 * scale,
      x, carTop,
    );
    carBody.quadraticBezierTo(
      carRight - 12 * scale, carTop - 1 * scale,
      carRight - 4 * scale, carTop + 15 * scale,
    );
    carBody.lineTo(carRight, carBottom - 8 * scale);
    carBody.lineTo(carRight - 3 * scale, carBottom);
    carBody.close();

    // Car fill
    canvas.drawPath(
      carBody,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [const Color(0xFF1A2A40), const Color(0xFF0F1B2D)],
        ).createShader(Rect.fromLTWH(carLeft, carTop, 70 * scale, 35 * scale)),
    );

    // Car outline
    canvas.drawPath(
      carBody,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2 * scale,
    );

    // Windshield
    final windshield = Path();
    windshield.moveTo(carLeft + 14 * scale, carTop + 12 * scale);
    windshield.quadraticBezierTo(x - 4 * scale, carTop + 2 * scale, x + 4 * scale, carTop + 3 * scale);
    windshield.lineTo(x + 12 * scale, carTop + 12 * scale);
    windshield.close();
    canvas.drawPath(windshield, Paint()..color = AppColors.primaryGreen.withOpacity(0.10));

    // Headlight (right/front)
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(carRight - 7 * scale, carBottom - 16 * scale, 5 * scale, 3 * scale),
        Radius.circular(1.5 * scale),
      ),
      Paint()..color = AppColors.primaryGreen.withOpacity(0.6),
    );
    // Headlight glow
    canvas.drawCircle(
      Offset(carRight - 4 * scale, carBottom - 14 * scale),
      4 * scale,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.12)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 4 * scale),
    );

    // Taillight (left/rear)
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(carLeft + 2 * scale, carBottom - 14 * scale, 3 * scale, 2.5 * scale),
        Radius.circular(1 * scale),
      ),
      Paint()..color = Colors.redAccent.withOpacity(0.5),
    );

    // Wheels
    _drawWheel(canvas, carLeft + 12 * scale, carBottom + 2 * scale, 8 * scale, scale);
    _drawWheel(canvas, carRight - 12 * scale, carBottom + 2 * scale, 8 * scale, scale);

    // ===== CLEAN BATTERY INDICATOR (above car) =====
    final battW = 22 * scale;
    final battH = 10 * scale;
    final battX = x - battW / 2;
    final battY = carTop - 16 * scale;

    // Battery outline
    final battRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(battX, battY, battW, battH),
      Radius.circular(2 * scale),
    );
    canvas.drawRRect(battRect, Paint()..color = const Color(0xFF0F1B2D));
    canvas.drawRRect(
      battRect,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.5)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1 * scale,
    );
    // Battery tip (right nub)
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(battX + battW, battY + 3 * scale, 2.5 * scale, 4 * scale),
        Radius.circular(1 * scale),
      ),
      Paint()..color = AppColors.primaryGreen.withOpacity(0.5),
    );
    // Battery fill (green, full)
    final fillPadding = 1.5 * scale;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
          battX + fillPadding,
          battY + fillPadding,
          (battW - fillPadding * 2),  // full charge
          battH - fillPadding * 2,
        ),
        Radius.circular(1 * scale),
      ),
      Paint()..color = AppColors.primaryGreen.withOpacity(0.35),
    );
    // Lightning bolt inside battery
    final boltPath = Path();
    final boltCx = x;
    final boltCy = battY + battH / 2;
    boltPath.moveTo(boltCx + 1 * scale, boltCy - 3.5 * scale);
    boltPath.lineTo(boltCx - 2 * scale, boltCy);
    boltPath.lineTo(boltCx + 0.5 * scale, boltCy);
    boltPath.lineTo(boltCx - 1 * scale, boltCy + 3.5 * scale);
    boltPath.lineTo(boltCx + 2.5 * scale, boltCy - 0.5 * scale);
    boltPath.lineTo(boltCx, boltCy - 0.5 * scale);
    boltPath.close();
    canvas.drawPath(boltPath, Paint()..color = AppColors.primaryGreen);

    // Charging port dot (right side of car, where cable connects)
    final portX = carRight - 5 * scale;
    final portY = carBottom - 20 * scale;
    canvas.drawCircle(
      Offset(portX, portY),
      3 * scale,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.3)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 3 * scale),
    );
    canvas.drawCircle(
      Offset(portX, portY),
      1.5 * scale,
      Paint()..color = AppColors.primaryGreen,
    );
  }

  void _drawWheel(Canvas canvas, double cx, double cy, double radius, double scale) {
    // Tire
    canvas.drawCircle(
      Offset(cx, cy),
      radius,
      Paint()..color = const Color(0xFF1A1A2E),
    );
    // Rim
    canvas.drawCircle(
      Offset(cx, cy),
      radius * 0.6,
      Paint()..color = const Color(0xFF2A3A50),
    );
    // Hub
    canvas.drawCircle(
      Offset(cx, cy),
      radius * 0.25,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.3),
    );
    // Tire outline
    canvas.drawCircle(
      Offset(cx, cy),
      radius,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.15)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8 * scale,
    );
  }

  void _drawChargingStation(Canvas canvas, double x, double groundY, double scale) {
    // Station pole
    final poleRect = Rect.fromLTWH(
      x - 8 * scale, groundY - 75 * scale, 16 * scale, 75 * scale,
    );
    final poleRRect = RRect.fromRectAndCorners(
      poleRect,
      topLeft: Radius.circular(4 * scale),
      topRight: Radius.circular(4 * scale),
    );
    canvas.drawRRect(
      poleRRect,
      Paint()..color = const Color(0xFF1A2A40),
    );
    canvas.drawRRect(
      poleRRect,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.25)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2 * scale,
    );

    // Station screen area
    final screenRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(x - 6 * scale, groundY - 68 * scale, 12 * scale, 18 * scale),
      Radius.circular(2 * scale),
    );
    canvas.drawRRect(
      screenRect,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.08),
    );
    canvas.drawRRect(
      screenRect,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8 * scale,
    );

    // Screen content - lightning bolt icon
    final boltPath = Path();
    final bx = x;
    final by = groundY - 63 * scale;
    boltPath.moveTo(bx + 1 * scale, by);
    boltPath.lineTo(bx - 2 * scale, by + 4 * scale);
    boltPath.lineTo(bx, by + 4 * scale);
    boltPath.lineTo(bx - 1 * scale, by + 8 * scale);
    boltPath.lineTo(bx + 3 * scale, by + 3 * scale);
    boltPath.lineTo(bx + 1 * scale, by + 3 * scale);
    boltPath.lineTo(bx + 2 * scale, by);
    boltPath.close();
    canvas.drawPath(
      boltPath,
      Paint()..color = AppColors.primaryGreen,
    );

    // Status LED
    final ledGlow = Paint()
      ..color = AppColors.primaryGreen.withOpacity(0.5)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 3 * scale);
    canvas.drawCircle(
      Offset(x, groundY - 45 * scale),
      2.5 * scale,
      ledGlow,
    );
    canvas.drawCircle(
      Offset(x, groundY - 45 * scale),
      1.5 * scale,
      Paint()..color = AppColors.primaryGreen,
    );

    // Station base
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 12 * scale, groundY - 4 * scale, 24 * scale, 4 * scale),
        Radius.circular(1 * scale),
      ),
      Paint()..color = const Color(0xFF1A2A40),
    );
  }

  void _drawPerson(Canvas canvas, double x, double groundY, double scale) {
    // ===== PERSON - flat minimalist style =====

    // Shadow
    final shadowPaint = Paint()
      ..color = Colors.black.withOpacity(0.2)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 4 * scale);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(x, groundY - 1 * scale),
        width: 30 * scale,
        height: 6 * scale,
      ),
      shadowPaint,
    );

    // Legs
    final legPaint = Paint()
      ..color = const Color(0xFF2A3A50)
      ..strokeWidth = 5 * scale
      ..strokeCap = StrokeCap.round;
    // Left leg
    canvas.drawLine(
      Offset(x - 5 * scale, groundY - 30 * scale),
      Offset(x - 7 * scale, groundY - 4 * scale),
      legPaint,
    );
    // Right leg (slightly apart)
    canvas.drawLine(
      Offset(x + 3 * scale, groundY - 30 * scale),
      Offset(x + 6 * scale, groundY - 4 * scale),
      legPaint,
    );

    // Shoes
    final shoePaint = Paint()..color = AppColors.primaryGreen.withOpacity(0.7);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 11 * scale, groundY - 5 * scale, 9 * scale, 5 * scale),
        Radius.circular(2 * scale),
      ),
      shoePaint,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x + 2 * scale, groundY - 5 * scale, 9 * scale, 5 * scale),
        Radius.circular(2 * scale),
      ),
      shoePaint,
    );

    // Body / torso
    final torsoPath = Path();
    torsoPath.moveTo(x - 10 * scale, groundY - 30 * scale);
    torsoPath.lineTo(x - 12 * scale, groundY - 55 * scale);
    torsoPath.quadraticBezierTo(
      x, groundY - 60 * scale,
      x + 12 * scale, groundY - 55 * scale,
    );
    torsoPath.lineTo(x + 10 * scale, groundY - 30 * scale);
    torsoPath.close();

    // Jacket/shirt gradient
    final torsoGradient = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          const Color(0xFF1E6B4F),
          const Color(0xFF153D35),
        ],
      ).createShader(Rect.fromLTWH(
        x - 12 * scale, groundY - 60 * scale, 24 * scale, 30 * scale,
      ));
    canvas.drawPath(torsoPath, torsoGradient);

    // T-shirt collar detail
    final collarPaint = Paint()
      ..color = AppColors.primaryGreen.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1 * scale;
    final collarPath = Path();
    collarPath.moveTo(x - 5 * scale, groundY - 56 * scale);
    collarPath.quadraticBezierTo(
      x, groundY - 52 * scale,
      x + 5 * scale, groundY - 56 * scale,
    );
    canvas.drawPath(collarPath, collarPaint);

    // Arms
    final armPaint = Paint()
      ..color = const Color(0xFF1E6B4F)
      ..strokeWidth = 5 * scale
      ..strokeCap = StrokeCap.round;

    // Left arm (holding phone/app)
    canvas.drawLine(
      Offset(x - 12 * scale, groundY - 52 * scale),
      Offset(x - 20 * scale, groundY - 38 * scale),
      armPaint,
    );
    // Forearm
    canvas.drawLine(
      Offset(x - 20 * scale, groundY - 38 * scale),
      Offset(x - 16 * scale, groundY - 32 * scale),
      Paint()
        ..color = const Color(0xFFD4A574) // skin tone
        ..strokeWidth = 4 * scale
        ..strokeCap = StrokeCap.round,
    );

    // Phone in hand
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 19 * scale, groundY - 36 * scale, 7 * scale, 12 * scale),
        Radius.circular(1.5 * scale),
      ),
      Paint()..color = const Color(0xFF1A1A2E),
    );
    // Phone screen glow
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 18 * scale, groundY - 35 * scale, 5 * scale, 9 * scale),
        Radius.circular(1 * scale),
      ),
      Paint()..color = AppColors.primaryGreen.withOpacity(0.3),
    );

    // Right arm (relaxed)
    canvas.drawLine(
      Offset(x + 12 * scale, groundY - 52 * scale),
      Offset(x + 18 * scale, groundY - 36 * scale),
      armPaint,
    );
    // Hand
    canvas.drawCircle(
      Offset(x + 18 * scale, groundY - 35 * scale),
      3 * scale,
      Paint()..color = const Color(0xFFD4A574),
    );

    // Head
    canvas.drawCircle(
      Offset(x, groundY - 68 * scale),
      11 * scale,
      Paint()..color = const Color(0xFFD4A574),
    );

    // Hair
    final hairPath = Path();
    hairPath.addArc(
      Rect.fromCenter(
        center: Offset(x, groundY - 70 * scale),
        width: 24 * scale,
        height: 22 * scale,
      ),
      math.pi,
      math.pi,
    );
    hairPath.lineTo(x + 12 * scale, groundY - 67 * scale);
    hairPath.quadraticBezierTo(
      x + 13 * scale, groundY - 72 * scale,
      x + 8 * scale, groundY - 75 * scale,
    );
    hairPath.close();
    canvas.drawPath(
      hairPath,
      Paint()..color = const Color(0xFF2A1A0E),
    );

    // Simple face - eyes
    canvas.drawCircle(
      Offset(x - 4 * scale, groundY - 68 * scale),
      1.5 * scale,
      Paint()..color = const Color(0xFF1A1A2E),
    );
    canvas.drawCircle(
      Offset(x + 4 * scale, groundY - 68 * scale),
      1.5 * scale,
      Paint()..color = const Color(0xFF1A1A2E),
    );

    // Simple smile
    final smilePath = Path();
    smilePath.addArc(
      Rect.fromCenter(
        center: Offset(x, groundY - 64 * scale),
        width: 8 * scale,
        height: 5 * scale,
      ),
      0.2,
      math.pi - 0.4,
    );
    canvas.drawPath(
      smilePath,
      Paint()
        ..color = const Color(0xFF1A1A2E)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1 * scale
        ..strokeCap = StrokeCap.round,
    );
  }

  void _drawChargingCable(Canvas canvas, double startX, double startY, double endX, double endY, double groundY, double scale) {
    // P0 = start (station side)
    final p0x = startX;
    final p0y = startY;
    // P2 = end (car side)
    final p2x = endX;
    final p2y = endY;
    // P1 = control point (natural droop below both endpoints)
    final p1x = (p0x + p2x) / 2;
    final p1y = groundY - 8 * scale; // hangs near ground

    // Build cable path
    final cablePath = Path();
    cablePath.moveTo(p0x, p0y);
    cablePath.quadraticBezierTo(p1x, p1y, p2x, p2y);

    // Cable outer glow
    canvas.drawPath(
      cablePath,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.10)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6 * scale
        ..strokeCap = StrokeCap.round
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 4 * scale),
    );

    // Cable main line
    canvas.drawPath(
      cablePath,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.50)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0 * scale
        ..strokeCap = StrokeCap.round,
    );

    // Connector plugs at both ends
    for (final pt in [Offset(p0x, p0y), Offset(p2x, p2y)]) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: pt, width: 5 * scale, height: 4 * scale),
          Radius.circular(1 * scale),
        ),
        Paint()..color = AppColors.primaryGreen.withOpacity(0.6),
      );
    }

    // Energy flow particles on the Bezier curve
    // B(t) = (1-t)²·P0 + 2(1-t)·t·P1 + t²·P2
    for (final t in [0.2, 0.4, 0.6, 0.8]) {
      final u = 1.0 - t;
      final px = u * u * p0x + 2 * u * t * p1x + t * t * p2x;
      final py = u * u * p0y + 2 * u * t * p1y + t * t * p2y;

      canvas.drawCircle(
        Offset(px, py),
        3.0 * scale,
        Paint()
          ..color = AppColors.primaryGreen.withOpacity(0.20)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 3 * scale),
      );
      canvas.drawCircle(
        Offset(px, py),
        1.5 * scale,
        Paint()..color = AppColors.primaryGreen.withOpacity(0.8),
      );
    }
  }

  void _drawSparkles(Canvas canvas, Size size, double scale) {
    final sparklePositions = [
      [0.15, 0.2],
      [0.85, 0.35],
      [0.25, 0.4],
      [0.75, 0.15],
      [0.9, 0.55],
      [0.08, 0.6],
    ];

    for (var pos in sparklePositions) {
      final sx = size.width * pos[0];
      final sy = size.height * pos[1];
      final sparkleSize = (2 + sparklePositions.indexOf(pos) % 3) * scale;

      // Star sparkle shape
      final sparklePaint = Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.3);

      // Horizontal line
      canvas.drawLine(
        Offset(sx - sparkleSize, sy),
        Offset(sx + sparkleSize, sy),
        sparklePaint..strokeWidth = 0.8 * scale,
      );
      // Vertical line
      canvas.drawLine(
        Offset(sx, sy - sparkleSize),
        Offset(sx, sy + sparkleSize),
        sparklePaint..strokeWidth = 0.8 * scale,
      );

      // Center dot
      canvas.drawCircle(
        Offset(sx, sy),
        0.8 * scale,
        Paint()..color = AppColors.primaryGreen.withOpacity(0.5),
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Flat illustration of a person creating an account with a plus sign
class EVRegisterIllustration extends StatelessWidget {
  final double height;

  const EVRegisterIllustration({super.key, this.height = 160});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: height,
      child: CustomPaint(
        painter: _EVRegisterPainter(),
      ),
    );
  }
}

class _EVRegisterPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height;
    final scale = size.height / 160;

    // Ground
    final groundPaint = Paint()..color = const Color(0xFF0F1B2D);
    canvas.drawRect(
      Rect.fromLTWH(0, cy - 12 * scale, size.width, 12 * scale),
      groundPaint,
    );
    final groundLinePaint = Paint()
      ..color = AppColors.primaryGreen.withOpacity(0.3)
      ..strokeWidth = 1 * scale;
    canvas.drawLine(
      Offset(0, cy - 12 * scale),
      Offset(size.width, cy - 12 * scale),
      groundLinePaint,
    );

    // ===== PERSON 1 (left - welcoming) =====
    _drawWelcomePerson(canvas, cx - 40 * scale, cy - 12 * scale, scale);

    // ===== SHIELD / BADGE (center) =====
    _drawSecurityBadge(canvas, cx + 15 * scale, cy - 65 * scale, scale);

    // ===== PHONE/FORM (right) =====
    _drawSignUpForm(canvas, cx + 50 * scale, cy - 12 * scale, scale);

    // Sparkles
    final sparkles = [
      [0.1, 0.25],
      [0.9, 0.2],
      [0.2, 0.55],
      [0.8, 0.5],
    ];
    for (var s in sparkles) {
      final sx = size.width * s[0];
      final sy = size.height * s[1];
      final sSize = 2.5 * scale;
      final sPaint = Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.25)
        ..strokeWidth = 0.8 * scale;
      canvas.drawLine(Offset(sx - sSize, sy), Offset(sx + sSize, sy), sPaint);
      canvas.drawLine(Offset(sx, sy - sSize), Offset(sx, sy + sSize), sPaint);
    }
  }

  void _drawWelcomePerson(Canvas canvas, double x, double groundY, double scale) {
    // Shadow
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(x, groundY - 1 * scale),
        width: 28 * scale,
        height: 5 * scale,
      ),
      Paint()
        ..color = Colors.black.withOpacity(0.2)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 3 * scale),
    );

    // Legs
    final legPaint = Paint()
      ..color = const Color(0xFF2A3A50)
      ..strokeWidth = 4.5 * scale
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(x - 4 * scale, groundY - 26 * scale),
      Offset(x - 6 * scale, groundY - 3 * scale),
      legPaint,
    );
    canvas.drawLine(
      Offset(x + 4 * scale, groundY - 26 * scale),
      Offset(x + 6 * scale, groundY - 3 * scale),
      legPaint,
    );

    // Shoes
    final shoePaint = Paint()..color = const Color(0xFF00AA55);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 10 * scale, groundY - 4 * scale, 8 * scale, 4 * scale),
        Radius.circular(2 * scale),
      ),
      shoePaint,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(x + 2 * scale, groundY - 4 * scale, 8 * scale, 4 * scale),
        Radius.circular(2 * scale),
      ),
      shoePaint,
    );

    // Torso
    final torsoPath = Path();
    torsoPath.moveTo(x - 10 * scale, groundY - 26 * scale);
    torsoPath.lineTo(x - 11 * scale, groundY - 48 * scale);
    torsoPath.quadraticBezierTo(x, groundY - 52 * scale, x + 11 * scale, groundY - 48 * scale);
    torsoPath.lineTo(x + 10 * scale, groundY - 26 * scale);
    torsoPath.close();
    canvas.drawPath(
      torsoPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [const Color(0xFF6B3FA0), const Color(0xFF4A2D7A)],
        ).createShader(Rect.fromLTWH(x - 11 * scale, groundY - 52 * scale, 22 * scale, 26 * scale)),
    );

    // Arms - right arm waving
    final armPaint = Paint()
      ..color = const Color(0xFF6B3FA0)
      ..strokeWidth = 4.5 * scale
      ..strokeCap = StrokeCap.round;

    // Left arm down
    canvas.drawLine(
      Offset(x - 11 * scale, groundY - 45 * scale),
      Offset(x - 18 * scale, groundY - 32 * scale),
      armPaint,
    );
    canvas.drawCircle(
      Offset(x - 18 * scale, groundY - 31 * scale),
      2.5 * scale,
      Paint()..color = const Color(0xFFD4A574),
    );

    // Right arm waving up
    canvas.drawLine(
      Offset(x + 11 * scale, groundY - 45 * scale),
      Offset(x + 22 * scale, groundY - 56 * scale),
      armPaint,
    );
    // Hand
    canvas.drawCircle(
      Offset(x + 23 * scale, groundY - 57 * scale),
      2.5 * scale,
      Paint()..color = const Color(0xFFD4A574),
    );

    // Head
    canvas.drawCircle(
      Offset(x, groundY - 58 * scale),
      10 * scale,
      Paint()..color = const Color(0xFFD4A574),
    );

    // Hair (bob cut style)
    final hairPath = Path();
    hairPath.addArc(
      Rect.fromCenter(
        center: Offset(x, groundY - 60 * scale),
        width: 22 * scale,
        height: 20 * scale,
      ),
      math.pi,
      math.pi,
    );
    hairPath.lineTo(x + 11 * scale, groundY - 55 * scale);
    hairPath.lineTo(x + 12 * scale, groundY - 50 * scale);
    hairPath.quadraticBezierTo(x + 13 * scale, groundY - 55 * scale, x + 8 * scale, groundY - 60 * scale);
    hairPath.close();
    // Also left side hair
    final hairPath2 = Path();
    hairPath2.moveTo(x - 11 * scale, groundY - 60 * scale);
    hairPath2.lineTo(x - 12 * scale, groundY - 50 * scale);
    hairPath2.quadraticBezierTo(x - 13 * scale, groundY - 55 * scale, x - 8 * scale, groundY - 60 * scale);
    canvas.drawPath(hairPath, Paint()..color = const Color(0xFF1A0E2A));
    canvas.drawPath(hairPath2, Paint()..color = const Color(0xFF1A0E2A));

    // Eyes
    canvas.drawCircle(
      Offset(x - 3 * scale, groundY - 58 * scale),
      1.3 * scale,
      Paint()..color = const Color(0xFF1A1A2E),
    );
    canvas.drawCircle(
      Offset(x + 3 * scale, groundY - 58 * scale),
      1.3 * scale,
      Paint()..color = const Color(0xFF1A1A2E),
    );

    // Smile
    final smilePath = Path();
    smilePath.addArc(
      Rect.fromCenter(
        center: Offset(x, groundY - 54.5 * scale),
        width: 7 * scale,
        height: 4 * scale,
      ),
      0.2,
      math.pi - 0.4,
    );
    canvas.drawPath(
      smilePath,
      Paint()
        ..color = const Color(0xFF1A1A2E)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8 * scale
        ..strokeCap = StrokeCap.round,
    );
  }

  void _drawSecurityBadge(Canvas canvas, double x, double y, double scale) {
    // Shield shape
    final shieldPath = Path();
    shieldPath.moveTo(x, y - 18 * scale);
    shieldPath.lineTo(x + 15 * scale, y - 12 * scale);
    shieldPath.lineTo(x + 14 * scale, y + 5 * scale);
    shieldPath.quadraticBezierTo(x, y + 18 * scale, x - 14 * scale, y + 5 * scale);
    shieldPath.lineTo(x - 15 * scale, y - 12 * scale);
    shieldPath.close();

    // Shield glow
    canvas.drawPath(
      shieldPath,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.08)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 8 * scale),
    );

    // Shield fill
    canvas.drawPath(
      shieldPath,
      Paint()..color = AppColors.primaryGreen.withOpacity(0.12),
    );
    canvas.drawPath(
      shieldPath,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.5)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2 * scale,
    );

    // Checkmark inside
    final checkPath = Path();
    checkPath.moveTo(x - 5 * scale, y - 1 * scale);
    checkPath.lineTo(x - 1 * scale, y + 4 * scale);
    checkPath.lineTo(x + 7 * scale, y - 6 * scale);
    canvas.drawPath(
      checkPath,
      Paint()
        ..color = AppColors.primaryGreen
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2 * scale
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  void _drawSignUpForm(Canvas canvas, double x, double groundY, double scale) {
    // Floating form/card
    final formY = groundY - 70 * scale;
    final formRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(x - 20 * scale, formY, 40 * scale, 55 * scale),
      Radius.circular(4 * scale),
    );

    // Form shadow
    canvas.drawRRect(
      formRect,
      Paint()
        ..color = Colors.black.withOpacity(0.2)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 5 * scale),
    );

    // Form background
    canvas.drawRRect(formRect, Paint()..color = const Color(0xFF12192B));
    canvas.drawRRect(
      formRect,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.2)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8 * scale,
    );

    // Form lines (input fields)
    for (int i = 0; i < 3; i++) {
      final ly = formY + 10 * scale + i * 14 * scale;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x - 15 * scale, ly, 30 * scale, 8 * scale),
          Radius.circular(2 * scale),
        ),
        Paint()..color = AppColors.primaryGreen.withOpacity(0.06),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x - 15 * scale, ly, 30 * scale, 8 * scale),
          Radius.circular(2 * scale),
        ),
        Paint()
          ..color = AppColors.primaryGreen.withOpacity(0.15)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.5 * scale,
      );
      // Icon placeholder
      canvas.drawCircle(
        Offset(x - 11 * scale, ly + 4 * scale),
        2 * scale,
        Paint()..color = AppColors.primaryGreen.withOpacity(0.3),
      );
    }

    // Plus/Add user icon at top
    final plusGlow = Paint()
      ..color = AppColors.primaryGreen.withOpacity(0.15)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 5 * scale);
    canvas.drawCircle(Offset(x, formY - 8 * scale), 8 * scale, plusGlow);
    canvas.drawCircle(
      Offset(x, formY - 8 * scale),
      7 * scale,
      Paint()..color = const Color(0xFF12192B),
    );
    canvas.drawCircle(
      Offset(x, formY - 8 * scale),
      7 * scale,
      Paint()
        ..color = AppColors.primaryGreen.withOpacity(0.5)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1 * scale,
    );

    // Plus sign
    final plusPaint = Paint()
      ..color = AppColors.primaryGreen
      ..strokeWidth = 1.5 * scale
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(x - 4 * scale, formY - 8 * scale),
      Offset(x + 4 * scale, formY - 8 * scale),
      plusPaint,
    );
    canvas.drawLine(
      Offset(x, formY - 12 * scale),
      Offset(x, formY - 4 * scale),
      plusPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
