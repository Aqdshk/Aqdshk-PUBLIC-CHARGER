import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../constants/app_colors.dart';

class RewardsScreen extends StatefulWidget {
  const RewardsScreen({super.key});

  @override
  State<RewardsScreen> createState() => _RewardsScreenState();
}

class _RewardsScreenState extends State<RewardsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<Map<String, dynamic>> _catalog = [];
  List<Map<String, dynamic>> _history = [];
  bool _loadingCatalog = true;
  bool _loadingHistory = false;
  bool _redeeming = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (_tabController.index == 1 && _history.isEmpty && !_loadingHistory) {
        _loadHistory();
      }
    });
    _loadCatalog();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadCatalog() async {
    setState(() => _loadingCatalog = true);
    try {
      final catalog = await ApiService.getRewardsCatalog();
      if (mounted) {
        setState(() {
          _catalog = catalog;
          _loadingCatalog = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loadingCatalog = false);
    }
  }

  Future<void> _loadHistory() async {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final user = authProvider.currentUser;
    if (user == null) return;

    setState(() => _loadingHistory = true);
    try {
      final history = await ApiService.getRewardHistory(user.id);
      if (mounted) {
        setState(() {
          _history = history;
          _loadingHistory = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  Future<void> _redeemReward(Map<String, dynamic> reward) async {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final user = authProvider.currentUser;
    if (user == null) return;

    final pointsCost = reward['points_cost'] as int;
    final rewardType = reward['reward_type'] as String;
    final title = reward['title'] as String;
    final walletCredit = (reward['wallet_credit'] ?? 0.0) as num;

    // Check sufficient points
    if (user.walletPoints < pointsCost) {
      _showInsufficientPointsDialog(pointsCost, user.walletPoints);
      return;
    }

    // Show confirmation dialog
    final confirmed = await _showConfirmDialog(
      title: title,
      pointsCost: pointsCost,
      walletCredit: walletCredit.toDouble(),
      currentPoints: user.walletPoints,
    );
    if (confirmed != true) return;

    // Perform redemption
    setState(() => _redeeming = true);
    try {
      final result = await ApiService.redeemReward(
        user.id,
        rewardType: rewardType,
        pointsCost: pointsCost,
      );

      if (mounted) {
        setState(() => _redeeming = false);
        if (result['success'] == true) {
          // Refresh user profile (updates points)
          await authProvider.refreshProfile();
          // Reload history
          _loadHistory();
          // Show success
          if (mounted) _showSuccessDialog(result, title, walletCredit.toDouble());
        } else {
          _showErrorSnackBar(result['message'] ?? 'Failed to redeem reward');
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _redeeming = false);
        _showErrorSnackBar('Error: $e');
      }
    }
  }

  void _showInsufficientPointsDialog(int needed, int current) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Icon(Icons.lock_outline, color: AppColors.warning, size: 28),
            const SizedBox(width: 10),
            Text('Not Enough Points',
                style: TextStyle(color: AppColors.textPrimary, fontSize: 18)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'You need $needed points but only have $current.',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
            ),
            const SizedBox(height: 12),
            Text(
              'Keep charging to earn more points!',
              style: TextStyle(color: AppColors.textLight, fontSize: 13),
            ),
            const SizedBox(height: 16),
            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: (current / needed).clamp(0.0, 1.0),
                minHeight: 10,
                backgroundColor: AppColors.surface,
                valueColor:
                    AlwaysStoppedAnimation<Color>(AppColors.primaryGreen),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${((current / needed) * 100).toStringAsFixed(0)}% there — ${needed - current} more points needed',
              style: TextStyle(
                  color: AppColors.primaryGreen,
                  fontSize: 12,
                  fontWeight: FontWeight.w600),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('OK',
                style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Future<bool?> _showConfirmDialog({
    required String title,
    required int pointsCost,
    required double walletCredit,
    required int currentPoints,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Confirm Redemption',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Reward icon
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.card_giftcard,
                  color: AppColors.primaryGreen, size: 40),
            ),
            const SizedBox(height: 16),
            Text(title,
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 20),
            // Details
            _confirmRow('Points to spend', '$pointsCost pts', AppColors.warning),
            if (walletCredit > 0)
              _confirmRow('Wallet credit', '+RM ${walletCredit.toStringAsFixed(2)}', AppColors.primaryGreen),
            _confirmRow('Points after', '${currentPoints - pointsCost} pts', AppColors.textSecondary),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('Cancel', style: TextStyle(color: AppColors.textLight)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primaryGreen,
              foregroundColor: AppColors.background,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
              padding:
                  const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
            ),
            child: const Text('Redeem', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _confirmRow(String label, String value, Color valueColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: AppColors.textLight, fontSize: 13)),
          Text(value,
              style: TextStyle(
                  color: valueColor, fontSize: 14, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  void _showSuccessDialog(
      Map<String, dynamic> result, String title, double walletCredit) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            // Animated check
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.0, end: 1.0),
              duration: const Duration(milliseconds: 600),
              curve: Curves.elasticOut,
              builder: (context, value, child) {
                return Transform.scale(
                  scale: value,
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppColors.primaryGreen.withOpacity(0.15),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.primaryGreen.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                    child: Icon(Icons.check_circle,
                        color: AppColors.primaryGreen, size: 56),
                  ),
                );
              },
            ),
            const SizedBox(height: 20),
            Text('Reward Redeemed!',
                style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 22,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(title,
                style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
            const SizedBox(height: 16),
            if (walletCredit > 0)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.primaryGreen.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: AppColors.primaryGreen.withOpacity(0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.account_balance_wallet,
                        color: AppColors.primaryGreen, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      '+RM ${walletCredit.toStringAsFixed(2)} added to wallet',
                      style: TextStyle(
                          color: AppColors.primaryGreen,
                          fontWeight: FontWeight.w600,
                          fontSize: 14),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 8),
            Text(
              'Remaining: ${result['points_after'] ?? 0} pts',
              style: TextStyle(color: AppColors.textLight, fontSize: 13),
            ),
          ],
        ),
        actions: [
          Center(
            child: ElevatedButton(
              onPressed: () => Navigator.pop(ctx),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                foregroundColor: AppColors.background,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
                padding:
                    const EdgeInsets.symmetric(horizontal: 40, vertical: 12),
              ),
              child: const Text('Awesome!',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: AppColors.error,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Rewards'),
        backgroundColor: Colors.transparent,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppColors.primaryGreen,
          labelColor: AppColors.primaryGreen,
          unselectedLabelColor: AppColors.textLight,
          indicatorWeight: 3,
          tabs: const [
            Tab(text: 'Rewards'),
            Tab(text: 'History'),
          ],
        ),
      ),
      body: Consumer<AuthProvider>(
        builder: (context, authProvider, _) {
          final user = authProvider.currentUser;
          final points = user?.walletPoints ?? 0;
          
          return Stack(
            children: [
              TabBarView(
                controller: _tabController,
                children: [
                  // ===== TAB 1: REWARDS =====
                  RefreshIndicator(
                    color: AppColors.primaryGreen,
                    backgroundColor: AppColors.cardBackground,
                    onRefresh: () async {
                      await _loadCatalog();
                      await authProvider.refreshProfile();
                    },
                    child: SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Points Card
                          _buildPointsCard(points),
                          const SizedBox(height: 24),

                          // Earn more section
                          _buildEarnSection(),
                          const SizedBox(height: 24),

                          // Available Rewards
                          Text(
                            'AVAILABLE REWARDS',
                            style: TextStyle(
                              color: AppColors.primaryGreen.withOpacity(0.7),
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 1,
                            ),
                          ),
                          const SizedBox(height: 16),

                          if (_loadingCatalog)
                            Center(
                              child: Padding(
                                padding: const EdgeInsets.all(40),
                                child: CircularProgressIndicator(
                                    color: AppColors.primaryGreen),
                              ),
                            )
                          else if (_catalog.isEmpty)
                            _buildEmptyState(
                                'No rewards available', Icons.card_giftcard)
                          else
                            ..._catalog.map((reward) => _RewardCard(
                                  title: reward['title'] ?? '',
                                  points: reward['points_cost'] ?? 0,
                                  description: reward['description'] ?? '',
                                  icon: _getIconFromName(
                                      reward['icon'] ?? 'card_giftcard'),
                                  walletCredit:
                                      (reward['wallet_credit'] ?? 0.0)
                                          as num,
                                  userPoints: points,
                                  onRedeem: () => _redeemReward(reward),
                                )),
                          const SizedBox(height: 40),
                        ],
                      ),
                    ),
                  ),

                  // ===== TAB 2: HISTORY =====
                  RefreshIndicator(
                    color: AppColors.primaryGreen,
                    backgroundColor: AppColors.cardBackground,
                    onRefresh: _loadHistory,
                    child: _loadingHistory
                        ? Center(
                            child: CircularProgressIndicator(
                                color: AppColors.primaryGreen))
                        : _history.isEmpty
                            ? SingleChildScrollView(
                                physics:
                                    const AlwaysScrollableScrollPhysics(),
                                child: SizedBox(
                                  height: MediaQuery.of(context).size.height * 0.5,
                                  child: _buildEmptyState(
                                    'No redemption history yet',
                                    Icons.history,
                                  ),
                                ),
                              )
                            : ListView.builder(
                                padding: const EdgeInsets.all(16),
                                itemCount: _history.length,
                                itemBuilder: (context, index) {
                                  return _buildHistoryItem(
                                      _history[index]);
                                },
                              ),
                  ),
                ],
              ),

              // Loading overlay when redeeming
              if (_redeeming)
                Container(
                  color: Colors.black54,
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.all(32),
                      decoration: BoxDecoration(
                        color: AppColors.cardBackground,
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primaryGreen.withOpacity(0.2),
                            blurRadius: 30,
                          ),
                        ],
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          SizedBox(
                            width: 50,
                            height: 50,
                            child: CircularProgressIndicator(
                              color: AppColors.primaryGreen,
                              strokeWidth: 3,
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text('Redeeming...',
                              style: TextStyle(
                                  color: AppColors.textPrimary,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildPointsCard(int points) {
    // Find cheapest reward to show progress
    int? cheapestCost;
    String? cheapestTitle;
    if (_catalog.isNotEmpty) {
      final sorted = List<Map<String, dynamic>>.from(_catalog)
        ..sort((a, b) =>
            (a['points_cost'] as int).compareTo(b['points_cost'] as int));
      // Find the cheapest reward user hasn't reached yet, or the cheapest
      for (final r in sorted) {
        if ((r['points_cost'] as int) > points) {
          cheapestCost = r['points_cost'] as int;
          cheapestTitle = r['title'] as String;
          break;
        }
      }
      cheapestCost ??= sorted.last['points_cost'] as int;
      cheapestTitle ??= sorted.last['title'] as String;
    }

    return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: AppColors.primaryGradient,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
          BoxShadow(
              color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15),
                    ],
                  ),
                  child: Column(
                    children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.stars, color: Colors.white.withOpacity(0.9), size: 22),
              const SizedBox(width: 8),
              Text('Your Points',
                  style: TextStyle(
                      color: Colors.white.withOpacity(0.9), fontSize: 16)),
            ],
          ),
          const SizedBox(height: 8),
          TweenAnimationBuilder<int>(
            tween: IntTween(begin: 0, end: points),
            duration: const Duration(milliseconds: 800),
            curve: Curves.easeOutCubic,
            builder: (context, value, child) {
              return Text(
                value.toString(),
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 48,
                    fontWeight: FontWeight.bold),
              );
            },
          ),

          // Progress to next reward
          if (cheapestCost != null && cheapestTitle != null) ...[
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: (points / cheapestCost).clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: Colors.white.withOpacity(0.2),
                valueColor:
                    const AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            ),
                      const SizedBox(height: 8),
                      Text(
              points >= cheapestCost
                  ? '🎉 You can redeem $cheapestTitle!'
                  : '${cheapestCost - points} pts more for $cheapestTitle',
              style: TextStyle(
                  color: Colors.white.withOpacity(0.85),
                  fontSize: 12,
                  fontWeight: FontWeight.w500),
                      ),
          ],

                      const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () {
              _tabController.animateTo(1);
              if (_history.isEmpty && !_loadingHistory) _loadHistory();
            },
            icon: const Icon(Icons.history, size: 18),
            label: const Text('View History'),
            style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
              side: BorderSide(color: Colors.white.withOpacity(0.4)),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
              padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            ),
                      ),
                    ],
                  ),
    );
  }

  Widget _buildEarnSection() {
    return Container(
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
              Icon(Icons.info_outline,
                  color: AppColors.primaryGreen.withOpacity(0.7), size: 18),
              const SizedBox(width: 8),
              Text('HOW TO EARN POINTS',
                  style: TextStyle(
                      color: AppColors.primaryGreen.withOpacity(0.7),
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 1)),
            ],
          ),
          const SizedBox(height: 12),
          _earnRow(Icons.bolt, 'Charge your EV', '1 pt per RM spent'),
          _earnRow(Icons.login, 'Daily login', '+5 pts per day'),
          _earnRow(Icons.rate_review, 'Leave a review', '+50 pts'),
          _earnRow(Icons.person_add, 'Refer a friend', '+200 pts'),
        ],
      ),
    );
  }

  Widget _earnRow(IconData icon, String title, String subtitle) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, color: AppColors.primaryGreen.withOpacity(0.6), size: 18),
          const SizedBox(width: 12),
          Expanded(
            child: Text(title,
                style: TextStyle(
                    color: AppColors.textSecondary, fontSize: 13)),
          ),
          Text(subtitle,
              style: TextStyle(
                  color: AppColors.primaryGreen,
                  fontSize: 12,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildHistoryItem(Map<String, dynamic> item) {
    final title = item['reward_title'] ?? 'Unknown Reward';
    final pointsCost = item['points_cost'] ?? 0;
    final walletCredit = item['wallet_credit'];
    final status = item['status'] ?? 'completed';
    final redeemedAt = item['redeemed_at'] != null
        ? DateTime.tryParse(item['redeemed_at'])
        : null;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        children: [
          // Status icon
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: (status == 'completed'
                      ? AppColors.primaryGreen
                      : AppColors.warning)
                  .withOpacity(0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              status == 'completed' ? Icons.check_circle : Icons.pending,
              color: status == 'completed'
                  ? AppColors.primaryGreen
                  : AppColors.warning,
              size: 24,
            ),
          ),
          const SizedBox(width: 14),
          // Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w600,
                        fontSize: 14)),
                const SizedBox(height: 4),
                Text(
                  redeemedAt != null
                      ? '${redeemedAt.day}/${redeemedAt.month}/${redeemedAt.year} ${redeemedAt.hour.toString().padLeft(2, '0')}:${redeemedAt.minute.toString().padLeft(2, '0')}'
                      : 'Unknown date',
                  style: TextStyle(color: AppColors.textLight, fontSize: 12),
                ),
              ],
            ),
          ),
          // Points & credit
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('-$pointsCost pts',
                  style: TextStyle(
                      color: AppColors.warning,
                      fontWeight: FontWeight.bold,
                      fontSize: 13)),
              if (walletCredit != null && walletCredit > 0)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text('+RM ${(walletCredit as num).toStringAsFixed(2)}',
                      style: TextStyle(
                          color: AppColors.primaryGreen,
                          fontSize: 12,
                          fontWeight: FontWeight.w600)),
                ),
            ],
          ),
              ],
            ),
          );
  }

  Widget _buildEmptyState(String message, IconData icon) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: AppColors.textLight.withOpacity(0.3), size: 60),
          const SizedBox(height: 16),
          Text(message,
              style: TextStyle(color: AppColors.textLight, fontSize: 15)),
          const SizedBox(height: 8),
          Text('Pull down to refresh',
              style: TextStyle(
                  color: AppColors.textLight.withOpacity(0.5),
                  fontSize: 12)),
        ],
      ),
    );
  }

  IconData _getIconFromName(String name) {
    switch (name) {
      case 'card_giftcard':
        return Icons.card_giftcard;
      case 'bolt':
        return Icons.bolt;
      case 'star':
        return Icons.star;
      case 'local_offer':
        return Icons.local_offer;
      default:
        return Icons.card_giftcard;
    }
  }
}

// ==================== REWARD CARD ====================

class _RewardCard extends StatelessWidget {
  final String title;
  final int points;
  final String description;
  final IconData icon;
  final num walletCredit;
  final int userPoints;
  final VoidCallback onRedeem;

  const _RewardCard({
    required this.title,
    required this.points,
    required this.description,
    required this.icon,
    required this.walletCredit,
    required this.userPoints,
    required this.onRedeem,
  });

  @override
  Widget build(BuildContext context) {
    final canRedeem = userPoints >= points;
    final progress = (userPoints / points).clamp(0.0, 1.0);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: canRedeem
              ? AppColors.primaryGreen.withOpacity(0.3)
              : AppColors.borderLight,
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              // Icon
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
                  color: AppColors.primaryGreen.withOpacity(canRedeem ? 0.15 : 0.08),
              borderRadius: BorderRadius.circular(12),
            ),
                child: Icon(icon,
                    color: canRedeem
                        ? AppColors.primaryGreen
                        : AppColors.textLight),
          ),
          const SizedBox(width: 16),
              // Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                    Text(title,
                        style: TextStyle(
                            color: AppColors.textPrimary,
                            fontWeight: FontWeight.bold,
                            fontSize: 15)),
                    const SizedBox(height: 4),
                    Text(description,
                        style: TextStyle(
                            color: AppColors.textLight, fontSize: 12)),
                    if (walletCredit > 0) ...[
                const SizedBox(height: 4),
                      Text(
                        '+RM ${walletCredit.toStringAsFixed(2)} wallet credit',
                        style: TextStyle(
                            color: AppColors.primaryGreen.withOpacity(0.7),
                            fontSize: 11,
                            fontWeight: FontWeight.w500),
                      ),
                    ],
              ],
            ),
          ),
              // Points + Redeem
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
                  Text('$points pts',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: canRedeem
                              ? AppColors.primaryGreen
                              : AppColors.warning,
                          fontSize: 14)),
              const SizedBox(height: 8),
              ElevatedButton(
                    onPressed: onRedeem,
                style: ElevatedButton.styleFrom(
                      backgroundColor: canRedeem
                          ? AppColors.primaryGreen
                          : AppColors.surface,
                      foregroundColor:
                          canRedeem ? AppColors.background : AppColors.textLight,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 6),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                      elevation: canRedeem ? 2 : 0,
                ),
                    child: Text(
                      canRedeem ? 'Redeem' : 'Locked',
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ],
          ),
          // Progress bar (only show if can't redeem yet)
          if (!canRedeem) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 4,
                backgroundColor: AppColors.surface,
                valueColor:
                    AlwaysStoppedAnimation<Color>(AppColors.primaryGreen.withOpacity(0.6)),
              ),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                '${(progress * 100).toStringAsFixed(0)}% — ${points - userPoints} pts more',
                style: TextStyle(
                    color: AppColors.textLight.withOpacity(0.6), fontSize: 10),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
