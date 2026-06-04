import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

// ─────────────────────────────────────────────────────────────────────────────
// FLOATING BOTTOM NAV — capsule-shaped, hovers over content. Each cell owns
// its own animated pill background; the active cell expands to fit its label
// while inactive cells collapse to icon-only. No overlay → labels can never
// overflow their pill.
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
      padding: EdgeInsets.fromLTRB(12, 8, 12, 12 + bottomInset),
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
    const double height = 60;
    return Container(
      height: height,
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      decoration: BoxDecoration(
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
      // Active cell grows to its content (icon + label); inactive shrinks to
      // an icon-only square. `AnimatedSize` smooths the layout shift so the
      // expansion feels like a single fluid motion across the whole bar.
      child: AnimatedSize(
        duration: const Duration(milliseconds: 320),
        curve: Curves.easeOutCubic,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: List.generate(items.length, (i) {
            final spec = items[i];
            return _NavCell(
              icon: spec.icon,
              label: spec.label,
              isActive: i == currentIndex,
              onTap: () => onTap(i),
            );
          }),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Single tap target. The cell hugs its content (icon, or icon+label when
// active) so the active pill is always exactly wide enough — label never
// overflows.
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
        scale: _pressed ? 0.9 : 1.0,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOut,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          padding: EdgeInsets.symmetric(
            horizontal: widget.isActive ? 14 : 10,
            vertical: 8,
          ),
          decoration: BoxDecoration(
            color: widget.isActive
                ? activeColor.withOpacity(0.14)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(40),
            border: Border.all(
              color: widget.isActive
                  ? activeColor.withOpacity(0.35)
                  : Colors.transparent,
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 1.0, end: widget.isActive ? 1.06 : 1.0),
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutBack,
                builder: (_, v, child) =>
                    Transform.scale(scale: v, child: child),
                child: Icon(widget.icon, size: 21, color: color),
              ),
              // Label only rendered for the active cell — FittedBox guarantees
              // it shrinks if the bar gets unusually narrow.
              if (widget.isActive)
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      widget.label,
                      style: TextStyle(
                        color: activeColor,
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.2,
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
