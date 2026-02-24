import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'nav_item.dart';

class BottomNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  const BottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        border: Border(
          top: BorderSide(
            color: AppColors.primaryGreen.withOpacity(0.15),
            width: 1,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.primaryGreen.withOpacity(0.05),
            blurRadius: 20,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            NavItem(
              icon: Icons.bolt_rounded,
              label: 'PlagSini Explore',
              isActive: currentIndex == 0,
              onTap: () => onTap(0),
            ),
            NavItem(
              icon: Icons.map_rounded,
              label: 'Maps',
              isActive: currentIndex == 1,
              onTap: () => onTap(1),
            ),
            NavItem(
              icon: Icons.qr_code_scanner_rounded,
              label: 'Scan',
              isActive: currentIndex == 2,
              onTap: () => onTap(2),
            ),
            NavItem(
              icon: Icons.card_giftcard_rounded,
              label: 'Rewards',
              isActive: currentIndex == 3,
              onTap: () => onTap(3),
            ),
            NavItem(
              icon: Icons.person_rounded,
              label: 'Me',
              isActive: currentIndex == 4,
              onTap: () => onTap(4),
            ),
          ],
        ),
      ),
      ),
    );
  }
}
