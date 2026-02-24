import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../constants/app_colors.dart';
import '../providers/session_provider.dart';
import '../screens/live_charging_screen.dart';
import '../screens/charger_detail_screen.dart';

class FeaturedStationCard extends StatefulWidget {
  final dynamic charger;

  const FeaturedStationCard({super.key, required this.charger});

  @override
  State<FeaturedStationCard> createState() => _FeaturedStationCardState();
}

class _FeaturedStationCardState extends State<FeaturedStationCard> {
  bool _isFavourite = false;

  dynamic get charger => widget.charger;

  String _getStatusLabel(String availability, String status) {
    if (status != 'online') return 'Offline';
    switch (availability) {
      case 'available':
      case 'preparing':
        return 'Available';
      case 'charging':
        return 'Charging';
      case 'finishing':
        return 'Finishing';
      case 'faulted':
        return 'Faulted';
      default:
        return 'Unavailable';
    }
  }

  Color _getStatusColor(String availability, String status) {
    if (status != 'online') return Colors.grey;
    switch (availability) {
      case 'available':
      case 'preparing':
        return AppColors.primaryGreen;
      case 'charging':
        return Colors.orange;
      case 'faulted':
        return AppColors.error;
      default:
        return Colors.grey;
    }
  }

  Future<void> _startCharging(BuildContext context) async {
    final chargerId = charger['charge_point_id'] as String?;
    if (chargerId == null) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Center(
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.cardBackground,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: AppColors.primaryGreen),
              const SizedBox(height: 16),
              Text('Starting charging...', style: TextStyle(color: AppColors.textPrimary)),
            ],
          ),
        ),
      ),
    );

    try {
      final sessionProvider = Provider.of<SessionProvider>(context, listen: false);
      await sessionProvider.startCharging(chargerId, 1);
      if (context.mounted) Navigator.of(context).pop();
      await Future.delayed(const Duration(seconds: 1));
      final activeSession = sessionProvider.activeSession;
      if (context.mounted) {
        if (activeSession != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Charging started successfully!'), backgroundColor: AppColors.primaryGreen, duration: Duration(seconds: 2)),
          );
          Navigator.of(context).push(MaterialPageRoute(builder: (_) => const LiveChargingScreen()));
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to start charging. Please try again.'), backgroundColor: AppColors.error, duration: Duration(seconds: 3)),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}'), backgroundColor: AppColors.error, duration: const Duration(seconds: 3)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id']?.toString() ?? 'Charging Station';
    final status = charger['status']?.toString() ?? 'unknown';
    final availability = charger['availability']?.toString() ?? 'unknown';
    final vendor = charger['vendor']?.toString() ?? '';
    final model = charger['model']?.toString() ?? '';
    final firmware = charger['firmware_version']?.toString() ?? '';
    final isAvailable = status == 'online' && (availability == 'available' || availability == 'preparing');
    final isCharging = availability == 'charging';
    final statusLabel = _getStatusLabel(availability, status);
    final statusColor = _getStatusColor(availability, status);
    
    return GestureDetector(
      onTap: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger as Map<String, dynamic>))),
      child: Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: statusColor.withOpacity(0.25), width: 1),
        boxShadow: [
            BoxShadow(color: statusColor.withOpacity(0.08), blurRadius: 16, spreadRadius: 0),
        ],
      ),
      child: Padding(
          padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
              // Top row: Icon + Name + Status + Bookmark
            Row(
              children: [
                  // Charger icon
                Container(
                    width: 48,
                    height: 48,
                  decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [statusColor, statusColor.withOpacity(0.7)]),
                      borderRadius: BorderRadius.circular(14),
                  ),
                    child: const Icon(Icons.ev_station_rounded, color: Colors.white, size: 24),
                ),
                  const SizedBox(width: 12),
                  // Name & vendor
                Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(name,
                            style: const TextStyle(color: AppColors.textPrimary, fontSize: 17, fontWeight: FontWeight.bold),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
                        if (vendor.isNotEmpty || model.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                  child: Text(
                              [vendor, model].where((s) => s.isNotEmpty).join(' · '),
                              style: TextStyle(color: AppColors.textLight, fontSize: 12),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                    ),
                  ),
                  // Status badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: statusColor.withOpacity(0.4)),
                  ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 7,
                          height: 7,
                          decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                        ),
                        const SizedBox(width: 5),
                        Text(statusLabel,
                            style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 4),
                  // Bookmark
                  GestureDetector(
                    onTap: () {
                    setState(() => _isFavourite = !_isFavourite);
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(_isFavourite ? 'Added to favourites' : 'Removed from favourites'),
                        backgroundColor: AppColors.primaryGreen,
                        duration: const Duration(seconds: 1),
                      ),
                    );
                  },
                    child: Icon(
                      _isFavourite ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                      color: _isFavourite ? AppColors.primaryGreen : AppColors.textLight,
                      size: 22,
                    ),
                ),
              ],
            ),
              const SizedBox(height: 14),

              // Info chips row - real data
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                  if (firmware.isNotEmpty) _infoTag(Icons.memory_rounded, 'FW: $firmware'),
                  _infoTag(Icons.power_rounded, status == 'online' ? 'Online' : 'Offline'),
                  _infoTag(Icons.access_time_rounded, availability),
                ],
            ),
              const SizedBox(height: 14),

              // Action button
            SizedBox(
              width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: isAvailable
                      ? () => _startCharging(context)
                      : () => Navigator.push(context,
                          MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger as Map<String, dynamic>))),
                  icon: Icon(
                    isAvailable
                        ? Icons.bolt_rounded
                        : isCharging
                            ? Icons.battery_charging_full_rounded
                            : Icons.info_outline_rounded,
                    size: 18,
                ),
                  label: Text(
                  isAvailable 
                      ? 'Start Charging' 
                      : isCharging
                            ? 'In Use · View Details'
                            : 'View Details',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isAvailable ? AppColors.primaryGreen : AppColors.surface,
                    foregroundColor: isAvailable ? AppColors.background : AppColors.textSecondary,
                    padding: const EdgeInsets.symmetric(vertical: 13),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    elevation: isAvailable ? 2 : 0,
                ),
              ),
            ),
          ],
        ),
      ),
      ),
    );
  }

  Widget _infoTag(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.borderLight, width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: AppColors.primaryGreen.withOpacity(0.7)),
          const SizedBox(width: 4),
          Text(text, style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
