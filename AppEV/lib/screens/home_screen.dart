import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/session_provider.dart';
import '../providers/charger_provider.dart';
import '../providers/notification_provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import 'topup_screen.dart';
import 'my_bookings_screen.dart';
import '../constants/app_colors.dart';
import '../widgets/header_widget.dart';
import '../widgets/bottom_nav_bar.dart';
import 'find_charger_screen.dart';
import 'live_charging_screen.dart';
import 'scan_screen.dart';
import 'profile_screen.dart';
import 'rewards_screen.dart';
import 'dcfc_chargers_screen.dart';
import 'auto_charge_screen.dart';
import 'chat_support_screen.dart';
import 'favourite_stations_screen.dart';
import 'charger_detail_screen.dart';
import 'notifications_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
// HOME SHELL — bottom-nav scaffold + animated tab switcher.
// ─────────────────────────────────────────────────────────────────────────────

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  int _currentIndex = 0;
  int _previousIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    FindChargerScreen(),
    ScanScreen(),
    RewardsScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    // Initial unread-badge fetch so the bell shows the right number before
    // the user opens the notifications screen.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<NotificationProvider>().refreshUnread();
      }
    });
  }

  void _onTabTapped(int index) {
    if (index == _currentIndex) return;
    setState(() {
      _previousIndex = _currentIndex;
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final bool goingForward = _currentIndex > _previousIndex;
    final screenW = MediaQuery.sizeOf(context).width;
    const double kMaxContentWidth = 600.0;
    final bool useConstrainedLayout = screenW > kMaxContentWidth;

    final scaffold = Scaffold(
      backgroundColor: AppColors.background,
      // Let body extend behind the floating nav bar so content shows through.
      extendBody: true,
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 280),
        switchInCurve: Curves.easeOutQuart,
        switchOutCurve: Curves.easeInOut,
        transitionBuilder: (Widget child, Animation<double> animation) {
          final bool isIncoming = child.key == ValueKey<int>(_currentIndex);
          final Offset beginOffset = isIncoming
              ? Offset(goingForward ? 1.0 : -1.0, 0.0)
              : Offset(goingForward ? -1.0 : 1.0, 0.0);

          return SlideTransition(
            position: Tween<Offset>(begin: beginOffset, end: Offset.zero).animate(animation),
            child: child,
          );
        },
        child: KeyedSubtree(
          key: ValueKey<int>(_currentIndex),
          child: _screens[_currentIndex],
        ),
      ),
      floatingActionButton: _SupportFab(
        onPressed: () async {
          if (kIsWeb) {
            const botUrl = String.fromEnvironment('BOT_BASE_URL', defaultValue: '');
            const apiUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
            final derivedBotUrl = apiUrl.isNotEmpty
                ? '${Uri.parse(apiUrl).scheme}://${Uri.parse(apiUrl).host}/bot'
                : 'http://localhost:8001';
            final url = botUrl.isNotEmpty ? botUrl : derivedBotUrl;
            await launchUrl(Uri.parse(url), mode: LaunchMode.platformDefault);
          } else {
            Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatSupportScreen()));
          }
        },
      ),
      bottomNavigationBar: BottomNavBar(
        currentIndex: _currentIndex,
        onTap: _onTabTapped,
      ),
    );

    if (useConstrainedLayout) {
      return Container(
        color: AppColors.background,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxContentWidth),
            child: scaffold,
          ),
        ),
      );
    }
    return scaffold;
  }
}

// Quiet, solid support FAB (no gradient, no glow halo).
class _SupportFab extends StatelessWidget {
  final VoidCallback onPressed;
  const _SupportFab({required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      onPressed: onPressed,
      backgroundColor: AppColors.primaryGreen,
      foregroundColor: AppColors.background,
      elevation: 0,
      highlightElevation: 0,
      shape: const CircleBorder(),
      child: const Icon(Icons.support_agent, size: 26),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD — "Explore" tab. Vibrant Grab/TnG wallet-style: gradient balance
// card on top, colourful action grid, promo banner, then nearby stations.
// ─────────────────────────────────────────────────────────────────────────────

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _wallet;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadWallet());
  }

  Future<void> _loadWallet() async {
    final user = context.read<AuthProvider>().currentUser;
    if (user == null) return;
    final w = await ApiService.getWallet(user.id);
    if (mounted) setState(() => _wallet = w);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () async {
            await Future.wait([
              Provider.of<SessionProvider>(context, listen: false).loadActiveSession(),
              Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers(),
              Provider.of<NotificationProvider>(context, listen: false).refreshUnread(),
              _loadWallet(),
            ]);
          },
          color: AppColors.primaryGreen,
          backgroundColor: AppColors.cardBackground,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Brand + bell
                HeaderWidget(
                  onNotificationTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                  ),
                ),

                const SizedBox(height: 8),

                // ── WALLET BALANCE CARD ── (the headline)
                _WalletHero(wallet: _wallet),

                const SizedBox(height: 22),

                // ── COLOURFUL ACTION STRIP ── (5 quick actions)
                const _ActionStrip(),

                const SizedBox(height: 26),

                // ── PROMO BANNER ── (gradient CTA)
                const _PromoBanner(),

                const SizedBox(height: 26),

                // ── STATS STRIP ── (live activity)
                const _StatsStrip(),

                const SizedBox(height: 26),

                // ── NEARBY stations ──
                _SectionHeader(
                  title: 'Nearby Stations',
                  actionLabel: 'See all',
                  onAction: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const FavouriteStationsScreen()),
                  ),
                ),
                const SizedBox(height: 10),
                Consumer<ChargerProvider>(
                  builder: (context, cp, _) {
                    if (cp.isLoading) return const _LoadingRow();
                    if (cp.nearbyChargers.isEmpty) {
                      return const _EmptyRow(text: 'No stations within range');
                    }
                    final list = cp.nearbyChargers.take(4).toList();
                    return Column(
                      children: list.map((c) => _StationRow(charger: c)).toList(),
                    );
                  },
                ),

                // Bottom breathing room (above floating nav + FAB).
                const SizedBox(height: 140),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// HERO — the single big block at the top. Mirrors a Tesla "vehicle status"
// card: large thin numeric, small qualifier line.
//   • Active session → kWh delivered, charger id.
//   • Idle → quiet welcome line.
// ─────────────────────────────────────────────────────────────────────────────

class _HeroBlock extends StatelessWidget {
  const _HeroBlock();

  static double _num(dynamic v) {
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? 0.0;
    return 0.0;
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Consumer<SessionProvider>(
        builder: (context, sp, _) {
          final session = sp.activeSession;
          if (session != null) {
            final chargerId = session['charge_point_id']?.toString()
                ?? session['charger_id']?.toString()
                ?? 'Charger';
            final energy = _num(session['energy']);
            final power = _num(session['power']);
            return GestureDetector(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const LiveChargingScreen()),
              ),
              behavior: HitTestBehavior.opaque,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          color: AppColors.primaryGreen,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'CHARGING',
                        style: TextStyle(
                          color: AppColors.primaryGreen,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 2.5,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  // FittedBox so the giant kWh number never overflows on
                  // narrow viewports — shrinks as a unit with its 'kWh' suffix.
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        energy.toStringAsFixed(1),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 68,
                          fontWeight: FontWeight.w200,
                          height: 1.0,
                          letterSpacing: -2.5,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          'kWh',
                          style: TextStyle(
                            color: AppColors.textLight,
                            fontSize: 16,
                            fontWeight: FontWeight.w300,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    power > 0
                        ? '$chargerId · ${power.toStringAsFixed(1)} kW now'
                        : chargerId,
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                      fontWeight: FontWeight.w300,
                      letterSpacing: 0.4,
                    ),
                  ),
                ],
              ),
            );
          }
          // Idle
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(width: 14, height: 1, color: AppColors.premiumGold),
                  const SizedBox(width: 10),
                  Text(
                    'WELCOME',
                    style: TextStyle(
                      color: AppColors.premiumGold,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 2.5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              // FittedBox shrinks the headline cleanly on narrow viewports
              // (avoids the right-edge overflow seen on small mobile widths).
              const FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  'Ready to charge.',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 38,
                    fontWeight: FontWeight.w300,
                    height: 1.1,
                    letterSpacing: -0.5,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'No active session.',
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 14,
                  fontWeight: FontWeight.w300,
                  letterSpacing: 0.3,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION LABEL — gold dash + tiny uppercase letter-spaced text.
// ─────────────────────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  final String label;
  const _SectionLabel(this.label);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Container(width: 14, height: 1, color: AppColors.premiumGold),
          const SizedBox(width: 10),
          Text(
            label,
            style: TextStyle(
              color: AppColors.premiumGold,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 2.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabelRow extends StatelessWidget {
  final String label;
  final Widget trailing;
  const _SectionLabelRow({required this.label, required this.trailing});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Container(width: 14, height: 1, color: AppColors.premiumGold),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: AppColors.premiumGold,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 2.5,
              ),
            ),
          ),
          trailing,
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// QUICK ROW — 3 minimal action tiles. Outline only, no fills, no glow.
// (DC Fast, AutoCharge, Scan — the actions a user reaches for most.)
// ─────────────────────────────────────────────────────────────────────────────

class _QuickRow extends StatelessWidget {
  const _QuickRow();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Expanded(
            child: _QuickItem(
              icon: Icons.bolt_rounded,
              label: 'DC Fast',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const DCFCChargersScreen()),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _QuickItem(
              icon: Icons.auto_awesome_rounded,
              label: 'AutoCharge',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AutoChargeScreen()),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _QuickItem(
              icon: Icons.qr_code_scanner_rounded,
              label: 'Scan',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ScanScreen()),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _QuickItem({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borderHairline),
          borderRadius: BorderRadius.circular(2),
        ),
        child: Column(
          children: [
            Icon(icon, color: Colors.white, size: 22),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w400,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// STATION ROW — full-width vertical row. Status dot + tiny uppercase label
// on the right; name big-ish on the left; vendor / kW / price on a second
// line. Outline border only — no fills, no gradients.
// ─────────────────────────────────────────────────────────────────────────────

class _StationRow extends StatelessWidget {
  final Map<String, dynamic> charger;
  const _StationRow({required this.charger});

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id']?.toString() ?? 'Station';
    final status = charger['status']?.toString() ?? 'unknown';
    final availability = charger['availability']?.toString() ?? 'unknown';
    final vendor = charger['vendor']?.toString() ?? '';
    final model = charger['model']?.toString() ?? '';
    final maxKw = charger['max_power_kw'];
    final price = charger['tariff_per_kwh'] ?? charger['price_per_kwh'];

    final isOnline = status == 'online';
    final isAvailable = isOnline && (availability == 'available' || availability == 'preparing');
    final isCharging = availability == 'charging';

    Color dotColor;
    String statusText;
    if (!isOnline) {
      dotColor = Colors.grey.shade600;
      statusText = 'OFFLINE';
    } else if (isCharging) {
      dotColor = AppColors.warning;
      statusText = 'IN USE';
    } else if (isAvailable) {
      dotColor = AppColors.primaryGreen;
      statusText = 'AVAILABLE';
    } else {
      dotColor = Colors.grey.shade600;
      statusText = availability.toUpperCase();
    }

    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger)),
      ),
      behavior: HitTestBehavior.opaque,
      child: Container(
        margin: const EdgeInsets.fromLTRB(24, 0, 24, 10),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borderHairline),
          borderRadius: BorderRadius.circular(2),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(
                  statusText,
                  style: TextStyle(
                    color: dotColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: Text(
                    (vendor.isNotEmpty || model.isNotEmpty)
                        ? [vendor, model].where((s) => s.isNotEmpty).join(' · ')
                        : '—',
                    style: TextStyle(
                      color: AppColors.textLight,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w400,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (maxKw is num) ...[
                  Text(
                    '${maxKw.toStringAsFixed(0)} kW',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
                if (price is num)
                  Text(
                    'RM ${price.toStringAsFixed(2)}/kWh',
                    style: TextStyle(
                      color: AppColors.premiumGold,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0.3,
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty / Loading rows — same minimal outline aesthetic.
// ─────────────────────────────────────────────────────────────────────────────

class _EmptyRow extends StatelessWidget {
  final String text;
  const _EmptyRow({required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 22, horizontal: 18),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borderHairline),
          borderRadius: BorderRadius.circular(2),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: AppColors.textLight,
            fontSize: 12,
            fontWeight: FontWeight.w400,
            letterSpacing: 0.3,
          ),
        ),
      ),
    );
  }
}

class _LoadingRow extends StatelessWidget {
  const _LoadingRow();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Container(
        height: 72,
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borderHairline),
          borderRadius: BorderRadius.circular(2),
        ),
        child: Center(
          child: SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              color: AppColors.premiumGold,
              strokeWidth: 1.5,
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// NEW VIBRANT WIDGETS — Grab/TnG wallet aesthetic
// ═══════════════════════════════════════════════════════════════════════════

// ── WALLET HERO ─────────────────────────────────────────────────────────────
// Green→teal gradient card. Balance is the focal point; points + Top Up CTA
// sit underneath. Watermark wallet icon adds depth without competing.
class _WalletHero extends StatelessWidget {
  final Map<String, dynamic>? wallet;
  const _WalletHero({required this.wallet});

  @override
  Widget build(BuildContext context) {
    final balance = (wallet?['balance'] as num?)?.toDouble() ?? 0.0;
    final points = (wallet?['points'] as num?)?.toInt() ?? 0;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
        padding: const EdgeInsets.fromLTRB(22, 20, 22, 18),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF00C870), Color(0xFF00875A), Color(0xFF0F4A38)],
            stops: [0.0, 0.55, 1.0],
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: AppColors.primaryGreen.withOpacity(0.25),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Stack(
          children: [
            Positioned(
              right: -8,
              top: -8,
              child: Icon(
                Icons.account_balance_wallet_rounded,
                size: 110,
                color: Colors.white.withOpacity(0.06),
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.18),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: const [
                      Icon(Icons.bolt_rounded, color: Colors.white, size: 11),
                      SizedBox(width: 3),
                      Text(
                        'PLAGSINI WALLET',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'RM',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.75),
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      balance.toStringAsFixed(2),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 36,
                        fontWeight: FontWeight.w800,
                        height: 1.0,
                        letterSpacing: -1.0,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Icon(Icons.star_rounded, color: Colors.amber.shade300, size: 16),
                    const SizedBox(width: 4),
                    Text(
                      '$points Points',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.92),
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    GestureDetector(
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const TopUpScreen()),
                      ),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            Icon(Icons.add_rounded, color: Color(0xFF00875A), size: 16),
                            SizedBox(width: 4),
                            Text(
                              'Top Up',
                              style: TextStyle(
                                color: Color(0xFF00875A),
                                fontSize: 12.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ── ACTION STRIP ────────────────────────────────────────────────────────────
class _ActionStrip extends StatelessWidget {
  const _ActionStrip();

  static const _items = [
    _ActionSpec(label: 'Find', icon: Icons.search_rounded, c1: Color(0xFF4FC3F7), c2: Color(0xFF1976D2)),
    _ActionSpec(label: 'DC Fast', icon: Icons.flash_on_rounded, c1: Color(0xFFFFB74D), c2: Color(0xFFE65100)),
    _ActionSpec(label: 'Scan', icon: Icons.qr_code_scanner_rounded, c1: Color(0xFFBA68C8), c2: Color(0xFF6A1B9A)),
    _ActionSpec(label: 'Auto', icon: Icons.auto_awesome_rounded, c1: Color(0xFF81C784), c2: Color(0xFF2E7D32)),
    _ActionSpec(label: 'Schedule', icon: Icons.schedule_rounded, c1: Color(0xFFF06292), c2: Color(0xFFAD1457)),
  ];

  void _navigate(BuildContext context, String label) {
    switch (label) {
      case 'Find':
        Navigator.push(context, MaterialPageRoute(builder: (_) => const FindChargerScreen()));
        break;
      case 'DC Fast':
        Navigator.push(context, MaterialPageRoute(builder: (_) => const DCFCChargersScreen()));
        break;
      case 'Scan':
        Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen()));
        break;
      case 'Auto':
        Navigator.push(context, MaterialPageRoute(builder: (_) => const AutoChargeScreen()));
        break;
      case 'Schedule':
        Navigator.push(context, MaterialPageRoute(builder: (_) => const MyBookingsScreen()));
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: _items.map((s) {
          return GestureDetector(
            onTap: () => _navigate(context, s.label),
            behavior: HitTestBehavior.opaque,
            child: Column(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [s.c1, s.c2],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: s.c2.withOpacity(0.35),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Icon(s.icon, color: Colors.white, size: 24),
                ),
                const SizedBox(height: 7),
                SizedBox(
                  width: 60,
                  child: Text(
                    s.label,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _ActionSpec {
  final String label;
  final IconData icon;
  final Color c1;
  final Color c2;
  const _ActionSpec({required this.label, required this.icon, required this.c1, required this.c2});
}

// ── PROMO BANNER ────────────────────────────────────────────────────────────
class _PromoBanner extends StatelessWidget {
  const _PromoBanner();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 18, 16, 18),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF6B5BFF), Color(0xFFA855F7), Color(0xFFEC4899)],
            stops: [0.0, 0.55, 1.0],
          ),
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF6B5BFF).withOpacity(0.25),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.22),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Text(
                      'WEEKEND BOOST',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Earn 2× points\non every kWh',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      height: 1.15,
                      letterSpacing: -0.2,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Charge today and stack rewards faster.',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.85),
                      fontSize: 11.5,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.18),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(Icons.local_fire_department_rounded, color: Colors.white, size: 36),
            ),
          ],
        ),
      ),
    );
  }
}

// ── STATS STRIP ─────────────────────────────────────────────────────────────
class _StatsStrip extends StatelessWidget {
  const _StatsStrip();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: const [
          Expanded(child: _StatPill(label: 'kWh used', value: '0.0', accent: Color(0xFF4FC3F7), icon: Icons.bolt_rounded)),
          SizedBox(width: 10),
          Expanded(child: _StatPill(label: 'Sessions', value: '0', accent: Color(0xFF81C784), icon: Icons.history_rounded)),
          SizedBox(width: 10),
          Expanded(child: _StatPill(label: 'CO₂ saved', value: '0 kg', accent: Color(0xFFA855F7), icon: Icons.eco_rounded)),
        ],
      ),
    );
  }
}

class _StatPill extends StatelessWidget {
  final String label;
  final String value;
  final Color accent;
  final IconData icon;
  const _StatPill({required this.label, required this.value, required this.accent, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 11, 12, 11),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: accent.withOpacity(0.18), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: accent, size: 14),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: AppColors.textLight,
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 17,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.3,
            ),
          ),
        ],
      ),
    );
  }
}

// ── SECTION HEADER ──────────────────────────────────────────────────────────
class _SectionHeader extends StatelessWidget {
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;
  const _SectionHeader({required this.title, this.actionLabel, this.onAction});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.2,
            ),
          ),
          const Spacer(),
          if (actionLabel != null)
            GestureDetector(
              onTap: onAction,
              child: Row(
                children: [
                  Text(
                    actionLabel!,
                    style: TextStyle(
                      color: AppColors.primaryGreen,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 2),
                  Icon(Icons.chevron_right_rounded, color: AppColors.primaryGreen, size: 16),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
