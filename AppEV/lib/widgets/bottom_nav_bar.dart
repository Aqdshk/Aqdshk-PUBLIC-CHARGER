import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

// ─────────────────────────────────────────────────────────────────────────────
// FLOATING BOTTOM NAV — capsule-shaped, hovers over content with an animated
// pill that slides between active items (GoCar / Tesla-style).
//
// Public API unchanged: pass [currentIndex] + [onTap]. Scaffold should set
// `extendBody: true` so body content shows through behind the bar.
// ─────────────────────────────────────────────────────────────────────────────

class BottomNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  static const List<_NavSpec> _items = [
    _NavSpec(icon: Icons.bolt_rounded, label: 'Explore'),
    _NavSpec(icon: Icons.map_rounded, label: 'Maps'),
    _NavSpec(icon: Icons.qr_code_scanner_rounded, label: 'Scan'),
    _NavSpec(icon: Icons.card_giftcard_rounded, label: 'Rewards'),
    _NavSpec(icon: Icons.person_rounded, label: 'Me'),
  ];

  const BottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewPaddingOf(context).bottom;
    return Padding(
      // Floating margin around the capsule. Adds the device safe-area on top
      // so the pill never sits under the home indicator.
      padding: EdgeInsets.fromLTRB(16, 8, 16, 12 + bottomInset),
      child: _FloatingBar(
        currentIndex: currentIndex,
        items: _items,
        onTap: onTap,
      ),
    );
  }
}

class _NavSpec {
  final IconData icon;
  final String label;
  const _NavSpec({required this.icon, required this.label});
}

class _FloatingBar extends StatelessWidget {
  final int currentIndex;
  final List<_NavSpec> items;
  final ValueChanged<int> onTap;

  const _FloatingBar({
    required this.currentIndex,
    required this.items,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    const double height = 64;
    return Container(
      height: height,
      decoration: BoxDecoration(
        // Subtle vertical gradient — keeps the bar from looking flat-dead
        // against AMOLED black.
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF181A20), Color(0xFF101216)],
        ),
        borderRadius: BorderRadius.circular(height / 2),
        border: Border.all(color: Colors.white.withOpacity(0.06), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.45),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
          BoxShadow(
            color: AppColors.primaryGreen.withOpacity(0.08),
            blurRadius: 30,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: LayoutBuilder(
        builder: (context, c) {
          final double slot = c.maxWidth / items.length;
          // Active pill: slightly inset from slot edges so neighbours breathe.
          const double pillPadH = 8;
          const double pillPadV = 8;
          return Stack(
            children: [
              // Sliding active pill — the headline animation.
              AnimatedPositioned(
                duration: const Duration(milliseconds: 380),
                curve: Curves.easeOutCubic,
                left: slot * currentIndex + pillPadH,
                top: pillPadV,
                bottom: pillPadV,
                width: slot - pillPadH * 2,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: AppColors.primaryGreen.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(40),
                    border: Border.all(
                      color: AppColors.primaryGreen.withOpacity(0.35),
                      width: 1,
                    ),
                  ),
                ),
              ),
              // Foreground tap targets (icon + label).
              Row(
                children: List.generate(items.length, (i) {
                  final spec = items[i];
                  return Expanded(
                    child: _NavCell(
                      icon: spec.icon,
                      label: spec.label,
                      isActive: i == currentIndex,
                      onTap: () => onTap(i),
                    ),
                  );
                }),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Single tap target. Uses an AnimatedScale on press for tactile feedback and
// AnimatedDefaultTextStyle / TweenAnimationBuilder for the active→idle morph.
// ─────────────────────────────────────────────────────────────────────────────
class _NavCell extends StatefulWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _NavCell({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  State<_NavCell> createState() => _NavCellState();
}

class _NavCellState extends State<_NavCell> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final activeColor = AppColors.primaryGreen;
    final idleColor = Colors.white.withOpacity(0.55);
    final color = widget.isActive ? activeColor : idleColor;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => setState(() => _pressed = true),
      onTapCancel: () => setState(() => _pressed = false),
      onTapUp: (_) => setState(() => _pressed = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _pressed ? 0.88 : 1.0,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOut,
        child: Center(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 1.0, end: widget.isActive ? 1.08 : 1.0),
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutBack,
                builder: (_, v, child) =>
                    Transform.scale(scale: v, child: child),
                child: Icon(widget.icon, size: 22, color: color),
              ),
              // Label only renders for the active item — collapses cleanly
              // with an animated width so the pill stays compact.
              ClipRect(
                child: AnimatedAlign(
                  alignment: Alignment.centerLeft,
                  duration: const Duration(milliseconds: 320),
                  curve: Curves.easeOutCubic,
                  widthFactor: widget.isActive ? 1.0 : 0.0,
                  child: AnimatedOpacity(
                    opacity: widget.isActive ? 1.0 : 0.0,
                    duration: const Duration(milliseconds: 220),
                    child: Padding(
                      padding: const EdgeInsets.only(left: 6),
                      child: Text(
                        widget.label,
                        style: TextStyle(
                          color: activeColor,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
