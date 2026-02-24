import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';
import 'live_charging_screen.dart';

class ChargerDetailScreen extends StatefulWidget {
  final Map<String, dynamic> charger;

  const ChargerDetailScreen({super.key, required this.charger});

  @override
  State<ChargerDetailScreen> createState() => _ChargerDetailScreenState();
}

class _ChargerDetailScreenState extends State<ChargerDetailScreen> {
  bool _isFavourite = false;
  int _selectedConnector = 0;

  @override
  Widget build(BuildContext context) {
    final name = widget.charger['charge_point_id'] ?? 'Unknown Charger';
    final status = widget.charger['availability'] ?? 'unknown';
    final isAvailable = status == 'available' || status == 'preparing';
    final vendor = widget.charger['vendor'] ?? 'Unknown';
    final model = widget.charger['model'] ?? '';

    return Scaffold(
      backgroundColor: AppColors.background,
      body: CustomScrollView(
        slivers: [
          // App Bar with Image
          SliverAppBar(
            expandedHeight: 200,
            pinned: true,
            backgroundColor: AppColors.primaryGreen,
            iconTheme: const IconThemeData(color: Colors.white),
            actions: [
              IconButton(
                icon: Icon(
                  _isFavourite ? Icons.bookmark : Icons.bookmark_border,
                  color: Colors.white,
                ),
                onPressed: () {
                  setState(() => _isFavourite = !_isFavourite);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(_isFavourite 
                        ? 'Added to favourites' 
                        : 'Removed from favourites'),
                      backgroundColor: AppColors.primaryGreen,
                    ),
                  );
                },
              ),
              IconButton(
                icon: const Icon(Icons.share, color: Colors.white),
                onPressed: () {
                  final shareText = '⚡ Check out $name charger on PlagSini!\n'
                      'Status: ${isAvailable ? "Available" : "Offline"}\n'
                      'Vendor: $vendor $model\n\n'
                      'Download PlagSini EV app to start charging!';
                  Clipboard.setData(ClipboardData(text: shareText));
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Charger info copied to clipboard! Share it with friends.'),
                      backgroundColor: AppColors.primaryGreen,
                    ),
                  );
                },
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      AppColors.primaryGreen,
                      AppColors.darkGreen,
                    ],
                  ),
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(height: 40),
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.ev_station,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        name,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Status & Rating Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: _InfoItem(
                            icon: Icons.circle,
                            iconColor: isAvailable ? AppColors.primaryGreen : Colors.red,
                            label: 'Status',
                            value: isAvailable ? 'Available' : 'In Use',
                          ),
                        ),
                        Container(
                          width: 1,
                          height: 40,
                          color: AppColors.borderLight,
                        ),
                        Expanded(
                          child: _InfoItem(
                            icon: Icons.star,
                            iconColor: Colors.amber,
                            label: 'Rating',
                            value: '4.9 (128)',
                          ),
                        ),
                        Container(
                          width: 1,
                          height: 40,
                          color: AppColors.borderLight,
                        ),
                        Expanded(
                          child: _InfoItem(
                            icon: Icons.location_on,
                            iconColor: AppColors.primaryGreen,
                            label: 'Distance',
                            value: '1.5 km',
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Location Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.location_on, color: AppColors.primaryGreen),
                            const SizedBox(width: 8),
                            Text(
                              'Location',
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Lot 123, Jalan Perusahaan,\nShah Alam, Selangor',
                          style: TextStyle(
                            color: AppColors.textLight,
                            fontSize: 14,
                            height: 1.5,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: const Text('Opening navigation...'),
                                      backgroundColor: AppColors.primaryGreen,
                                    ),
                                  );
                                },
                                icon: Icon(Icons.directions, color: AppColors.primaryGreen),
                                label: Text('Get Directions', style: TextStyle(color: AppColors.primaryGreen)),
                                style: OutlinedButton.styleFrom(
                                  side: BorderSide(color: AppColors.primaryGreen),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Charger Info Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.info_outline, color: AppColors.primaryGreen),
                            const SizedBox(width: 8),
                            Text(
                              'Charger Information',
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _DetailRow(label: 'Vendor', value: vendor),
                        _DetailRow(label: 'Model', value: model.isNotEmpty ? model : 'Standard AC/DC'),
                        _DetailRow(label: 'Max Power', value: '40 kW'),
                        _DetailRow(label: 'Pricing', value: 'RM 0.60/kWh'),
                        _DetailRow(label: 'Operating Hours', value: '24/7'),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Connectors Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.power, color: AppColors.primaryGreen),
                            const SizedBox(width: 8),
                            Text(
                              'Select Connector',
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _ConnectorTile(
                          type: 'DC',
                          name: 'CCS2',
                          power: '50 kW',
                          isAvailable: true,
                          isSelected: _selectedConnector == 0,
                          onTap: () => setState(() => _selectedConnector = 0),
                        ),
                        const SizedBox(height: 8),
                        _ConnectorTile(
                          type: 'AC',
                          name: 'Type 2',
                          power: '22 kW',
                          isAvailable: true,
                          isSelected: _selectedConnector == 1,
                          onTap: () => setState(() => _selectedConnector = 1),
                        ),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Amenities
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.local_cafe, color: AppColors.primaryGreen),
                            const SizedBox(width: 8),
                            Text(
                              'Nearby Amenities',
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _AmenityChip(icon: Icons.local_parking, label: 'Parking'),
                            _AmenityChip(icon: Icons.restaurant, label: 'Restaurant'),
                            _AmenityChip(icon: Icons.wc, label: 'Restroom'),
                            _AmenityChip(icon: Icons.wifi, label: 'WiFi'),
                            _AmenityChip(icon: Icons.shopping_bag, label: 'Shopping'),
                          ],
                        ),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 100),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomSheet: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 10,
              offset: const Offset(0, -5),
            ),
          ],
        ),
        child: SafeArea(
          child: Row(
            children: [
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Estimated Cost',
                      style: TextStyle(
                        color: AppColors.textLight,
                        fontSize: 12,
                      ),
                    ),
                    Text(
                      'RM 0.60/kWh',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ElevatedButton(
                  onPressed: isAvailable ? () => _startCharging(context) : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isAvailable ? AppColors.primaryGreen : Colors.grey,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(
                    isAvailable ? 'START CHARGING' : 'NOT AVAILABLE',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _startCharging(BuildContext context) async {
    final sessionProvider = context.read<SessionProvider>();
    final chargerId = widget.charger['charge_point_id']?.toString() ?? '';
    
    // Show loading dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Center(
        child: Container(
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: AppColors.cardBackground,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: AppColors.primaryGreen),
              const SizedBox(height: 16),
              Text(
                'Starting charging session...',
                style: TextStyle(color: AppColors.textPrimary),
              ),
            ],
          ),
        ),
      ),
    );

    await sessionProvider.startCharging(chargerId, _selectedConnector + 1);
    
    if (context.mounted) {
      Navigator.pop(context); // Dismiss loading dialog
      
      // Check if session started by checking activeSession
      final activeSession = sessionProvider.activeSession;
      if (activeSession != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Charging started successfully!'),
            backgroundColor: AppColors.primaryGreen,
          ),
        );
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const LiveChargingScreen()),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Charging request sent. Please wait...'),
            backgroundColor: Colors.orange,
          ),
        );
        // Navigate anyway - the session might start shortly
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const LiveChargingScreen()),
        );
      }
    }
  }
}

class _InfoItem extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;

  const _InfoItem({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: iconColor, size: 16),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: AppColors.textLight,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              color: AppColors.textLight,
              fontSize: 14,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

class _ConnectorTile extends StatelessWidget {
  final String type;
  final String name;
  final String power;
  final bool isAvailable;
  final bool isSelected;
  final VoidCallback onTap;

  const _ConnectorTile({
    required this.type,
    required this.name,
    required this.power,
    required this.isAvailable,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: isAvailable ? onTap : null,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primaryGreen.withOpacity(0.1) : AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected ? AppColors.primaryGreen : AppColors.borderLight,
              width: isSelected ? 2 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: type == 'DC' ? AppColors.primaryGreen : Colors.blue,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  type,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      power,
                      style: TextStyle(
                        color: AppColors.textLight,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: isAvailable ? AppColors.primaryGreen.withOpacity(0.1) : Colors.red.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  isAvailable ? 'Available' : 'In Use',
                  style: TextStyle(
                    color: isAvailable ? AppColors.primaryGreen : Colors.red,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (isSelected) ...[
                const SizedBox(width: 8),
                Icon(Icons.check_circle, color: AppColors.primaryGreen, size: 20),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _AmenityChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _AmenityChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: AppColors.primaryGreen),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}
