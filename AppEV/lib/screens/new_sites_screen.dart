import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'charger_detail_screen.dart';

class NewSitesScreen extends StatelessWidget {
  const NewSitesScreen({super.key});

  List<Map<String, dynamic>> get _newSites => [
    {'charge_point_id': 'PS-IOI-DC-01', 'name': 'IOI City Mall', 'location': 'Putrajaya', 'availability': 'available', 'added_date': '3 days ago', 'power': '150 kW DC', 'connectors': ['CCS2', 'CHAdeMO'], 'promo': '20% OFF first charge'},
    {'charge_point_id': 'PS-MID-AC-02', 'name': 'Mid Valley Megamall', 'location': 'Kuala Lumpur', 'availability': 'available', 'added_date': '1 week ago', 'power': '22 kW AC', 'connectors': ['Type 2'], 'promo': null},
    {'charge_point_id': 'PS-SUN-DC-03', 'name': 'Sunway Pyramid', 'location': 'Subang Jaya', 'availability': 'available', 'added_date': '2 weeks ago', 'power': '50 kW DC', 'connectors': ['CCS2'], 'promo': 'Free parking while charging'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('New Charging Sites', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: Column(
        children: [
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [AppColors.primaryGreen, AppColors.darkGreen]),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [BoxShadow(color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15)],
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
                  child: const Icon(Icons.new_releases, color: Colors.white, size: 32),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text('New This Month', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      SizedBox(height: 4),
                      Text('12 new charging stations added!', style: TextStyle(color: Colors.white70, fontSize: 12)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(20)),
                  child: Text('NEW', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ),
          
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                _FilterTab(label: 'All', isSelected: true),
                _FilterTab(label: 'This Week'),
                _FilterTab(label: 'This Month'),
                _FilterTab(label: 'Near Me'),
              ],
            ),
          ),
          
          const SizedBox(height: 16),
          
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _newSites.length,
              itemBuilder: (context, index) {
                final site = _newSites[index];
                return _NewSiteCard(
                  site: site,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: site))),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterTab extends StatelessWidget {
  final String label;
  final bool isSelected;

  const _FilterTab({required this.label, this.isSelected = false});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () {},
            borderRadius: BorderRadius.circular(20),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primaryGreen : AppColors.cardBackground,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: isSelected ? AppColors.primaryGreen : AppColors.borderLight),
              ),
              child: Center(
                child: Text(
                  label,
                  style: TextStyle(
                    color: isSelected ? AppColors.background : AppColors.textSecondary,
                    fontSize: 12,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NewSiteCard extends StatelessWidget {
  final Map<String, dynamic> site;
  final VoidCallback onTap;

  const _NewSiteCard({required this.site, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = site['name'] ?? 'Unknown';
    final location = site['location'] ?? '';
    final addedDate = site['added_date'] ?? '';
    final power = site['power'] ?? '';
    final promo = site['promo'];
    final connectors = (site['connectors'] as List?)?.cast<String>() ?? [];

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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
                      child: Icon(Icons.ev_station, color: AppColors.primaryGreen, size: 28),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(child: Text(name, style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold))),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(color: AppColors.primaryGreen, borderRadius: BorderRadius.circular(10)),
                                child: const Text('NEW', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Icon(Icons.location_on, size: 14, color: AppColors.textLight),
                              const SizedBox(width: 4),
                              Text(location, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                              const SizedBox(width: 8),
                              Text('• Added $addedDate', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Divider(color: AppColors.borderLight),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
                      child: Text(power, style: TextStyle(color: AppColors.primaryGreen, fontSize: 11, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(width: 8),
                    ...connectors.map((c) => Container(
                      margin: const EdgeInsets.only(right: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.borderLight)),
                      child: Text(c, style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                    )),
                  ],
                ),
                if (promo != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.orange.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.withOpacity(0.2)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.local_offer, size: 16, color: Colors.orange),
                        const SizedBox(width: 8),
                        Text(promo, style: const TextStyle(color: Colors.orange, fontSize: 12, fontWeight: FontWeight.w500)),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
