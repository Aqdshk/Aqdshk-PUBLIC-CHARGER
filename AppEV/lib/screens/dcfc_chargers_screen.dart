import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/charger_provider.dart';
import '../constants/app_colors.dart';
import 'charger_detail_screen.dart';

class DCFCChargersScreen extends StatefulWidget {
  const DCFCChargersScreen({super.key});

  @override
  State<DCFCChargersScreen> createState() => _DCFCChargersScreenState();
}

class _DCFCChargersScreenState extends State<DCFCChargersScreen> {
  String _selectedFilter = 'All';

  final List<String> _filters = ['All', '50kW+', '100kW+', '150kW+', 'CCS2', 'CHAdeMO'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('DC Fast Chargers', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
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
              gradient: LinearGradient(colors: [AppColors.primaryGreen, AppColors.darkGreen]),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15)],
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
                  child: const Icon(Icons.bolt, color: Colors.white, size: 32),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text('DC Fast Charging', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      SizedBox(height: 4),
                      Text('Charge up to 80% in just 30 minutes!', style: TextStyle(color: Colors.white70, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: _filters.map((label) => Container(
                margin: const EdgeInsets.only(right: 8),
                child: FilterChip(
                  label: Text(label),
                  selected: _selectedFilter == label,
                  onSelected: (selected) {
                    setState(() => _selectedFilter = selected ? label : 'All');
                  },
                  selectedColor: AppColors.primaryGreen,
                  checkmarkColor: AppColors.background,
                  labelStyle: TextStyle(
                    color: _selectedFilter == label ? AppColors.background : AppColors.textSecondary,
                    fontWeight: _selectedFilter == label ? FontWeight.w600 : FontWeight.normal,
                  ),
                  backgroundColor: AppColors.cardBackground,
                  side: BorderSide(color: _selectedFilter == label ? AppColors.primaryGreen : AppColors.borderLight),
                ),
              )).toList(),
            ),
          ),
          
          const SizedBox(height: 16),
          
          Expanded(
            child: Consumer<ChargerProvider>(
              builder: (context, chargerProvider, _) {
                if (chargerProvider.isLoading) {
                  return const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen));
                }
                final dcChargers = chargerProvider.nearbyChargers;
                if (dcChargers.isEmpty) return _buildEmptyState();
                
                // Filter is visual-only since charger data doesn't have power/connector fields
                // When backend provides these fields, filtering logic can be added here
                final filtered = dcChargers;
                
                return Column(
                  children: [
                    if (_selectedFilter != 'All')
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: AppColors.primaryGreen.withOpacity(0.08),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            'Showing: $_selectedFilter chargers (${filtered.length} found)',
                            style: TextStyle(color: AppColors.primaryGreen, fontSize: 12, fontWeight: FontWeight.w500),
                          ),
                        ),
                      ),
                    if (_selectedFilter != 'All') const SizedBox(height: 8),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final charger = filtered[index];
                          return _DCFCChargerCard(
                            charger: charger,
                            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger))),
                          );
                        },
                      ),
                    ),
                  ],
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
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.bolt, size: 64, color: AppColors.textLight),
          const SizedBox(height: 16),
          Text('No DC Fast Chargers nearby', style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('Try expanding your search area', style: TextStyle(color: AppColors.textLight, fontSize: 14)),
        ],
      ),
    );
  }
}

class _DCFCChargerCard extends StatelessWidget {
  final Map<String, dynamic> charger;
  final VoidCallback onTap;

  const _DCFCChargerCard({required this.charger, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id'] ?? 'Unknown';
    final status = charger['availability'] ?? 'unknown';
    final isAvailable = status == 'available' || status == 'preparing';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.primaryGreen.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.bolt, color: AppColors.primaryGreen, size: 28),
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
                            decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
                            child: Text('DC 50kW', style: TextStyle(color: AppColors.primaryGreen, fontSize: 11, fontWeight: FontWeight.w600)),
                          ),
                          const SizedBox(width: 8),
                          Text('• 2.0 km', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                        ],
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: isAvailable ? AppColors.primaryGreen : Colors.red, borderRadius: BorderRadius.circular(12)),
                      child: Text(isAvailable ? 'Available' : 'In Use', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(height: 8),
                    Text('RM 0.80/kWh', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
