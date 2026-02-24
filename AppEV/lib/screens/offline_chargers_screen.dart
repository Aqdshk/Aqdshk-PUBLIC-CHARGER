import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/charger_provider.dart';
import '../constants/app_colors.dart';

class OfflineChargersScreen extends StatelessWidget {
  const OfflineChargersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Offline Chargers', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: Column(
        children: [
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.orange.withOpacity(0.08),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.orange.withOpacity(0.2)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: Colors.orange.withOpacity(0.15), borderRadius: BorderRadius.circular(12)),
                  child: const Icon(Icons.build, color: Colors.orange, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Under Maintenance', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text('These chargers are currently offline for maintenance or repair.', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          
          Expanded(
            child: Consumer<ChargerProvider>(
              builder: (context, chargerProvider, _) {
                if (chargerProvider.isLoading) {
                  return const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen));
                }
                final offlineChargers = chargerProvider.nearbyChargers.where((c) {
                  final status = c['status']?.toString().toLowerCase() ?? '';
                  final availability = c['availability']?.toString().toLowerCase() ?? '';
                  return status == 'offline' || availability == 'unavailable' || availability == 'faulted';
                }).toList();
                if (offlineChargers.isEmpty) return _buildEmptyState();
                return ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: offlineChargers.length,
                  itemBuilder: (context, index) => _OfflineChargerCard(charger: offlineChargers[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.1), shape: BoxShape.circle),
              child: Icon(Icons.check_circle_outline, size: 64, color: AppColors.primaryGreen),
            ),
            const SizedBox(height: 24),
            Text('All Chargers Online!', style: TextStyle(color: AppColors.textPrimary, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Great news! All nearby chargers are currently operational.', textAlign: TextAlign.center, style: TextStyle(color: AppColors.textLight, fontSize: 14)),
          ],
        ),
      ),
    );
  }
}

class _OfflineChargerCard extends StatelessWidget {
  final Map<String, dynamic> charger;

  const _OfflineChargerCard({required this.charger});

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id'] ?? 'Unknown';
    final availability = charger['availability']?.toString() ?? 'offline';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.orange.withOpacity(0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Colors.orange.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
              child: const Icon(Icons.ev_station, color: Colors.orange, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(color: Colors.orange.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
                        child: Text(availability == 'faulted' ? 'FAULTED' : 'OFFLINE', style: const TextStyle(color: Colors.orange, fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 8),
                      Text('• 2.5 km', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                    ],
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Icon(Icons.notifications_outlined, color: AppColors.primaryGreen),
                const SizedBox(height: 4),
                Text('Notify me', style: TextStyle(color: AppColors.primaryGreen, fontSize: 11, fontWeight: FontWeight.w500)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
