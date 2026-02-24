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
          // Logo
          Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
              Image.asset(
                'assets/images/logo.png',
                height: 58,
                width: 58,
                fit: BoxFit.contain,
              ),
              const SizedBox(width: 12),
              const Text(
                        'PlagSini',
                        style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 26,
                          fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                      ),
                    ),
                  ],
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
