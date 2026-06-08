import 'dart:async';
import 'package:flutter/material.dart';
import 'home_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
// SPLASH SCREEN — Joycharge-style. Full-bleed EV-and-charger photo, soft
// blue gradient overlay for legibility, big welcome headline, skip pill
// top-right, glowing arrow bottom centre to advance. Falls forward to the
// home screen on tap or after a 4-second auto-timeout.
// ─────────────────────────────────────────────────────────────────────────────

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim;
  Timer? _autoAdvance;
  int _countdown = 4;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
    // Auto-advance to home after countdown — feels like the GoCar/Joycharge
    // splash: read for a beat, then we go.
    _autoAdvance = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      setState(() => _countdown--);
      if (_countdown <= 0) {
        t.cancel();
        _navigateToHome();
      }
    });
  }

  @override
  void dispose() {
    _autoAdvance?.cancel();
    _anim.dispose();
    super.dispose();
  }

  void _navigateToHome() {
    if (!mounted) return;
    _autoAdvance?.cancel();
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const HomeScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 400),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A1626),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ── Hero photo (full bleed) ────────────────────────────────────
          // The photo is the ENTIRE backdrop. errorBuilder falls back to a
          // plain gradient if the asset somehow fails to load.
          Image.asset(
            'assets/images/splash_hero.jpg',
            fit: BoxFit.cover,
            alignment: Alignment.center,
            errorBuilder: (_, __, ___) => Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF1B2A4B), Color(0xFF0A1626)],
                ),
              ),
            ),
          ),
          // ── Tint overlay ───────────────────────────────────────────────
          // Cool blue scrim ties the photo to the brand and gives the white
          // text safe contrast across any image variation.
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xCC0F2236),  // ~80% top
                  Color(0x880F2236),  // ~50% middle
                  Color(0xEE07101D),  // ~93% bottom for arrow legibility
                ],
                stops: [0.0, 0.45, 1.0],
              ),
            ),
          ),

          // ── SKIP pill (top right) ──────────────────────────────────────
          Positioned(
            top: mq.padding.top + 14,
            right: 20,
            child: GestureDetector(
              onTap: _navigateToHome,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white.withOpacity(0.20)),
                ),
                child: Text(
                  '$_countdown s',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.3,
                  ),
                ),
              ),
            ),
          ),

          // ── Headline (top-left) ────────────────────────────────────────
          Positioned(
            top: mq.padding.top + 70,
            left: 24,
            right: 24,
            child: FadeTransition(
              opacity: _anim,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, -0.08),
                  end: Offset.zero,
                ).animate(CurvedAnimation(parent: _anim, curve: Curves.easeOutCubic)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Welcome to\nPlagSini',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 38,
                        fontWeight: FontWeight.w800,
                        height: 1.1,
                        letterSpacing: -1.0,
                      ),
                    ),
                    const SizedBox(height: 10),
                    // Hairline divider for that Joycharge editorial vibe.
                    Container(
                      height: 1,
                      color: Colors.white.withOpacity(0.35),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      "Malaysia's smart EV charging network.",
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.78),
                        fontSize: 14,
                        fontWeight: FontWeight.w400,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // ── Arrow button (bottom-centre) ───────────────────────────────
          Positioned(
            bottom: mq.padding.bottom + 36,
            left: 0,
            right: 0,
            child: Center(
              child: FadeTransition(
                opacity: _anim,
                child: GestureDetector(
                  onTap: _navigateToHome,
                  child: _PulsingArrow(),
                ),
              ),
            ),
          ),

          // ── Brand mark (top-left, small) ──────────────────────────────
          Positioned(
            top: mq.padding.top + 14,
            left: 20,
            child: FadeTransition(
              opacity: _anim,
              child: Image.asset(
                'assets/images/plagsini_logo.png',
                height: 36,
                width: 36,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Pulsing chevron — subtle "tap to continue" affordance ────────────────────
class _PulsingArrow extends StatefulWidget {
  @override
  State<_PulsingArrow> createState() => _PulsingArrowState();
}

class _PulsingArrowState extends State<_PulsingArrow>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, __) {
        // Pulse alpha + slight scale so the button breathes without
        // feeling busy.
        final t = _pulse.value;
        return Container(
          width: 60,
          height: 60,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withOpacity(0.10 + t * 0.05),
            border: Border.all(
              color: Colors.white.withOpacity(0.35 + t * 0.25),
              width: 1.2,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.white.withOpacity(0.08 + t * 0.10),
                blurRadius: 20 + t * 10,
              ),
            ],
          ),
          child: Transform.scale(
            scale: 1.0 + t * 0.04,
            child: const Icon(
              Icons.arrow_forward_ios_rounded,
              color: Colors.white,
              size: 22,
            ),
          ),
        );
      },
    );
  }
}
