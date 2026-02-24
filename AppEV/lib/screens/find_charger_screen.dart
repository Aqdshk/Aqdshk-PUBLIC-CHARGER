import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';
import '../providers/charger_provider.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';
import 'live_charging_screen.dart';
import 'dart:ui';

class FindChargerScreen extends StatefulWidget {
  const FindChargerScreen({super.key});

  @override
  State<FindChargerScreen> createState() => _FindChargerScreenState();
}

class _FindChargerScreenState extends State<FindChargerScreen> {
  final MapController _mapController = MapController();
  LatLng _currentLocation = const LatLng(3.1390, 101.6869); // Default: KL
  List<Marker> _markers = [];
  bool _locationLoaded = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _getCurrentLocation();
        _loadChargers();
      }
    });
  }

  Future<void> _getCurrentLocation() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        if (mounted) setState(() => _locationLoaded = true);
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          if (mounted) setState(() => _locationLoaded = true);
          return;
        }
      }

      if (permission == LocationPermission.deniedForever) {
        if (mounted) setState(() => _locationLoaded = true);
        return;
      }

      Position position = await Geolocator.getCurrentPosition();
      if (!mounted) return;
      setState(() {
        _currentLocation = LatLng(position.latitude, position.longitude);
        _locationLoaded = true;
      });
    } catch (e) {
      debugPrint('Location error: $e');
      if (mounted) setState(() => _locationLoaded = true);
    }
  }

  Future<void> _loadChargers() async {
    if (!mounted) return;
    await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
    if (!mounted) return;
    _updateMarkers();
  }

  void _updateMarkers() {
    if (!mounted) return;
    final chargers = Provider.of<ChargerProvider>(context, listen: false).nearbyChargers;
    if (!mounted) return;
    setState(() {
      _markers = chargers.map((charger) {
        final chargerId = charger['id'] ?? 0;
        final lat = 3.1390 + (chargerId % 10) * 0.01;
        final lng = 101.6869 + (chargerId % 10) * 0.01;

        final availability = charger['availability']?.toString() ?? 'unknown';
        final status = charger['status']?.toString() ?? 'unknown';
        final isAvailable = status == 'online' && (availability == 'available' || availability == 'preparing');
        final isCharging = availability == 'charging';

        final markerColor = isAvailable
            ? AppColors.primaryGreen
            : isCharging
                ? const Color(0xFFFFA500)
                : const Color(0xFFFF006E);

        return Marker(
          point: LatLng(lat, lng),
          width: 40,
          height: 40,
          child: GestureDetector(
            onTap: () {
              _showChargerInfo(charger);
            },
            child: Container(
              decoration: BoxDecoration(
                color: markerColor,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: [
                  BoxShadow(
                    color: markerColor.withOpacity(0.6),
                    blurRadius: 8,
                    spreadRadius: 1,
                  ),
                ],
              ),
              child: const Icon(
                Icons.bolt_rounded,
                color: Colors.white,
                size: 20,
              ),
            ),
          ),
        );
      }).toList();
    });
  }

  void _showChargerInfo(Map<String, dynamic> charger) {
    final chargePointId = charger['charge_point_id']?.toString() ?? 'Unknown';
    final availability = charger['availability']?.toString() ?? 'unknown';
    final status = charger['status']?.toString() ?? 'unknown';

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$chargePointId — Status: $status, Availability: $availability'),
        backgroundColor: AppColors.cardBackground,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Future<void> _startCharging(String chargerId) async {
    debugPrint('🚀 _startCharging called with chargerId: $chargerId');

    if (!mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(color: AppColors.primaryGreen),
                SizedBox(height: 16),
                Text('Starting charging...', style: TextStyle(color: AppColors.textPrimary)),
              ],
            ),
          ),
        ),
      ),
    );

    try {
      final sessionProvider = Provider.of<SessionProvider>(context, listen: false);
      await sessionProvider.startCharging(chargerId, 1);

      if (mounted) Navigator.of(context).pop();

      if (mounted) {
        await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
      }

      await Future.delayed(const Duration(seconds: 1));
      final activeSession = sessionProvider.activeSession;

      if (mounted) {
        if (activeSession != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Charging started successfully!'),
              backgroundColor: AppColors.primaryGreen,
              duration: Duration(seconds: 2),
            ),
          );
          if (mounted) {
            await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
          }
          Navigator.of(context).push(
            MaterialPageRoute(builder: (context) => const LiveChargingScreen()),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to start charging. Please try again.'),
              backgroundColor: AppColors.error,
              duration: Duration(seconds: 3),
            ),
          );
          if (mounted) {
            await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
          }
        }
      }
    } catch (e) {
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: ${e.toString()}'),
            backgroundColor: AppColors.error,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.background,
            AppColors.surface,
            AppColors.background,
          ],
        ),
      ),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('FIND CHARGER'),
          backgroundColor: Colors.transparent,
        ),
        body: !_locationLoaded
            ? const Center(
                child: CircularProgressIndicator(color: AppColors.primaryGreen),
              )
            : Stack(
                children: [
                  // OpenStreetMap
                  FlutterMap(
                    mapController: _mapController,
                    options: MapOptions(
                      initialCenter: _currentLocation,
                      initialZoom: 14.0,
                    ),
                    children: [
                      // Dark-themed tile layer
                      TileLayer(
                        urlTemplate: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
                        subdomains: const ['a', 'b', 'c', 'd'],
                        userAgentPackageName: 'com.plagsini.appev',
                        retinaMode: true,
                      ),
                      // Charger markers
                      MarkerLayer(markers: _markers),
                      // Current location marker
                      MarkerLayer(
                        markers: [
                          Marker(
                            point: _currentLocation,
                            width: 20,
                            height: 20,
                            child: Container(
                              decoration: BoxDecoration(
                                color: Colors.blue,
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white, width: 3),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.blue.withOpacity(0.4),
                                    blurRadius: 10,
                                    spreadRadius: 3,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),

                  // My location button
                  Positioned(
                    top: 16,
                    right: 16,
                    child: GestureDetector(
                      onTap: () {
                        _mapController.move(_currentLocation, 14.0);
                      },
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppColors.cardBackground,
                          shape: BoxShape.circle,
                          border: Border.all(color: AppColors.borderLight),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.3),
                              blurRadius: 8,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.my_location,
                          color: AppColors.primaryGreen,
                          size: 20,
                        ),
                      ),
                    ),
                  ),

                  // Charger list at bottom
                  Positioned(
                    bottom: 20,
                    left: 20,
                    right: 20,
                    child: Consumer<ChargerProvider>(
                      builder: (context, chargerProvider, _) {
                        if (chargerProvider.nearbyChargers.isEmpty) {
                          return const SizedBox.shrink();
                        }
                        return Material(
                          color: Colors.transparent,
                          child: Container(
                            constraints: const BoxConstraints(maxHeight: 300),
                            decoration: BoxDecoration(
                              color: AppColors.cardBackground.withOpacity(0.95),
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(
                                color: AppColors.primaryGreen.withOpacity(0.3),
                                width: 1,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: AppColors.primaryGreen.withOpacity(0.3),
                                  blurRadius: 20,
                                  spreadRadius: 0,
                                ),
                              ],
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(24),
                              child: BackdropFilter(
                                filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                                child: SingleChildScrollView(
                                  physics: const ClampingScrollPhysics(),
                                  padding: const EdgeInsets.all(16),
                                  child: Column(
                                    children: chargerProvider.nearbyChargers.map((charger) {
                                      final rawAvailability = charger['availability']?.toString() ?? '';
                                      final rawStatus = charger['status']?.toString() ?? 'unknown';
                                      final availability = rawAvailability.toLowerCase().trim();
                                      final status = rawStatus.toLowerCase().trim();

                                      final statusCheck = status == 'online';
                                      final availabilityCheck = availability == 'available' || availability == 'preparing';
                                      final isAvailable = statusCheck && availabilityCheck;
                                      final isCharging = availability == 'charging';
                                      final chargePointId = charger['charge_point_id']?.toString() ?? 'Unknown';

                                      debugPrint('═══════════════════════════════════════');
                                      debugPrint('🔍 Charger: $chargePointId');
                                      debugPrint('   Raw status: "$rawStatus"');
                                      debugPrint('   Raw availability: "$rawAvailability"');
                                      debugPrint('   isAvailable: $isAvailable');
                                      debugPrint('═══════════════════════════════════════');

                                      final distance = charger['distance']?.toString() ?? '0.0';

                                      String availabilityText = availability;
                                      if (availability == 'charging') {
                                        availabilityText = 'Charging';
                                      } else if (availability == 'available') {
                                        availabilityText = 'Available';
                                      } else if (availability == 'preparing') {
                                        availabilityText = 'Preparing';
                                      } else if (availability == 'unavailable') {
                                        availabilityText = 'Unavailable';
                                      } else {
                                        availabilityText = 'Unknown';
                                      }

                                      return Container(
                                        margin: const EdgeInsets.only(bottom: 12),
                                        padding: const EdgeInsets.all(16),
                                        decoration: BoxDecoration(
                                          color: AppColors.surface.withOpacity(0.8),
                                          borderRadius: BorderRadius.circular(16),
                                          border: Border.all(
                                            color: (isAvailable
                                                    ? const Color(0xFF00FF88)
                                                    : isCharging
                                                        ? const Color(0xFFFFA500)
                                                        : const Color(0xFFFF006E))
                                                .withOpacity(0.3),
                                            width: 1,
                                          ),
                                        ),
                                        child: Row(
                                          children: [
                                            Container(
                                              padding: const EdgeInsets.all(12),
                                              decoration: BoxDecoration(
                                                shape: BoxShape.circle,
                                                gradient: LinearGradient(
                                                  colors: isAvailable
                                                      ? AppColors.mediumGradient
                                                      : isCharging
                                                          ? [const Color(0xFFFFA500), const Color(0xFFFF8800)]
                                                          : [const Color(0xFFFF006E), AppColors.primaryGreen],
                                                ),
                                                boxShadow: [
                                                  BoxShadow(
                                                    color: (isAvailable
                                                            ? const Color(0xFF00FF88)
                                                            : isCharging
                                                                ? const Color(0xFFFFA500)
                                                                : const Color(0xFFFF006E))
                                                        .withOpacity(0.5),
                                                    blurRadius: 10,
                                                  ),
                                                ],
                                              ),
                                              child: const Icon(
                                                Icons.bolt_rounded,
                                                color: Colors.white,
                                                size: 20,
                                              ),
                                            ),
                                            const SizedBox(width: 16),
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  Text(
                                                    chargePointId,
                                                    style: const TextStyle(
                                                      color: AppColors.textTertiary,
                                                      fontSize: 16,
                                                      fontWeight: FontWeight.bold,
                                                    ),
                                                  ),
                                                  const SizedBox(height: 4),
                                                  Wrap(
                                                    spacing: 8,
                                                    runSpacing: 4,
                                                    children: [
                                                      Container(
                                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                                        decoration: BoxDecoration(
                                                          color: (isAvailable
                                                                  ? AppColors.primaryGreen
                                                                  : isCharging
                                                                      ? const Color(0xFFFFA500)
                                                                      : const Color(0xFFFF006E))
                                                              .withOpacity(0.2),
                                                          borderRadius: BorderRadius.circular(8),
                                                          border: Border.all(
                                                            color: isAvailable
                                                                ? AppColors.primaryGreen
                                                                : isCharging
                                                                    ? const Color(0xFFFFA500)
                                                                    : const Color(0xFFFF006E),
                                                            width: 1,
                                                          ),
                                                        ),
                                                        child: Text(
                                                          availabilityText,
                                                          style: TextStyle(
                                                            color: isAvailable
                                                                ? AppColors.primaryGreen
                                                                : isCharging
                                                                    ? const Color(0xFFFFA500)
                                                                    : const Color(0xFFFF006E),
                                                            fontSize: 10,
                                                            fontWeight: FontWeight.bold,
                                                            letterSpacing: 1,
                                                          ),
                                                        ),
                                                      ),
                                                      Text(
                                                        '$distance km',
                                                        style: const TextStyle(
                                                          color: AppColors.textLight,
                                                          fontSize: 12,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ],
                                              ),
                                            ),
                                            if (isAvailable)
                                              Material(
                                                color: Colors.transparent,
                                                child: InkWell(
                                                  onTap: () {
                                                    if (chargePointId.isNotEmpty && chargePointId != 'Unknown') {
                                                      _startCharging(chargePointId);
                                                    }
                                                  },
                                                  borderRadius: BorderRadius.circular(12),
                                                  child: Container(
                                                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                                                    decoration: BoxDecoration(
                                                      gradient: const LinearGradient(colors: AppColors.mediumGradient),
                                                      borderRadius: BorderRadius.circular(12),
                                                      boxShadow: [
                                                        BoxShadow(
                                                          color: const Color(0xFF00FF88).withOpacity(0.5),
                                                          blurRadius: 10,
                                                        ),
                                                      ],
                                                    ),
                                                    child: const Text(
                                                      'START',
                                                      style: TextStyle(
                                                        color: AppColors.textTertiary,
                                                        fontWeight: FontWeight.bold,
                                                        fontSize: 12,
                                                        letterSpacing: 1,
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                      );
                                    }).toList(),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
