import 'dart:math';
import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'home_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _masterController;
  late AnimationController _particleController;
  late AnimationController _pulseController;
  late AnimationController _textController;

  // Animations
  late Animation<double> _carSlide;
  late Animation<double> _carOpacity;
  late Animation<double> _stationOpacity;
  late Animation<double> _cableProgress;
  late Animation<double> _sparkFlash;
  late Animation<double> _batteryFill;
  late Animation<double> _energyGlow;
  late Animation<double> _textOpacity;
  late Animation<double> _textSlide;
  late Animation<double> _fadeOut;

  final List<_EnergyParticle> _particles = [];
  final _random = Random();

  @override
  void initState() {
    super.initState();

    // Master timeline: 4 seconds
    _masterController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 4000),
    );

    // Particle loop
    _particleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..addListener(() {
        _updateParticles();
      });

    // Pulse glow loop
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    // Text reveal
    _textController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );

    // Define timeline segments
    _carSlide = Tween<double>(begin: -1.0, end: 0.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.0, 0.25, curve: Curves.easeOutCubic),
      ),
    );

    _carOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.0, 0.15, curve: Curves.easeIn),
      ),
    );

    _stationOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.05, 0.20, curve: Curves.easeIn),
      ),
    );

    _cableProgress = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.25, 0.45, curve: Curves.easeInOut),
      ),
    );

    _sparkFlash = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.44, 0.55, curve: Curves.easeOut),
      ),
    );

    _batteryFill = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.50, 0.80, curve: Curves.easeInOut),
      ),
    );

    _energyGlow = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.48, 0.60, curve: Curves.easeIn),
      ),
    );

    _textOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _textController,
        curve: Curves.easeOut,
      ),
    );

    _textSlide = Tween<double>(begin: 20.0, end: 0.0).animate(
      CurvedAnimation(
        parent: _textController,
        curve: Curves.easeOutCubic,
      ),
    );

    _fadeOut = Tween<double>(begin: 1.0, end: 0.0).animate(
      CurvedAnimation(
        parent: _masterController,
        curve: const Interval(0.90, 1.0, curve: Curves.easeIn),
      ),
    );

    _masterController.addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        _navigateToHome();
      }
    });

    _masterController.addListener(() {
      // Start particles when cable connects
      if (_masterController.value >= 0.45 && !_particleController.isAnimating) {
        _particleController.repeat();
        _pulseController.repeat(reverse: true);
      }
      // Start text when battery starts filling
      if (_masterController.value >= 0.65 && !_textController.isAnimating) {
        _textController.forward();
      }
    });

    // Start animation
    _masterController.forward();
  }

  void _updateParticles() {
    setState(() {
      // Add new particles
      if (_particles.length < 15) {
        _particles.add(_EnergyParticle(
          progress: 0.0,
          speed: 0.02 + _random.nextDouble() * 0.03,
          offset: (_random.nextDouble() - 0.5) * 8,
          size: 2 + _random.nextDouble() * 3,
          opacity: 0.6 + _random.nextDouble() * 0.4,
        ));
      }

      // Update existing particles
      for (var p in _particles) {
        p.progress += p.speed;
      }

      // Remove dead particles
      _particles.removeWhere((p) => p.progress > 1.0);
    });
  }

  void _navigateToHome() {
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (context, animation, secondaryAnimation) =>
            const HomeScreen(),
        transitionsBuilder: (context, animation, secondaryAnimation, child) {
          return FadeTransition(opacity: animation, child: child);
        },
        transitionDuration: const Duration(milliseconds: 500),
      ),
    );
  }

  @override
  void dispose() {
    _masterController.dispose();
    _particleController.dispose();
    _pulseController.dispose();
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0A1A),
      body: AnimatedBuilder(
        animation: Listenable.merge([
          _masterController,
          _particleController,
          _pulseController,
          _textController,
        ]),
        builder: (context, child) {
          return Opacity(
            opacity: _fadeOut.value,
            child: Stack(
              children: [
                // Background gradient
                _buildBackground(),

                // Main content — logo above, car scene below
                Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Brand text (logo + Plag Sini) ABOVE the car
                      Transform.translate(
                        offset: Offset(0, _textSlide.value),
                        child: Opacity(
                          opacity: _textOpacity.value,
                          child: _buildBrandText(),
                        ),
                      ),

                      const SizedBox(height: 24),

                      // Car animation scene
                      SizedBox(
                        width: 340,
                        height: 240,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            // Ground line / road
                            Positioned(
                              bottom: 40,
                              left: 0,
                              right: 0,
                              child: _buildRoad(),
                            ),

                            // Charging Station
                            Positioned(
                              right: 30,
                              bottom: 40,
                              child: Opacity(
                                opacity: _stationOpacity.value,
                                child: _buildChargingStation(),
                              ),
                            ),

                            // Cable
                            if (_cableProgress.value > 0)
                              Positioned(
                                bottom: 40,
                                left: 0,
                                right: 0,
                                child: CustomPaint(
                                  size: const Size(340, 120),
                                  painter: _CablePainter(
                                    progress: _cableProgress.value,
                                    particles: _particles,
                                    energyGlow: _energyGlow.value,
                                    pulseValue: _pulseController.value,
                                  ),
                                ),
                              ),

                            // Spark flash at connection (car charging port)
                            if (_sparkFlash.value > 0 && _sparkFlash.value < 1)
                              Positioned(
                                left: 151,
                                bottom: 68,
                                child: _buildSpark(),
                              ),

                            // Car
                            Positioned(
                              left: 20,
                              bottom: 40,
                              child: Transform.translate(
                                offset: Offset(_carSlide.value * 100, 0),
                                child: Opacity(
                                  opacity: _carOpacity.value,
                                  child: _buildCar(),
                                ),
                              ),
                            ),

                            // Battery indicator on car
                            if (_batteryFill.value > 0)
                              Positioned(
                                left: 93 + (_carSlide.value * 100),
                                bottom: 118,
                                child: Opacity(
                                  opacity: _carOpacity.value,
                                  child: _buildBatteryIndicator(),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // Loading dots at the very bottom
                Positioned(
                  bottom: 40,
                  left: 0,
                  right: 0,
                  child: _buildLoadingDots(),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildBackground() {
    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -0.3),
          radius: 1.2,
          colors: [
            Color(0xFF0F1B2D),
            Color(0xFF0A0A1A),
            Color(0xFF050510),
          ],
        ),
      ),
      child: CustomPaint(
        size: Size.infinite,
        painter: _BackgroundParticlePainter(
          progress: _masterController.value,
        ),
      ),
    );
  }

  Widget _buildRoad() {
    return Column(
      children: [
        Container(
          height: 2,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Colors.transparent,
                AppColors.primaryGreen.withOpacity(0.15),
                AppColors.primaryGreen.withOpacity(0.3),
                AppColors.primaryGreen.withOpacity(0.15),
                Colors.transparent,
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        // Dashed center line
        ClipRect(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(17, (i) {
              return Container(
                width: 12,
                height: 1,
                margin: const EdgeInsets.symmetric(horizontal: 4),
                color: Colors.white.withOpacity(i % 2 == 0 ? 0.08 : 0.0),
              );
            }),
          ),
        ),
      ],
    );
  }

  Widget _buildChargingStation() {
    return SizedBox(
      width: 50,
      height: 100,
      child: CustomPaint(
        painter: _ChargingStationPainter(
          glowIntensity: _energyGlow.value,
          pulseValue: _pulseController.value,
        ),
      ),
    );
  }

  Widget _buildCar() {
    return SizedBox(
      width: 160,
      height: 70,
      child: CustomPaint(
        painter: _CarPainter(
          batteryLevel: _batteryFill.value,
          isCharging: _cableProgress.value >= 1.0,
        ),
      ),
    );
  }

  Widget _buildBatteryIndicator() {
    final percentage = (_batteryFill.value * 100).toInt();
    return Column(
      children: [
        // Battery percentage text
        Text(
          '$percentage%',
          style: TextStyle(
            color: _batteryFill.value < 0.3
                ? Colors.redAccent
                : _batteryFill.value < 0.7
                    ? Colors.orangeAccent
                    : AppColors.primaryGreen,
            fontSize: 11,
            fontWeight: FontWeight.bold,
            shadows: [
              Shadow(
                color: AppColors.primaryGreen.withOpacity(0.5),
                blurRadius: 8,
              ),
            ],
          ),
        ),
        const SizedBox(height: 2),
        // Small battery icon
        Container(
          width: 28,
          height: 12,
          decoration: BoxDecoration(
            border: Border.all(
              color: AppColors.primaryGreen.withOpacity(0.6),
              width: 1.5,
            ),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Padding(
            padding: const EdgeInsets.all(1.5),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: _batteryFill.value,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(1),
                  gradient: LinearGradient(
                    colors: _batteryFill.value < 0.3
                        ? [Colors.redAccent, Colors.red]
                        : _batteryFill.value < 0.7
                            ? [Colors.orangeAccent, Colors.orange]
                            : [AppColors.primaryGreen, AppColors.darkGreen],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primaryGreen.withOpacity(0.4),
                      blurRadius: 4,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSpark() {
    final sparkOpacity = (1.0 - _sparkFlash.value).clamp(0.0, 1.0);
    final sparkScale = 0.5 + _sparkFlash.value * 1.5;
    return Transform.scale(
      scale: sparkScale,
      child: Opacity(
        opacity: sparkOpacity,
        child: Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: AppColors.primaryGreen.withOpacity(0.8),
                blurRadius: 20,
                spreadRadius: 8,
              ),
              BoxShadow(
                color: Colors.white.withOpacity(0.6),
                blurRadius: 8,
                spreadRadius: 2,
              ),
            ],
            gradient: RadialGradient(
              colors: [
                Colors.white,
                AppColors.primaryGreen.withOpacity(0.8),
                Colors.transparent,
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBrandText() {
    return Column(
      children: [
        // Logo
        Image.asset(
          'assets/images/plagsini_logo.png',
          height: 80,
          fit: BoxFit.contain,
        ),
        const SizedBox(height: 12),
        ShaderMask(
          shaderCallback: (bounds) => LinearGradient(
            colors: [
              AppColors.primaryGreen,
              AppColors.primaryGreen.withOpacity(0.8),
              Colors.white,
              AppColors.primaryGreen,
            ],
            stops: const [0.0, 0.3, 0.5, 1.0],
          ).createShader(bounds),
          child: const Text(
            'Plag Sini',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              letterSpacing: 2,
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'EV Charging Platform',
          style: TextStyle(
            fontSize: 12,
            color: Colors.white.withOpacity(0.4),
            letterSpacing: 3,
            fontWeight: FontWeight.w300,
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingDots() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(3, (i) {
        final delay = i * 0.15;
        final progress = (_masterController.value * 3 + delay) % 1.0;
        final opacity = (sin(progress * pi)).clamp(0.2, 1.0);
        return Container(
          width: 5,
          height: 5,
          margin: const EdgeInsets.symmetric(horizontal: 3),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.primaryGreen.withOpacity(opacity),
            boxShadow: [
              BoxShadow(
                color: AppColors.primaryGreen.withOpacity(opacity * 0.5),
                blurRadius: 4,
              ),
            ],
          ),
        );
      }),
    );
  }
}

// ============================================================
// Energy Particle data
// ============================================================
class _EnergyParticle {
  double progress;
  double speed;
  double offset;
  double size;
  double opacity;

  _EnergyParticle({
    required this.progress,
    required this.speed,
    required this.offset,
    required this.size,
    required this.opacity,
  });
}

// ============================================================
// Car Painter
// ============================================================
class _CarPainter extends CustomPainter {
  final double batteryLevel;
  final bool isCharging;

  _CarPainter({required this.batteryLevel, required this.isCharging});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;

    // Car body - symmetric greenhouse (mirrored windshield & rear window)
    // Roof center at x=0.56, front and rear slopes are exact mirrors
    final bodyPath = Path();

    // Bottom of car
    bodyPath.moveTo(size.width * 0.05, size.height * 0.75);

    // Front bumper
    bodyPath.lineTo(size.width * 0.0, size.height * 0.65);
    bodyPath.quadraticBezierTo(
      size.width * 0.0, size.height * 0.55,
      size.width * 0.08, size.height * 0.50,
    );

    // Hood
    bodyPath.lineTo(size.width * 0.24, size.height * 0.45);

    // Windshield (steep slope up)
    bodyPath.quadraticBezierTo(
      size.width * 0.29, size.height * 0.42,
      size.width * 0.34, size.height * 0.22,
    );

    // Front roof transition
    bodyPath.quadraticBezierTo(
      size.width * 0.36, size.height * 0.15,
      size.width * 0.44, size.height * 0.12,
    );

    // Roof (flat)
    bodyPath.lineTo(size.width * 0.68, size.height * 0.12);

    // Rear roof transition (mirror of front: ctrl 0.36→0.76, end 0.34→0.78)
    bodyPath.quadraticBezierTo(
      size.width * 0.76, size.height * 0.15,
      size.width * 0.78, size.height * 0.22,
    );

    // Rear window (mirror of windshield: ctrl 0.29→0.83, end 0.24→0.88)
    bodyPath.quadraticBezierTo(
      size.width * 0.83, size.height * 0.42,
      size.width * 0.88, size.height * 0.45,
    );

    // Rear bumper
    bodyPath.lineTo(size.width * 0.95, size.height * 0.50);
    bodyPath.quadraticBezierTo(
      size.width * 0.97, size.height * 0.55,
      size.width * 0.97, size.height * 0.65,
    );
    bodyPath.lineTo(size.width * 0.93, size.height * 0.75);

    bodyPath.close();

    // Car body gradient
    paint.shader = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        const Color(0xFF2A3A4E),
        const Color(0xFF1A2535),
        const Color(0xFF0F1A28),
      ],
    ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    canvas.drawPath(bodyPath, paint);

    // Car body outline
    final outlinePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = isCharging
          ? const Color(0xFF00FF88).withOpacity(0.5)
          : const Color(0xFF4A6080).withOpacity(0.6);
    canvas.drawPath(bodyPath, outlinePaint);

    // Windows
    _drawWindows(canvas, size);

    // Wheels
    _drawWheel(canvas, Offset(size.width * 0.22, size.height * 0.75), 13);
    _drawWheel(canvas, Offset(size.width * 0.78, size.height * 0.75), 13);

    // Headlights
    _drawHeadlight(canvas, Offset(size.width * 0.02, size.height * 0.58), true);

    // Taillights
    _drawTaillight(canvas, Offset(size.width * 0.94, size.height * 0.53));

    // Charging port (right side, rear)
    if (isCharging) {
      final portPaint = Paint()
        ..color = const Color(0xFF00FF88).withOpacity(0.8)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
      canvas.drawCircle(
        Offset(size.width * 0.86, size.height * 0.42),
        3,
        portPaint,
      );
    }

    // Glow when charging
    if (isCharging && batteryLevel > 0) {
      final glowPaint = Paint()
        ..color = const Color(0xFF00FF88).withOpacity(0.05 + batteryLevel * 0.08)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 15);
      canvas.drawPath(bodyPath, glowPaint);
    }
  }

  void _drawWindows(Canvas canvas, Size size) {
    final windowPaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          const Color(0xFF1A3050).withOpacity(0.8),
          const Color(0xFF0D1F33).withOpacity(0.9),
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    // ---- Symmetric trapezoid windows around B-pillar (x=0.55) ----
    // Both: top width 0.10, bottom width 0.16, height 0.16→0.36
    // Angled side slope dx=0.06 over dy=0.20 — identical, mirrored

    // Front window (windshield) — angled on LEFT side
    final frontWindow = Path();
    frontWindow.moveTo(size.width * 0.38, size.height * 0.36);   // bottom-left (windshield base)
    frontWindow.lineTo(size.width * 0.44, size.height * 0.16);   // top-left (windshield top)
    frontWindow.lineTo(size.width * 0.54, size.height * 0.16);   // top-right (roofline)
    frontWindow.lineTo(size.width * 0.54, size.height * 0.36);   // bottom-right (B-pillar)
    frontWindow.close();
    canvas.drawPath(frontWindow, windowPaint);

    // Rear window — exact mirror, angled on RIGHT side
    final rearWindow = Path();
    rearWindow.moveTo(size.width * 0.56, size.height * 0.36);    // bottom-left (B-pillar)
    rearWindow.lineTo(size.width * 0.56, size.height * 0.16);    // top-left (roofline)
    rearWindow.lineTo(size.width * 0.66, size.height * 0.16);    // top-right (roofline)
    rearWindow.lineTo(size.width * 0.72, size.height * 0.36);    // bottom-right (C-pillar base)
    rearWindow.close();
    canvas.drawPath(rearWindow, windowPaint);

    // Window frame
    final framePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.5
      ..color = const Color(0xFF4A6080).withOpacity(0.3);
    canvas.drawPath(frontWindow, framePaint);
    canvas.drawPath(rearWindow, framePaint);
  }

  void _drawWheel(Canvas canvas, Offset center, double radius) {
    // Tire
    final tirePaint = Paint()
      ..style = PaintingStyle.fill
      ..color = const Color(0xFF1A1A2A);
    canvas.drawCircle(center, radius, tirePaint);

    // Rim
    final rimPaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = RadialGradient(
        colors: [
          const Color(0xFF4A5570),
          const Color(0xFF2A3340),
        ],
      ).createShader(
        Rect.fromCircle(center: center, radius: radius * 0.7),
      );
    canvas.drawCircle(center, radius * 0.7, rimPaint);

    // Hub
    final hubPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = const Color(0xFF3A4555);
    canvas.drawCircle(center, radius * 0.25, hubPaint);
  }

  void _drawHeadlight(Canvas canvas, Offset pos, bool front) {
    final lightPaint = Paint()
      ..color = const Color(0xFFFFE0A0).withOpacity(0.9)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
    canvas.drawCircle(pos, 3, lightPaint);

    final corePaint = Paint()..color = const Color(0xFFFFFFDD);
    canvas.drawCircle(pos, 1.5, corePaint);
  }

  void _drawTaillight(Canvas canvas, Offset pos) {
    final lightPaint = Paint()
      ..color = const Color(0xFFFF3344).withOpacity(0.7)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
    canvas.drawCircle(pos, 2.5, lightPaint);

    final corePaint = Paint()..color = const Color(0xFFFF5566).withOpacity(0.9);
    canvas.drawCircle(pos, 1.2, corePaint);
  }

  @override
  bool shouldRepaint(covariant _CarPainter oldDelegate) =>
      batteryLevel != oldDelegate.batteryLevel ||
      isCharging != oldDelegate.isCharging;
}

// ============================================================
// Charging Station Painter
// ============================================================
class _ChargingStationPainter extends CustomPainter {
  final double glowIntensity;
  final double pulseValue;

  _ChargingStationPainter({
    required this.glowIntensity,
    required this.pulseValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width * 0.5;

    // Station base
    final basePaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFF2A3A4E), Color(0xFF1A2535)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    final baseRect = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: Offset(cx, size.height * 0.55),
        width: 28,
        height: 55,
      ),
      const Radius.circular(6),
    );
    canvas.drawRRect(baseRect, basePaint);

    // Station outline
    final outlinePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = Color.lerp(
        const Color(0xFF4A6080).withOpacity(0.4),
        const Color(0xFF00FF88).withOpacity(0.6),
        glowIntensity,
      )!;
    canvas.drawRRect(baseRect, outlinePaint);

    // Screen on station
    final screenRect = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: Offset(cx, size.height * 0.42),
        width: 16,
        height: 12,
      ),
      const Radius.circular(2),
    );
    final screenPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = Color.lerp(
        const Color(0xFF0A1520),
        const Color(0xFF0A2A15),
        glowIntensity,
      )!;
    canvas.drawRRect(screenRect, screenPaint);

    // Lightning bolt icon on screen
    if (glowIntensity > 0) {
      final boltPaint = Paint()
        ..color = const Color(0xFF00FF88).withOpacity(glowIntensity)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round;

      final boltPath = Path();
      boltPath.moveTo(cx + 2, size.height * 0.38);
      boltPath.lineTo(cx - 1, size.height * 0.42);
      boltPath.lineTo(cx + 1, size.height * 0.42);
      boltPath.lineTo(cx - 2, size.height * 0.46);
      canvas.drawPath(boltPath, boltPaint);
    }

    // Status LED
    final ledColor = glowIntensity > 0
        ? Color.lerp(
            const Color(0xFF00FF88),
            const Color(0xFF00FF88).withOpacity(0.5),
            pulseValue,
          )!
        : const Color(0xFF4A6080).withOpacity(0.3);

    final ledPaint = Paint()
      ..color = ledColor
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2);
    canvas.drawCircle(Offset(cx, size.height * 0.33), 2.5, ledPaint);

    // Pillar/stand
    final pillarPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = const Color(0xFF1A2535);

    canvas.drawRect(
      Rect.fromCenter(
        center: Offset(cx, size.height * 0.88),
        width: 10,
        height: 15,
      ),
      pillarPaint,
    );

    // Ground plate
    final platePaint = Paint()
      ..style = PaintingStyle.fill
      ..color = const Color(0xFF2A3A4E);

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: Offset(cx, size.height * 0.97),
          width: 34,
          height: 6,
        ),
        const Radius.circular(3),
      ),
      platePaint,
    );

    // Glow effect
    if (glowIntensity > 0) {
      final glowPaint = Paint()
        ..color = const Color(0xFF00FF88).withOpacity(glowIntensity * 0.15)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12);
      canvas.drawRRect(baseRect, glowPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _ChargingStationPainter oldDelegate) =>
      glowIntensity != oldDelegate.glowIntensity ||
      pulseValue != oldDelegate.pulseValue;
}

// ============================================================
// Cable Painter (with energy particles)
// ============================================================
class _CablePainter extends CustomPainter {
  final double progress;
  final List<_EnergyParticle> particles;
  final double energyGlow;
  final double pulseValue;

  _CablePainter({
    required this.progress,
    required this.particles,
    required this.energyGlow,
    required this.pulseValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Cable from station (right) to car charging port (rear-right of car on left)
    // Layout: Car at left:20 w:160, Station at right:30 w:50 in 340px container
    // Station body left edge ≈ container x:271, cable exit mid-body
    // Car charging port at container x:161 (car left + 160*0.88)
    //
    // Cable canvas is 340×120 positioned at bottom:100 in the 400px stack.
    // Station body in cable coords: x≈271, y≈55-75
    // Car port in cable coords: x≈161, y≈82

    final startX = size.width * 0.795; // ~270 station left side
    final startY = size.height * 0.50;  // ~60 mid-upper station body
    final endX = size.width * 0.474;   // ~161 car charging port
    final endY = size.height * 0.68;   // ~82 car charging port height

    // Quadratic Bezier control point — cable droops DOWN naturally
    final cpX = (startX + endX) * 0.5;
    final cpY = size.height * 0.92; // ~110, near ground for visible droop

    // Calculate points along quadratic Bezier: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
    final points = <Offset>[];
    const segments = 40;
    final currentSegments = (segments * progress).toInt();

    for (int i = 0; i <= currentSegments; i++) {
      final t = i / segments;
      final mt = 1.0 - t;
      final x = mt * mt * startX + 2 * mt * t * cpX + t * t * endX;
      final y = mt * mt * startY + 2 * mt * t * cpY + t * t * endY;
      points.add(Offset(x, y));
    }

    if (points.length >= 2) {
      final drawPath = Path();
      drawPath.moveTo(points[0].dx, points[0].dy);
      for (int i = 1; i < points.length; i++) {
        drawPath.lineTo(points[i].dx, points[i].dy);
      }

      // Cable shadow
      final shadowPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 5
        ..strokeCap = StrokeCap.round
        ..color = Colors.black.withOpacity(0.3)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
      canvas.drawPath(drawPath, shadowPaint);

      // Cable body
      final cablePaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..strokeCap = StrokeCap.round
        ..color = const Color(0xFF2A3A4E);
      canvas.drawPath(drawPath, cablePaint);

      // Cable energy glow
      if (energyGlow > 0) {
        final glowPaint = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeCap = StrokeCap.round
          ..color = const Color(0xFF00FF88).withOpacity(energyGlow * 0.4 + pulseValue * 0.2)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
        canvas.drawPath(drawPath, glowPaint);
      }

      // Connector plug at car end
      if (progress >= 0.95) {
        final lastPoint = points.last;
        final nozzlePaint = Paint()
          ..style = PaintingStyle.fill
          ..color = const Color(0xFF3A4A5E);
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromCenter(center: lastPoint, width: 8, height: 6),
            const Radius.circular(2),
          ),
          nozzlePaint,
        );

        // Green glow at connection point
        if (energyGlow > 0) {
          final connGlow = Paint()
            ..color = const Color(0xFF00FF88).withOpacity(energyGlow * 0.5)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
          canvas.drawCircle(lastPoint, 4, connGlow);
        }
      }
    }

    // Draw energy particles precisely on the Bezier curve
    if (energyGlow > 0) {
      for (final particle in particles) {
        final t = particle.progress.clamp(0.0, 1.0);
        final mt = 1.0 - t;
        final px = mt * mt * startX + 2 * mt * t * cpX + t * t * endX;
        final py = mt * mt * startY + 2 * mt * t * cpY + t * t * endY;

        final particlePaint = Paint()
          ..color = const Color(0xFF00FF88).withOpacity(particle.opacity * energyGlow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, particle.size);

        canvas.drawCircle(
          Offset(px + particle.offset * 0.3, py + particle.offset * 0.2),
          particle.size,
          particlePaint,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _CablePainter oldDelegate) => true;
}

// ============================================================
// Background Particle Painter (ambient floating dots)
// ============================================================
class _BackgroundParticlePainter extends CustomPainter {
  final double progress;

  _BackgroundParticlePainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    final random = Random(42);

    for (int i = 0; i < 30; i++) {
      final baseX = random.nextDouble() * size.width;
      final baseY = random.nextDouble() * size.height;
      final drift = sin((progress * 2 * pi) + i * 0.5) * 10;
      final opacity = (sin((progress * 2 * pi) + i) * 0.3 + 0.3).clamp(0.05, 0.25);
      final radius = 1.0 + random.nextDouble() * 1.5;

      final paint = Paint()
        ..color = const Color(0xFF00FF88).withOpacity(opacity)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2);

      canvas.drawCircle(
        Offset(baseX + drift, baseY + drift * 0.5),
        radius,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _BackgroundParticlePainter oldDelegate) =>
      progress != oldDelegate.progress;
}
