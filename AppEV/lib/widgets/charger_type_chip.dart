import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class ChargerTypeChip extends StatelessWidget {
  final String text;
  final bool isAvailable;

  const ChargerTypeChip(this.text, this.isAvailable, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isAvailable 
            ? AppColors.primaryGreen.withOpacity(0.12) 
            : Colors.orange.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isAvailable 
              ? AppColors.primaryGreen.withOpacity(0.4) 
              : Colors.orange.withOpacity(0.4),
          width: 1,
        ),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: isAvailable ? AppColors.primaryGreen : Colors.orange,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
