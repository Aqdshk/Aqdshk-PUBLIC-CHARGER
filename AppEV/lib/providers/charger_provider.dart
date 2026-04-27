import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import '../services/api_service.dart';

class ChargerProvider with ChangeNotifier {
  List<Map<String, dynamic>> _nearbyChargers = [];
  bool _isLoading = false;
  String? _error;
  Position? _currentPosition;
  Timer? _pollTimer;

  List<Map<String, dynamic>> get nearbyChargers => _nearbyChargers;
  bool get isLoading => _isLoading;
  String? get error => _error;
  Position? get currentPosition => _currentPosition;

  ChargerProvider() {
    // Auto-load chargers on init
    loadNearbyChargers();
    // Start polling for live status updates (every 5s)
    startAutoRefresh();
  }

  void startAutoRefresh() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      silentRefresh();
    });
  }

  void stopAutoRefresh() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  /// Refresh charger list without showing loading spinner
  Future<void> silentRefresh() async {
    try {
      final chargers = await ApiService.getNearbyChargers(
        _currentPosition?.latitude ?? 0,
        _currentPosition?.longitude ?? 0,
      );
      final onlineChargers = chargers.where((c) {
        return (c['status']?.toString() ?? 'unknown') == 'online';
      }).toList();
      final withDistance = onlineChargers.map((c) {
        double distance = 0;
        if (_currentPosition != null) {
          final id = c['id'] ?? 0;
          distance = 1.0 + (id % 10) * 0.5;
        }
        return {
          ...c,
          'distance': distance,
          'charge_point_id': c['charge_point_id']?.toString() ?? '',
          'availability': c['availability']?.toString() ?? 'unknown',
          'status': c['status']?.toString() ?? 'unknown',
        };
      }).toList();
      _nearbyChargers = withDistance;
      notifyListeners();
    } catch (_) {
      // Silent fail
    }
  }

  /// Fetch a single charger's latest data by charge_point_id
  Map<String, dynamic>? findChargerById(String chargePointId) {
    for (final c in _nearbyChargers) {
      if (c['charge_point_id']?.toString() == chargePointId) return c;
    }
    return null;
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> loadNearbyChargers() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Try to get current location (non-blocking)
      await _getCurrentLocation();
      
      // Load chargers from API
      debugPrint('📡 Loading chargers from API...');
      final chargers = await ApiService.getNearbyChargers(
        _currentPosition?.latitude ?? 0,
        _currentPosition?.longitude ?? 0,
      );
      
      debugPrint('📡 Received ${chargers.length} chargers');

      // Filter: only show online chargers
      final onlineChargers = chargers.where((charger) {
        final status = charger['status']?.toString() ?? 'unknown';
        return status == 'online';
      }).toList();

      final chargersWithDistance = onlineChargers.map((charger) {
        double distance = 0;
        if (_currentPosition != null) {
          // Mock location calculation - replace with actual charger location
          final chargerId = charger['id'] ?? 0;
          distance = 1.0 + (chargerId % 10) * 0.5;
        }
        return {
          ...charger,
          'distance': distance,
          // Ensure all required fields have defaults
          'charge_point_id': charger['charge_point_id']?.toString() ?? '',
          'availability': charger['availability']?.toString() ?? 'unknown',
          'status': charger['status']?.toString() ?? 'unknown',
        };
      }).toList();

      // Sort: online first, then by availability (available > preparing > charging > others)
      chargersWithDistance.sort((a, b) {
        // First sort by status (online first)
        final aStatus = a['status']?.toString() ?? 'unknown';
        final bStatus = b['status']?.toString() ?? 'unknown';
        if (aStatus == 'online' && bStatus != 'online') return -1;
        if (aStatus != 'online' && bStatus == 'online') return 1;
        
        // Then sort by availability
        final aAvail = a['availability']?.toString() ?? 'unknown';
        final bAvail = b['availability']?.toString() ?? 'unknown';
        final availOrder = ['available', 'preparing', 'charging', 'offline', 'unknown'];
        return availOrder.indexOf(aAvail).compareTo(availOrder.indexOf(bAvail));
      });

      _nearbyChargers = chargersWithDistance;
      debugPrint('✅ Chargers loaded successfully');
    } catch (e) {
      debugPrint('❌ Error loading chargers: $e');
      if (e is AuthSessionExpiredException) {
        _error = 'Session expired. Please login again.';
      } else {
        _error = e.toString();
      }
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> _getCurrentLocation() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return;

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) return;
    }

    try {
      _currentPosition = await Geolocator.getCurrentPosition();
    } catch (e) {
      debugPrint('Error getting location: $e');
    }
  }

  Future<Map<String, dynamic>> startCharging(String chargerId, int connectorId, {String? idTag}) async {
    try {
      final result = await ApiService.startCharging(chargerId, connectorId, idTag: idTag);
      return result;
    } catch (e) {
      debugPrint('Error starting charging: $e');
      return {
        'success': false,
        'message': e.toString(),
      };
    }
  }
}

