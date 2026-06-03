import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/session_provider.dart';
import '../providers/charger_provider.dart';
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
// DASHBOARD — the "Explore" tab. Tesla-app aesthetic: near-black surface,
// gold section markers, large thin hero type, calm spacing, no card clutter.
// ─────────────────────────────────────────────────────────────────────────────

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () async {
            await Provider.of<SessionProvider>(context, listen: false).loadActiveSession();
            await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
          },
          color: AppColors.premiumGold,
          backgroundColor: AppColors.cardBackground,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header (brand + notifications) — keep existing widget so the bell
                // and unread badge logic stays intact.
                HeaderWidget(
                  onNotificationTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                  ),
                ),

                const SizedBox(height: 26),

                // ── HERO ──
                const _HeroBlock(),

                const SizedBox(height: 44),

                // ── QUICK actions — 3 only, inline tiles ──
                const _SectionLabel('QUICK'),
                const SizedBox(height: 14),
                const _QuickRow(),

                const SizedBox(height: 44),

                // ── NEARBY stations — vertical, rich rows ──
                Consumer<ChargerProvider>(
                  builder: (context, cp, _) => _SectionLabelRow(
                    label: 'NEARBY',
                    trailing: Text(
                      cp.nearbyChargers.isEmpty ? '—' : cp.nearbyChargers.length.toString(),
                      style: TextStyle(
                        color: AppColors.premiumGold,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
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

                const SizedBox(height: 44),

                // ── FAVOURITES — minimal, link to full list ──
                _SectionLabelRow(
                  label: 'FAVOURITES',
                  trailing: GestureDetector(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const FavouriteStationsScreen()),
                    ),
                    child: Text(
                      'SEE ALL',
                      style: TextStyle(
                        color: AppColors.premiumGold,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                const _EmptyRow(text: 'No favourites yet'),

                // Bottom breathing room (above bottom nav + FAB).
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
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
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
              const Text(
                'Ready to charge.',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 38,
                  fontWeight: FontWeight.w300,
                  height: 1.1,
                  letterSpacing: -0.5,
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
