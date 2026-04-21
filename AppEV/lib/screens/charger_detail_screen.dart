import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';
import '../services/api_service.dart';
import 'live_charging_screen.dart';
import 'booking_screen.dart';
import 'rating_review_screen.dart';

class ChargerDetailScreen extends StatefulWidget {
  final Map<String, dynamic> charger;

  const ChargerDetailScreen({super.key, required this.charger});

  @override
  State<ChargerDetailScreen> createState() => _ChargerDetailScreenState();
}

class _ChargerDetailScreenState extends State<ChargerDetailScreen> {
  bool _isFavourite = false;
  int _selectedConnector = 0;
  double _avgRating = 0;
  int _reviewCount = 0;

  @override
  void initState() {
    super.initState();
    _loadRating();
  }

  Future<void> _loadRating() async {
    try {
      final chargerId = widget.charger['charge_point_id']?.toString() ?? '';
      if (chargerId.isEmpty) return;
      final data = await ApiService.getChargerRating(chargerId);
      if (mounted) {
        setState(() {
          _avgRating = (data['avg_rating'] as num?)?.toDouble() ?? 0;
          _reviewCount = (data['review_count'] as num?)?.toInt() ?? 0;
        });
      }
    } catch (_) {}
  }

  void _showReportIssueSheet(BuildContext context, String chargerId) {
    String _selectedIssue = 'connector_damaged';
    final _descController = TextEditingController();
    bool _submitting = false;

    final issueTypes = [
      {'value': 'connector_damaged', 'label': 'Connector Damaged'},
      {'value': 'no_power', 'label': 'No Power / Dead'},
      {'value': 'payment_issue', 'label': 'Payment Issue'},
      {'value': 'screen_broken', 'label': 'Screen Broken'},
      {'value': 'vandalism', 'label': 'Vandalism'},
      {'value': 'other', 'label': 'Other'},
    ];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.cardBackground,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setModalState) {
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 24,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.report_problem, color: Colors.orange),
                    SizedBox(width: 8),
                    Text(
                      'Report Charger Issue',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                SizedBox(height: 16),
                Text('Issue Type', style: TextStyle(color: AppColors.textLight, fontSize: 13)),
                SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: _selectedIssue,
                  dropdownColor: AppColors.surface,
                  style: TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: AppColors.borderLight)),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: AppColors.borderLight)),
                    filled: true,
                    fillColor: AppColors.surface,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                  ),
                  items: issueTypes.map((t) => DropdownMenuItem(
                    value: t['value'],
                    child: Text(t['label']!),
                  )).toList(),
                  onChanged: (v) => setModalState(() => _selectedIssue = v ?? _selectedIssue),
                ),
                SizedBox(height: 12),
                TextField(
                  controller: _descController,
                  maxLines: 3,
                  style: TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Describe the issue (optional)...',
                    hintStyle: TextStyle(color: AppColors.textLight),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: AppColors.borderLight)),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: AppColors.borderLight)),
                    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.orange)),
                    filled: true,
                    fillColor: AppColors.surface,
                  ),
                ),
                SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _submitting ? null : () async {
                      setModalState(() => _submitting = true);
                      final ok = await ApiService.reportChargerIssue(
                        chargerId,
                        _selectedIssue,
                        _descController.text.trim().isEmpty ? null : _descController.text.trim(),
                      );
                      if (ctx.mounted) Navigator.pop(ctx);
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(ok ? 'Report submitted. Thank you!' : 'Failed to submit report.'),
                            backgroundColor: ok ? Colors.orange : Colors.red,
                          ),
                        );
                      }
                    },
                    icon: Icon(Icons.send, color: Colors.white),
                    label: Text(_submitting ? 'Submitting...' : 'SUBMIT REPORT', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.orange,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ],
            ),
          );
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.charger['charge_point_id'] ?? 'Unknown Charger';
    final status = widget.charger['availability'] ?? 'unknown';
    final isAvailable = status == 'available' || status == 'preparing';
    final vendor = widget.charger['vendor'] ?? 'Unknown';
    final model = widget.charger['model'] ?? '';

    // Real data from DB
    final location = widget.charger['location']?.toString();
    final double? distance = (widget.charger['distance'] as num?)?.toDouble();
    final connectorType = widget.charger['connector_type']?.toString();
    final double? maxPowerKw = (widget.charger['max_power_kw'] as num?)?.toDouble();
    final double? pricePerKwh = (widget.charger['price_per_kwh'] as num?)?.toDouble();
    final int numConnectors = ((widget.charger['number_of_connectors'] as num?)?.toInt()) ?? 1;

    final distanceStr = (distance != null && distance > 0)
        ? '${distance.toStringAsFixed(1)} km'
        : '—';
    final priceStr = pricePerKwh != null
        ? 'RM ${pricePerKwh.toStringAsFixed(2)}/kWh'
        : 'RM 0.50/kWh';
    final powerStr = maxPowerKw != null
        ? '${maxPowerKw % 1 == 0 ? maxPowerKw.toInt() : maxPowerKw} kW'
        : '—';
    // Determine AC/DC from connector type
    final bool isDC = connectorType != null &&
        (connectorType.toLowerCase().contains('ccs') ||
         connectorType.toLowerCase().contains('chademo') ||
         connectorType.toLowerCase().contains('dc'));
    final connectorLabel = connectorType ?? 'Type 2';

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
                icon: Icon(Icons.share, color: Colors.white),
                onPressed: () {
                  final shareText = '⚡ Check out $name charger on PlagSini!\n'
                      'Status: ${isAvailable ? "Available" : "Offline"}\n'
                      'Vendor: $vendor $model\n\n'
                      'Download PlagSini EV app to start charging!';
                  Clipboard.setData(ClipboardData(text: shareText));
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Charger info copied to clipboard! Share it with friends.'),
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
                      SizedBox(height: 40),
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.2),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          Icons.ev_station,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                      SizedBox(height: 12),
                      Text(
                        name,
                        style: TextStyle(
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
                            icon: Icons.power,
                            iconColor: AppColors.primaryGreen,
                            label: 'Power',
                            value: powerStr,
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
                            value: distanceStr,
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  SizedBox(height: 16),
                  
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
                            SizedBox(width: 8),
                            Text(
                              'Location',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 12),
                        Text(
                          location ?? 'Location not available',
                          style: TextStyle(
                            color: location != null ? AppColors.textLight : AppColors.textLight.withOpacity(0.5),
                            fontSize: 14,
                            height: 1.5,
                          ),
                        ),
                        SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: () async {
                                  final lat = widget.charger['latitude'];
                                  final lng = widget.charger['longitude'];
                                  final name = Uri.encodeComponent(
                                    widget.charger['charge_point_id']?.toString() ?? 'EV Charger'
                                  );
                                  Uri mapsUrl;
                                  if (lat != null && lng != null) {
                                    mapsUrl = Uri.parse('https://www.google.com/maps/dir/?api=1&destination=$lat,$lng&travelmode=driving');
                                  } else {
                                    mapsUrl = Uri.parse('https://www.google.com/maps/search/?api=1&query=$name+EV+charger');
                                  }
                                  if (await canLaunchUrl(mapsUrl)) {
                                    await launchUrl(mapsUrl, mode: LaunchMode.externalApplication);
                                  } else {
                                    if (context.mounted) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Could not open Maps')),
                                      );
                                    }
                                  }
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
                  
                  SizedBox(height: 16),
                  
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
                            SizedBox(width: 8),
                            Text(
                              'Charger Information',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 16),
                        _DetailRow(label: 'Vendor', value: vendor),
                        _DetailRow(label: 'Model', value: model.isNotEmpty ? model : '—'),
                        _DetailRow(label: 'Connectors', value: numConnectors.toString()),
                        _DetailRow(label: 'Max Power', value: powerStr),
                        _DetailRow(label: 'Pricing', value: priceStr),
                        _DetailRow(label: 'Operating Hours', value: '24/7'),
                      ],
                    ),
                  ),
                  
                  SizedBox(height: 16),
                  
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
                            SizedBox(width: 8),
                            Text(
                              'Select Connector',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 16),
                        // Build connector tiles from real data
                        ...List.generate(
                          numConnectors,
                          (index) => Padding(
                            padding: EdgeInsets.only(bottom: index < numConnectors - 1 ? 8 : 0),
                            child: _ConnectorTile(
                              type: isDC ? 'DC' : 'AC',
                              name: connectorLabel,
                              power: powerStr,
                              isAvailable: isAvailable,
                              isSelected: _selectedConnector == index,
                              onTap: () => setState(() => _selectedConnector = index),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  SizedBox(height: 16),
                  
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
                            SizedBox(width: 8),
                            Text(
                              'Nearby Amenities',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 16),
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
                  
                  SizedBox(height: 16),

                  // Rating & Reviews Card
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
                            Icon(Icons.star, color: Colors.amber),
                            SizedBox(width: 8),
                            Text(
                              'Rating & Reviews',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const Spacer(),
                            TextButton(
                              onPressed: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => RatingReviewScreen(
                                    chargePointId: name,
                                    chargerName: name,
                                  ),
                                ),
                              ).then((_) => _loadRating()),
                              child: Text(
                                'See All',
                                style: TextStyle(color: AppColors.primaryGreen),
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 8),
                        Row(
                          children: [
                            Text(
                              _avgRating > 0 ? _avgRating.toStringAsFixed(1) : '—',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 36,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: List.generate(5, (i) => Icon(
                                    i < _avgRating.round() ? Icons.star : Icons.star_border,
                                    color: Colors.amber,
                                    size: 20,
                                  )),
                                ),
                                SizedBox(height: 4),
                                Text(
                                  '$_reviewCount review${_reviewCount != 1 ? 's' : ''}',
                                  style: TextStyle(color: AppColors.textLight, fontSize: 12),
                                ),
                              ],
                            ),
                            const Spacer(),
                            ElevatedButton.icon(
                              onPressed: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => RatingReviewScreen(
                                    chargePointId: name,
                                    chargerName: name,
                                  ),
                                ),
                              ).then((_) => _loadRating()),
                              icon: Icon(Icons.rate_review, size: 16, color: Colors.black),
                              label: Text('Review', style: TextStyle(color: Colors.black, fontSize: 12)),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.primaryGreen,
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  SizedBox(height: 120),
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
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Secondary action buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => BookingScreen(charger: widget.charger),
                        ),
                      ),
                      icon: Icon(Icons.calendar_today, color: AppColors.primaryGreen, size: 16),
                      label: Text('Book Slot', style: TextStyle(color: AppColors.primaryGreen, fontSize: 13)),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(color: AppColors.primaryGreen),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                  SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _showReportIssueSheet(context, name),
                      icon: Icon(Icons.report_problem, color: Colors.orange, size: 16),
                      label: Text('Report Issue', style: TextStyle(color: Colors.orange, fontSize: 13)),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: Colors.orange),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                ],
              ),
              SizedBox(height: 10),
              // Main price + start charging row
              Row(
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
                          priceStr,
                          style: TextStyle(
                            color: Colors.white,
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
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
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
              SizedBox(height: 16),
              Text(
                'Starting charging session...',
                style: TextStyle(color: Colors.white),
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
            content: Text('Charging started successfully!'),
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
            content: Text('Charging request sent. Please wait...'),
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
        SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: AppColors.textLight,
            fontSize: 11,
          ),
        ),
        SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            color: Colors.white,
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
              color: Colors.white,
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
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        color: Colors.white,
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
                SizedBox(width: 8),
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
          SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}
