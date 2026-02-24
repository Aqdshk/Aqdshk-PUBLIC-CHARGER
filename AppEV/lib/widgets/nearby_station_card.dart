import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../screens/charger_detail_screen.dart';

class NearbyStationCard extends StatelessWidget {
  final dynamic charger;

  const NearbyStationCard({super.key, required this.charger});

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id']?.toString() ?? 'Station';
    final status = charger['status']?.toString() ?? 'unknown';
    final availability = charger['availability']?.toString() ?? 'unknown';
    final vendor = charger['vendor']?.toString() ?? '';
    final isOnline = status == 'online';
    final isAvailable = isOnline && (availability == 'available' || availability == 'preparing');
    final isCharging = availability == 'charging';

    // Status config
    Color dotColor;
    String statusText;
    if (!isOnline) {
      dotColor = Colors.grey;
      statusText = 'Offline';
    } else if (isAvailable) {
      dotColor = AppColors.primaryGreen;
      statusText = 'Available';
    } else if (isCharging) {
      dotColor = Colors.orange;
      statusText = 'In Use';
    } else {
      dotColor = Colors.grey;
      statusText = availability;
    }
    
    return GestureDetector(
      onTap: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger as Map<String, dynamic>))),
      child: Container(
        width: 170,
      margin: const EdgeInsets.only(right: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isAvailable ? AppColors.primaryGreen.withOpacity(0.2) : AppColors.borderLight, width: 1),
          ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // Top: Icon + Status dot
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [dotColor, dotColor.withOpacity(0.7)]),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.ev_station_rounded, color: Colors.white, size: 18),
                ),
                const Spacer(),
                // Status dot
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: dotColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(width: 6, height: 6, decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle)),
                          const SizedBox(width: 4),
                      Text(statusText,
                          style: TextStyle(color: dotColor, fontSize: 10, fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Name
            Text(name,
                style: const TextStyle(color: AppColors.textPrimary, fontSize: 13, fontWeight: FontWeight.bold),
                maxLines: 1,
                overflow: TextOverflow.ellipsis),
            // Vendor
            if (vendor.isNotEmpty)
              Text(vendor,
                  style: TextStyle(color: AppColors.textLight, fontSize: 10),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis),
          ],
      ),
      ),
    );
  }
}
