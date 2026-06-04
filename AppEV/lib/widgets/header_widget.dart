import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'glowing_icon_button.dart';

class HeaderWidget extends StatelessWidget {
  final VoidCallback? onNotificationTap;

  const HeaderWidget({super.key, this.onNotificationTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Logo — Expanded so Flexible inside can shrink the brand name.
          Expanded(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
              Image.asset(
                'assets/images/logo.png',
                height: 48,
                width: 48,
                fit: BoxFit.contain,
              ),
              const SizedBox(width: 10),
              // Flexible so the brand name shrinks rather than overflowing on
              // narrow viewports (small phones, embedded webviews).
              const Flexible(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'PlagSini',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              ),
              ],
            ),
          ),
          GlowingIconButton(
            icon: Icons.notifications_outlined,
            onTap: onNotificationTap ?? () {},
            badge: '3',
          ),
        ],
      ),
    );
  }
}
