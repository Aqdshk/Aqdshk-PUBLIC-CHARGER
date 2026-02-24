import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  final List<_NotificationItem> _notifications = [
    _NotificationItem(
      icon: Icons.bolt_rounded,
      title: 'Charging Complete',
      message: 'Your EV has been fully charged at Station PlagSini KL-01. Total: RM 12.50',
      time: '2 min ago',
      type: _NotifType.success,
      isRead: false,
    ),
    _NotificationItem(
      icon: Icons.local_offer_rounded,
      title: 'Weekend Promo!',
      message: 'Get 20% off on all charging sessions this weekend. Use code: WEEKEND20',
      time: '1 hour ago',
      type: _NotifType.promo,
      isRead: false,
    ),
    _NotificationItem(
      icon: Icons.account_balance_wallet_rounded,
      title: 'Wallet Top-Up Successful',
      message: 'RM 50.00 has been added to your PlagSini wallet. Current balance: RM 87.50',
      time: '3 hours ago',
      type: _NotifType.wallet,
      isRead: false,
    ),
    _NotificationItem(
      icon: Icons.ev_station_rounded,
      title: 'New Station Nearby',
      message: 'A new PlagSini charging station is now available at Setia City Mall!',
      time: 'Yesterday',
      type: _NotifType.info,
      isRead: true,
    ),
    _NotificationItem(
      icon: Icons.star_rounded,
      title: 'Reward Earned!',
      message: 'You earned 150 PlagSini Points from your last charging session.',
      time: 'Yesterday',
      type: _NotifType.reward,
      isRead: true,
    ),
    _NotificationItem(
      icon: Icons.update_rounded,
      title: 'App Update Available',
      message: 'PlagSini v2.1 is available with new features and bug fixes.',
      time: '2 days ago',
      type: _NotifType.info,
      isRead: true,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );
    _fadeController.forward();
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  int get _unreadCount => _notifications.where((n) => !n.isRead).length;

  void _markAllAsRead() {
    setState(() {
      for (var n in _notifications) {
        n.isRead = true;
      }
    });
  }

  void _clearNotification(int index) {
    setState(() {
      _notifications.removeAt(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: AppColors.textPrimary, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.notifications_rounded, color: AppColors.primaryGreen, size: 22),
            const SizedBox(width: 8),
            const Text(
              'Notifications',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            if (_unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primaryGreen.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
                ),
                child: Text(
                  '$_unreadCount new',
                  style: const TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
        centerTitle: true,
        actions: [
          if (_unreadCount > 0)
            TextButton(
              onPressed: _markAllAsRead,
              child: Text(
                'Read all',
                style: TextStyle(
                  color: AppColors.primaryGreen.withOpacity(0.8),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
        ],
        elevation: 0,
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: _notifications.isEmpty
            ? _buildEmptyState()
            : ListView.builder(
                padding: const EdgeInsets.symmetric(vertical: 8),
                itemCount: _notifications.length,
                itemBuilder: (context, index) {
                  return _buildNotificationTile(index);
                },
              ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
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
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'You\'re all caught up!',
            style: TextStyle(
              color: AppColors.textLight,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationTile(int index) {
    final notif = _notifications[index];
    final color = _getNotifColor(notif.type);

    return Dismissible(
      key: UniqueKey(),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        color: Colors.red.withOpacity(0.15),
        child: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 24),
      ),
      onDismissed: (_) => _clearNotification(index),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: notif.isRead
              ? AppColors.cardBackground
              : AppColors.cardBackground.withOpacity(0.9),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: notif.isRead
                ? AppColors.borderLight.withOpacity(0.3)
                : color.withOpacity(0.25),
          ),
          boxShadow: notif.isRead
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
            onTap: () {
              setState(() {
                notif.isRead = true;
              });
            },
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Icon
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: color.withOpacity(0.2)),
                    ),
                    child: Icon(notif.icon, color: color, size: 20),
                  ),
                  const SizedBox(width: 12),
                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                notif.title,
                                style: TextStyle(
                                  color: AppColors.textPrimary,
                                  fontSize: 14,
                                  fontWeight: notif.isRead
                                      ? FontWeight.w500
                                      : FontWeight.bold,
                                ),
                              ),
                            ),
                            if (!notif.isRead)
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: color,
                                  boxShadow: [
                                    BoxShadow(
                                      color: color.withOpacity(0.5),
                                      blurRadius: 6,
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          notif.message,
                          style: TextStyle(
                            color: AppColors.textSecondary.withOpacity(0.7),
                            fontSize: 12,
                            height: 1.4,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          notif.time,
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

  Color _getNotifColor(_NotifType type) {
    switch (type) {
      case _NotifType.success:
        return AppColors.primaryGreen;
      case _NotifType.promo:
        return const Color(0xFFFF006E);
      case _NotifType.wallet:
        return const Color(0xFF00B4D8);
      case _NotifType.reward:
        return const Color(0xFFFFD700);
      case _NotifType.info:
        return const Color(0xFF8B9DC3);
    }
  }
}

enum _NotifType { success, promo, wallet, reward, info }

class _NotificationItem {
  final IconData icon;
  final String title;
  final String message;
  final String time;
  final _NotifType type;
  bool isRead;

  _NotificationItem({
    required this.icon,
    required this.title,
    required this.message,
    required this.time,
    required this.type,
    required this.isRead,
  });
}
