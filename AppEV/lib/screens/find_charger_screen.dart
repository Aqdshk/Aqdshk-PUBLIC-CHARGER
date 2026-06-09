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
              child: Icon(
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
      builder: (context) => Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(color: AppColors.primaryGreen),
                SizedBox(height: 16),
                Text('Starting charging...', style: TextStyle(color: Colors.white)),
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

  // Filter state for the chips (All / Available / Charging)
  String _filter = 'all';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: !_locationLoaded
          ? Center(
              child: CircularProgressIndicator(color: AppColors.primaryGreen),
            )
          : Stack(
              children: [
                // ── FULL-BLEED MAP ─────────────────────────────────────────
                FlutterMap(
                  mapController: _mapController,
                  options: MapOptions(
                    initialCenter: _currentLocation,
                    initialZoom: 14.0,
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
                      subdomains: const ['a', 'b', 'c', 'd'],
                      userAgentPackageName: 'com.plagsini.appev',
                      retinaMode: true,
                    ),
                    MarkerLayer(markers: _markers),
                    MarkerLayer(
                      markers: [
                        Marker(
                          point: _currentLocation,
                          width: 22,
                          height: 22,
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.blue,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 3),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.blue.withOpacity(0.4),
                                  blurRadius: 12,
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

                // ── TOP GRADIENT SCRIM (legibility) ────────────────────────
                IgnorePointer(
                  child: Container(
                    height: 180,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          AppColors.background.withOpacity(0.95),
                          AppColors.background.withOpacity(0.0),
                        ],
                      ),
                    ),
                  ),
                ),

                // ── FLOATING TOP BAR: back + search + filter chips ─────────
                Positioned(
                  top: MediaQuery.of(context).padding.top + 8,
                  left: 16,
                  right: 16,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Search-style pill
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                        decoration: BoxDecoration(
                          color: AppColors.cardBackground.withOpacity(0.92),
                          borderRadius: BorderRadius.circular(28),
                          border: Border.all(color: Colors.white.withOpacity(0.08)),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.4),
                              blurRadius: 16,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Row(
                          children: [
                            IconButton(
                              icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary, size: 20),
                              onPressed: () => Navigator.maybePop(context),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.search_rounded, color: AppColors.textLight, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'Search stations…',
                                style: TextStyle(
                                  color: AppColors.textLight,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                            Container(
                              margin: const EdgeInsets.only(right: 4),
                              padding: const EdgeInsets.all(7),
                              decoration: BoxDecoration(
                                color: AppColors.primaryGreen.withOpacity(0.15),
                                shape: BoxShape.circle,
                              ),
                              child: Icon(Icons.tune_rounded, color: AppColors.primaryGreen, size: 16),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      // Filter chips
                      SizedBox(
                        height: 32,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          children: [
                            _filterChip('all', 'All'),
                            const SizedBox(width: 6),
                            _filterChip('available', '🟢 Available'),
                            const SizedBox(width: 6),
                            _filterChip('charging', '⚡ Charging'),
                            const SizedBox(width: 6),
                            _filterChip('dc', 'DC Fast'),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // ── My-location button (floating right, above sheet) ───────
                Positioned(
                  right: 16,
                  bottom: MediaQuery.of(context).size.height * 0.38 + 14,
                  child: GestureDetector(
                    onTap: () => _mapController.move(_currentLocation, 15.0),
                    child: Container(
                      padding: const EdgeInsets.all(11),
                      decoration: BoxDecoration(
                        color: AppColors.cardBackground,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white.withOpacity(0.10)),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.35),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Icon(
                        Icons.my_location_rounded,
                        color: AppColors.primaryGreen,
                        size: 20,
                      ),
                    ),
                  ),
                ),

                  // ── DRAGGABLE BOTTOM SHEET — Grab/Uber feel ──────────────
                  DraggableScrollableSheet(
                    initialChildSize: 0.38,
                    minChildSize: 0.18,
                    maxChildSize: 0.85,
                    snap: true,
                    snapSizes: const [0.18, 0.38, 0.85],
                    builder: (context, scrollController) => Container(
                      decoration: BoxDecoration(
                        color: AppColors.cardBackground,
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                        border: Border(
                          top: BorderSide(color: Colors.white.withOpacity(0.08)),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.4),
                            blurRadius: 24,
                            offset: const Offset(0, -6),
                          ),
                        ],
                      ),
                      child: Column(
                        children: [
                          // Drag handle
                          Container(
                            margin: const EdgeInsets.symmetric(vertical: 10),
                            width: 38,
                            height: 4,
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.18),
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                          // Sheet header
                          Consumer<ChargerProvider>(
                            builder: (context, cp, _) {
                              final n = _applyFilter(cp.nearbyChargers).length;
                              return Padding(
                                padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
                                child: Row(
                                  children: [
                                    Text(
                                      'Nearby Stations',
                                      style: TextStyle(
                                        color: AppColors.textPrimary,
                                        fontSize: 17,
                                        fontWeight: FontWeight.w700,
                                        letterSpacing: -0.2,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: AppColors.primaryGreen.withOpacity(0.14),
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                      child: Text(
                                        '$n',
                                        style: TextStyle(
                                          color: AppColors.primaryGreen,
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ),
                                    const Spacer(),
                                    Row(
                                      children: [
                                        Icon(Icons.sort_rounded, color: AppColors.textLight, size: 14),
                                        const SizedBox(width: 4),
                                        Text(
                                          'Nearest',
                                          style: TextStyle(
                                            color: AppColors.textLight,
                                            fontSize: 11,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
                          // Station list
                          Expanded(
                            child: Consumer<ChargerProvider>(
                              builder: (context, cp, _) {
                                final filtered = _applyFilter(cp.nearbyChargers);
                                if (filtered.isEmpty) {
                                  return Center(
                                    child: Padding(
                                      padding: const EdgeInsets.all(20),
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.search_off_rounded, color: AppColors.textLight, size: 36),
                                          const SizedBox(height: 8),
                                          Text(
                                            'No stations match this filter',
                                            style: TextStyle(color: AppColors.textLight, fontSize: 12),
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                }
                                return ListView.builder(
                                  controller: scrollController,
                                  padding: const EdgeInsets.fromLTRB(14, 0, 14, 24),
                                  itemCount: filtered.length,
                                  itemBuilder: (_, i) => _buildStationCard(filtered[i]),
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                ],
              ),
    );
  }

  // ── Helpers for the redesigned Find Charger screen ─────────────────────

  Widget _filterChip(String value, String label) {
    final active = _filter == value;
    return GestureDetector(
      onTap: () => setState(() => _filter = value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: active
              ? AppColors.primaryGreen.withOpacity(0.16)
              : AppColors.cardBackground.withOpacity(0.92),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: active
                ? AppColors.primaryGreen.withOpacity(0.45)
                : Colors.white.withOpacity(0.08),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: active ? AppColors.primaryGreen : AppColors.textLight,
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
        ),
      ),
    );
  }

  List<Map<String, dynamic>> _applyFilter(List<Map<String, dynamic>> all) {
    if (_filter == 'all') return all;
    return all.where((c) {
      final av = (c['availability']?.toString() ?? '').toLowerCase();
      final st = (c['status']?.toString() ?? '').toLowerCase();
      final maxKw = (c['max_power_kw'] as num?)?.toDouble() ?? 0;
      switch (_filter) {
        case 'available':
          return st == 'online' && (av == 'available' || av == 'preparing');
        case 'charging':
          return av == 'charging';
        case 'dc':
          return maxKw >= 25;
        default:
          return true;
      }
    }).toList();
  }

  Widget _buildStationCard(Map<String, dynamic> charger) {
    final cpId = charger['charge_point_id']?.toString() ?? 'Unknown';
    final vendor = charger['vendor']?.toString() ?? '';
    final av = (charger['availability']?.toString() ?? '').toLowerCase();
    final st = (charger['status']?.toString() ?? '').toLowerCase();
    final distance = charger['distance']?.toString() ?? '—';
    final maxKw = (charger['max_power_kw'] as num?)?.toDouble();
    final isAvailable = st == 'online' && (av == 'available' || av == 'preparing');
    final isCharging = av == 'charging';

    Color accent;
    String statusLabel;
    if (isAvailable) {
      accent = AppColors.primaryGreen;
      statusLabel = 'AVAILABLE';
    } else if (isCharging) {
      accent = const Color(0xFFFFA500);
      statusLabel = 'CHARGING';
    } else if (st == 'online') {
      accent = const Color(0xFFFF4466);
      statusLabel = av.toUpperCase().isEmpty ? 'BUSY' : av.toUpperCase();
    } else {
      accent = Colors.grey.shade600;
      statusLabel = 'OFFLINE';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: () {
            if (cpId.isNotEmpty && cpId != 'Unknown') _showChargerInfo(charger);
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
            child: Row(
              children: [
                Container(
                  width: 3,
                  height: 44,
                  decoration: BoxDecoration(
                    color: accent,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 12),
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: accent.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.bolt_rounded, color: accent, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        cpId,
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.1,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 3),
                      Wrap(
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(
                            statusLabel,
                            style: TextStyle(
                              color: accent,
                              fontSize: 9.5,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.8,
                            ),
                          ),
                          Text('  •  ', style: TextStyle(color: AppColors.textLight, fontSize: 9)),
                          Text(
                            '$distance km',
                            style: TextStyle(color: AppColors.textLight, fontSize: 11, fontWeight: FontWeight.w500),
                          ),
                          if (maxKw != null) ...[
                            Text('  •  ', style: TextStyle(color: AppColors.textLight, fontSize: 9)),
                            Text(
                              '${maxKw.toStringAsFixed(0)} kW',
                              style: TextStyle(color: AppColors.textLight, fontSize: 11, fontWeight: FontWeight.w500),
                            ),
                          ],
                          if (vendor.isNotEmpty) ...[
                            Text('  •  ', style: TextStyle(color: AppColors.textLight, fontSize: 9)),
                            Text(
                              vendor,
                              style: TextStyle(color: AppColors.textLight, fontSize: 11, fontWeight: FontWeight.w500),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                if (isAvailable)
                  GestureDetector(
                    onTap: () {
                      if (cpId.isNotEmpty && cpId != 'Unknown') _startCharging(cpId);
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                      decoration: BoxDecoration(
                        color: AppColors.primaryGreen,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: const [
                          Text(
                            'Start',
                            style: TextStyle(
                              color: Color(0xFF062614),
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          SizedBox(width: 4),
                          Icon(Icons.arrow_forward_rounded, color: Color(0xFF062614), size: 14),
                        ],
                      ),
                    ),
                  )
                else
                  Icon(Icons.chevron_right_rounded, color: AppColors.textLight, size: 22),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
