import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../constants/app_colors.dart';
import '../providers/notification_provider.dart';

// ─────────────────────────────────────────────────────────────────────────────
// NOTIFICATIONS SCREEN — backed by /api/notifications.
//
// Real notifications (no hardcoded mock data). Empty state shown when the
// user has no events yet — honest signal to a new user that nothing has
// happened on their account.
// ─────────────────────────────────────────────────────────────────────────────

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _fadeAnimation = CurvedAnimation(parent: _fadeController, curve: Curves.easeOut);
    _fadeController.forward();
    // Load on next frame so context is fully mounted.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().load();
    });
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  // Map server notification dict → display attributes (icon + colour).
  _Visual _visualFor(String type) {
    switch (type) {
      case 'success':
        return _Visual(Icons.bolt_rounded, AppColors.primaryGreen);
      case 'wallet':
        return const _Visual(Icons.account_balance_wallet_rounded, Color(0xFF00B4D8));
      case 'promo':
        return const _Visual(Icons.local_offer_rounded, Color(0xFFFF006E));
      case 'reward':
        return const _Visual(Icons.star_rounded, Color(0xFFFFD700));
      case 'warning':
        return _Visual(Icons.warning_amber_rounded, AppColors.warning);
      case 'info':
      default:
        return const _Visual(Icons.info_outline_rounded, Color(0xFF8B9DC3));
    }
  }

  // Convert ISO timestamp → "2 min ago" style relative label.
  String _relativeTime(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = DateTime.now().difference(dt);
      if (diff.inSeconds < 60) return 'Just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
      if (diff.inHours < 24) return '${diff.inHours} hour${diff.inHours > 1 ? 's' : ''} ago';
      if (diff.inDays == 1) return 'Yesterday';
      if (diff.inDays < 7) return '${diff.inDays} days ago';
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: Colors.white, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Consumer<NotificationProvider>(
          builder: (context, np, _) => Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.notifications_rounded, color: AppColors.primaryGreen, size: 22),
              const SizedBox(width: 8),
              const Text(
                'Notifications',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
              ),
              if (np.unreadCount > 0) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.primaryGreen.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
                  ),
                  child: Text(
                    '${np.unreadCount} new',
                    style: TextStyle(
                      color: AppColors.primaryGreen,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        centerTitle: true,
        actions: [
          Consumer<NotificationProvider>(
            builder: (context, np, _) => np.unreadCount > 0
                ? TextButton(
                    onPressed: () => np.markAllRead(),
                    child: Text(
                      'Read all',
                      style: TextStyle(
                        color: AppColors.primaryGreen.withOpacity(0.8),
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
        elevation: 0,
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: Consumer<NotificationProvider>(
          builder: (context, np, _) {
            if (np.isLoading && np.items.isEmpty) {
              return const Center(
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.primaryGreen,
                ),
              );
            }
            if (np.items.isEmpty) return _buildEmptyState();
            return RefreshIndicator(
              color: AppColors.primaryGreen,
              backgroundColor: AppColors.cardBackground,
              onRefresh: () => np.load(),
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(vertical: 8),
                itemCount: np.items.length,
                itemBuilder: (context, i) => _buildTile(np, np.items[i]),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return ListView(
      // ListView (not Center) so RefreshIndicator works in the empty state.
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        SizedBox(height: MediaQuery.of(context).size.height * 0.25),
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppColors.primaryGreen.withOpacity(0.1),
                  border: Border.all(color: AppColors.primaryGreen.withOpacity(0.2)),
                ),
                child: Icon(
                  Icons.notifications_off_outlined,
                  size: 36,
                  color: AppColors.primaryGreen.withOpacity(0.5),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'No Notifications',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                "You're all caught up!",
                style: TextStyle(color: AppColors.textLight, fontSize: 14),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildTile(NotificationProvider np, Map<String, dynamic> n) {
    final id = n['id'] as int;
    final title = (n['title'] ?? '').toString();
    final message = (n['message'] ?? '').toString();
    final type = (n['type'] ?? 'info').toString();
    final isRead = n['is_read'] == true;
    final time = _relativeTime(n['created_at']?.toString());
    final vis = _visualFor(type);
    final color = vis.color;

    return Dismissible(
      key: ValueKey('notif-$id'),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        color: Colors.red.withOpacity(0.15),
        child: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 24),
      ),
      onDismissed: (_) => np.remove(id),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: isRead ? AppColors.cardBackground : AppColors.cardBackground.withOpacity(0.9),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isRead
                ? AppColors.borderLight.withOpacity(0.3)
                : color.withOpacity(0.25),
          ),
          boxShadow: isRead
              ? null
              : [
                  BoxShadow(
                    color: color.withOpacity(0.08),
                    blurRadius: 12,
                    offset: const Offset(0, 2),
                  ),
                ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => np.markRead(id),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: color.withOpacity(0.2)),
                    ),
                    child: Icon(vis.icon, color: color, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                title,
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 14,
                                  fontWeight: isRead ? FontWeight.w500 : FontWeight.bold,
                                ),
                              ),
                            ),
                            if (!isRead)
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: color,
                                  boxShadow: [
                                    BoxShadow(color: color.withOpacity(0.5), blurRadius: 6),
                                  ],
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          message,
                          style: TextStyle(
                            color: AppColors.textSecondary.withOpacity(0.7),
                            fontSize: 12,
                            height: 1.4,
                          ),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          time,
                          style: TextStyle(
                            color: AppColors.textLight.withOpacity(0.5),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Visual {
  final IconData icon;
  final Color color;
  const _Visual(this.icon, this.color);
}
