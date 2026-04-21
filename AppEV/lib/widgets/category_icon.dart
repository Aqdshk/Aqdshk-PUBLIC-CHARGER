import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class CategoryIcon extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? subLabel;
  final String? badge;
  final VoidCallback onTap;

  const CategoryIcon({
    super.key,
    required this.icon,
    required this.label,
    this.subLabel,
    this.badge,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final tileRadius = 14.0;
          final iconInner = constraints.maxWidth * 0.24;
          return Container(
            decoration: BoxDecoration(
              color: AppColors.cardBackground,
              borderRadius: BorderRadius.circular(tileRadius),
              border: Border.all(
                color: AppColors.borderLight,
                width: 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.primaryGreen.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(11),
                        border: Border.all(
                          color: AppColors.primaryGreen.withOpacity(0.35),
                          width: 1.2,
                        ),
                      ),
                      child: Icon(
                        icon,
                        color: AppColors.primaryGreen,
                        size: iconInner,
                      ),
                    ),
                    if (badge != null)
                      Positioned(
                        right: -2,
                        top: -2,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                          decoration: BoxDecoration(
                            color: Color(0xFFFF006E),
                            borderRadius: BorderRadius.all(Radius.circular(999)),
                          ),
                          child: Text(
                            badge!,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 8,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                SizedBox(height: 8),
                Text(
                  label,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (subLabel != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      subLabel!,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: AppColors.textLight,
                        fontSize: 9.5,
                      ),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
