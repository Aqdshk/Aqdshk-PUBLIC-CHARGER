import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

/// In-app notification feed state.
///
/// Backed by `/api/notifications` on the platform. The screen calls [load]
/// on open + pull-to-refresh; the bell-badge widget calls [refreshUnread]
/// periodically (cheap count endpoint).
class NotificationProvider extends ChangeNotifier {
  List<Map<String, dynamic>> _items = [];
  int _unreadCount = 0;
  bool _isLoading = false;

  List<Map<String, dynamic>> get items => _items;
  int get unreadCount => _unreadCount;
  bool get isLoading => _isLoading;

  Future<void> load() async {
    _isLoading = true;
    notifyListeners();
    final list = await ApiService.getNotifications();
    _items = list;
    _unreadCount = list.where((n) => n['is_read'] == false).length;
    _isLoading = false;
    notifyListeners();
  }

  /// Lightweight refresh of just the badge count (cheap endpoint).
  Future<void> refreshUnread() async {
    final c = await ApiService.getNotificationsUnreadCount();
    if (c != _unreadCount) {
      _unreadCount = c;
      notifyListeners();
    }
  }

  Future<void> markRead(int id) async {
    // Optimistic flip — feels instant; server call in background.
    final idx = _items.indexWhere((n) => n['id'] == id);
    if (idx == -1) return;
    if (_items[idx]['is_read'] == true) return;
    _items[idx] = {..._items[idx], 'is_read': true};
    if (_unreadCount > 0) _unreadCount--;
    notifyListeners();
    final ok = await ApiService.markNotificationRead(id);
    if (!ok) {
      // Roll back on failure so UI stays consistent with server.
      _items[idx] = {..._items[idx], 'is_read': false};
      _unreadCount++;
      notifyListeners();
    }
  }

  Future<void> markAllRead() async {
    final wasUnread = _unreadCount;
    _items = _items.map((n) => {...n, 'is_read': true}).toList();
    _unreadCount = 0;
    notifyListeners();
    final ok = await ApiService.markAllNotificationsRead();
    if (!ok) {
      _unreadCount = wasUnread;
      notifyListeners();
    }
  }

  Future<void> remove(int id) async {
    final removed = _items.where((n) => n['id'] == id).toList();
    _items = _items.where((n) => n['id'] != id).toList();
    if (removed.isNotEmpty && removed.first['is_read'] == false && _unreadCount > 0) {
      _unreadCount--;
    }
    notifyListeners();
    final ok = await ApiService.deleteNotification(id);
    if (!ok && removed.isNotEmpty) {
      _items = [..._items, removed.first];
      _items.sort((a, b) => (b['id'] as int).compareTo(a['id'] as int));
      if (removed.first['is_read'] == false) _unreadCount++;
      notifyListeners();
    }
  }
}
