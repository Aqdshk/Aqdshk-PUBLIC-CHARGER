import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

class SessionProvider with ChangeNotifier {
  Map<String, dynamic>? _activeSession;
  List<Map<String, dynamic>> _history = [];
  bool _isLoading = false;
  String? _error;
  Timer? _pollingTimer;
  // When true, keep polling even if _activeSession is null (waiting for OCPP StartTransaction).
  bool _expectingSession = false;
  DateTime? _expectingUntil;

  Map<String, dynamic>? get activeSession => _activeSession;
  List<Map<String, dynamic>> get history => _history;
  bool get isLoading => _isLoading;
  String? get error => _error;

  SessionProvider() {
    // Auto-load active session on init
    loadActiveSession();
  }

  Future<void> loadActiveSession() async {
    _isLoading = true;
    notifyListeners();

    try {
      final session = await ApiService.getActiveSession();
      if (session != null) {
        // Real session arrived — replace placeholder & clear expecting flag.
        _activeSession = session;
        _expectingSession = false;
        _expectingUntil = null;
        await _enrichWithMetering();
      } else if (_expectingSession &&
          _expectingUntil != null &&
          DateTime.now().isBefore(_expectingUntil!)) {
        // Still waiting for OCPP StartTransaction — keep placeholder visible.
      } else {
        _activeSession = null;
      }
    } catch (e) {
      if (e is AuthSessionExpiredException) {
        _error = 'Session expired. Please login again.';
      } else {
        debugPrint('Error loading session: $e');
      }
    }

    _isLoading = false;
    notifyListeners();
  }

  /// The /api/sessions object has no live power/voltage/current and no
  /// duration. Enrich the active session with the latest meter reading
  /// and a computed duration so the Live Charging screen has real data.
  Future<void> _enrichWithMetering() async {
    final s = _activeSession;
    if (s == null) return;

    // Session energy — API field is `energy_consumed`.
    s['energy'] = s['energy'] ?? s['energy_consumed'] ?? 0;

    // Duration — computed from start_time (treated as MYT if no offset).
    final st = s['start_time']?.toString();
    if (st != null && st.isNotEmpty) {
      try {
        final norm = (st.contains('+') || st.endsWith('Z')) ? st : '$st+08:00';
        final start = DateTime.parse(norm);
        final d = DateTime.now().difference(start);
        final h = d.inHours;
        final m = d.inMinutes % 60;
        final sec = d.inSeconds % 60;
        s['duration'] = h > 0
            ? '$h:${m.toString().padLeft(2, '0')}:${sec.toString().padLeft(2, '0')}'
            : '${m.toString().padLeft(2, '0')}:${sec.toString().padLeft(2, '0')}';
      } catch (_) {}
    }

    // Live power/voltage/current — from the metering endpoint (power is kW).
    final cp = s['charge_point_id']?.toString();
    if (cp != null && cp.isNotEmpty) {
      final m = await ApiService.getLatestMetering(cp);
      if (m != null) {
        s['power'] = m['power'] ?? 0;
        s['voltage'] = m['voltage'] ?? 0;
        s['current'] = m['current'] ?? 0;
      }
    }
  }

  Future<void> loadHistory() async {
    _isLoading = true;
    notifyListeners();

    try {
      final sessions = await ApiService.getChargingHistory();
      _history = sessions;
    } catch (e) {
      if (e is AuthSessionExpiredException) {
        _error = 'Session expired. Please login again.';
      } else {
        debugPrint('Error loading history: $e');
      }
    }

    _isLoading = false;
    notifyListeners();
  }

  void startPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      // Poll if we have a real session OR we're waiting for one (within window).
      if (_activeSession != null) {
        loadActiveSession();
      } else if (_expectingSession &&
          _expectingUntil != null &&
          DateTime.now().isBefore(_expectingUntil!)) {
        loadActiveSession();
      } else if (_expectingSession &&
          _expectingUntil != null &&
          DateTime.now().isAfter(_expectingUntil!)) {
        // Give up waiting — clear placeholder & stop.
        _expectingSession = false;
        _activeSession = null;
        notifyListeners();
        stopPolling();
      }
    });
  }

  void stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }

  Future<bool> stopCharging() async {
    try {
      if (_activeSession == null) {
        debugPrint('No active session to stop');
        return false;
      }
      
      final transactionId = _activeSession!['transaction_id'];
      if (transactionId == null || transactionId == 0) {
        debugPrint('Invalid transaction_id: $transactionId');
        return false;
      }
      
      final result = await ApiService.stopCharging(transactionId);
      
      if (result['success'] ?? false) {
        _activeSession = null;
        _expectingSession = false;
        _expectingUntil = null;
        stopPolling();
        await loadHistory();
        notifyListeners();
        return true;
      } else {
        debugPrint('Stop charging failed: ${result['message'] ?? 'Unknown error'}');
        return false;
      }
    } catch (e) {
      debugPrint('Error stopping charging: $e');
      return false;
    }
  }
  
  Future<void> startCharging(String chargerId, int connectorId, {String? idTag}) async {
    try {
      debugPrint('🔄 Starting charging for charger: $chargerId, connector: $connectorId');
      final result = await ApiService.startCharging(chargerId, connectorId, idTag: idTag);
      
      debugPrint('📡 Start charging response: $result');
      
      if (result['success'] ?? false) {
        debugPrint('✅ Charging request accepted. Waiting for transaction to start...');
        // Optimistic placeholder — banner / live screen shows immediately while we wait
        // for the OCPP StartTransaction callback to land in the DB.
        _activeSession = {
          'charger_id': chargerId,
          'connector_id': connectorId,
          'transaction_id': 0,
          'energy': 0,
          'power': 0,
          'voltage': 0,
          'current': 0,
          'duration': '00:00',
          'pending': true,
        };
        _expectingSession = true;
        _expectingUntil = DateTime.now().add(const Duration(minutes: 2));
        notifyListeners();
        startPolling();
        // First real check after 2s
        await Future.delayed(const Duration(seconds: 2));
        await loadActiveSession();
      } else {
        final errorMsg = result['message'] ?? 'Unknown error';
        debugPrint('❌ Start charging failed: $errorMsg');
        // Don't set active session if charging failed
        _activeSession = null;
        notifyListeners();
      }
    } catch (e) {
      debugPrint('❌ Error starting charging: $e');
      _activeSession = null;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    stopPolling();
    super.dispose();
  }
}

