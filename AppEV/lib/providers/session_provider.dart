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
      // Ask for our own session first. It is the only endpoint a customer is
      // allowed to read, and it already carries live power, voltage, current
      // and SoC, so no second call is needed. Fall back to the operator
      // endpoint for admin and dashboard accounts, whose sessions predate
      // per-user attribution and are not matched by user id.
      var session = await ApiService.getMyActiveSession();
      var enriched = session != null;
      session ??= await ApiService.getActiveSession();

      if (session != null) {
        // Real session arrived — replace placeholder & clear expecting flag.
        _activeSession = session;
        _expectingSession = false;
        _expectingUntil = null;
        if (enriched) {
          _computeDuration();
        } else {
          await _enrichWithMetering();
        }
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

  /// Elapsed time since the session started, formatted for the live screen.
  /// start_time is Malaysian wall time and carries no offset, so one is added
  /// before parsing rather than letting it be read as UTC.
  void _computeDuration() {
    final s = _activeSession;
    if (s == null) return;
    final st = s['start_time']?.toString();
    if (st == null || st.isEmpty) return;
    try {
      final norm = (st.contains('+') || st.endsWith('Z')) ? st : '$st+08:00';
      final start = DateTime.parse(norm);
      final d = DateTime.now().difference(start);
      if (d.isNegative) return;
      final h = d.inHours;
      final m = d.inMinutes % 60;
      final sec = d.inSeconds % 60;
      s['duration'] = h > 0
          ? '$h:${m.toString().padLeft(2, '0')}:${sec.toString().padLeft(2, '0')}'
          : '${m.toString().padLeft(2, '0')}:${sec.toString().padLeft(2, '0')}';
    } catch (_) {}
  }

  /// The /api/sessions object has no live power/voltage/current and no
  /// duration. Enrich the active session with the latest meter reading
  /// and a computed duration so the Live Charging screen has real data.
  Future<void> _enrichWithMetering() async {
    final s = _activeSession;
    if (s == null) return;

    // Session energy — API field is `energy_consumed`.
    s['energy'] = s['energy'] ?? s['energy_consumed'] ?? 0;

    _computeDuration();

    // Live power/voltage/current — from the metering endpoint (power is kW).
    final cp = s['charge_point_id']?.toString();
    if (cp != null && cp.isNotEmpty) {
      final m = await ApiService.getLatestMetering(cp);
      if (m != null) {
        s['power'] = m['power'] ?? 0;
        s['voltage'] = m['voltage'] ?? 0;
        s['current'] = m['current'] ?? 0;
        // Carried through so the battery animation shows a percentage on this
        // path too. Operator sessions are labelled APP_USER rather than a real
        // user id, so an admin always lands here rather than on /me.
        // Kept from the previous poll when a sample omits it, since SoC is not
        // present on every MeterValues and blanking it makes the pack flicker.
        if (m['soc'] != null) s['soc'] = m['soc'];
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

