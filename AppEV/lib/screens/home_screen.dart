import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/session_provider.dart';
import '../providers/charger_provider.dart';
import '../constants/app_colors.dart';
import '../widgets/featured_station_card.dart';
import '../widgets/nearby_station_card.dart';
import '../widgets/category_icon.dart';
import '../widgets/header_widget.dart';
import '../widgets/bottom_nav_bar.dart';
import 'find_charger_screen.dart';
import 'live_charging_screen.dart';
import 'scan_screen.dart';
import 'profile_screen.dart';
import 'rewards_screen.dart';
import 'dcfc_chargers_screen.dart';
import 'auto_charge_screen.dart';
import 'offline_chargers_screen.dart';
import 'new_sites_screen.dart';
import 'promotions_screen.dart';
import 'chat_support_screen.dart';
import 'invite_friends_screen.dart';
import 'business_accounts_screen.dart';
import 'favourite_stations_screen.dart';
import 'charger_detail_screen.dart';
import 'notifications_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  int _currentIndex = 0;
  int _previousIndex = 0;
  late AnimationController _pulseController;
  late AnimationController _gradientController;

  final List<Widget> _screens = [
    const DashboardScreen(),
    const FindChargerScreen(),
    const ScanScreen(),
    const RewardsScreen(),
    const ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _gradientController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _gradientController.dispose();
    super.dispose();
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
    // Slide direction: right-to-left when going forward, left-to-right when going back
    final bool goingForward = _currentIndex > _previousIndex;
    final screenW = MediaQuery.sizeOf(context).width;
    // On desktop/wide screens: center content with max width to avoid stretched layout
    const double kMaxContentWidth = 600.0;
    final bool useConstrainedLayout = screenW > kMaxContentWidth;

    final scaffold = Scaffold(
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 300),
        switchInCurve: Curves.easeInOut,
        switchOutCurve: Curves.easeInOut,
        transitionBuilder: (Widget child, Animation<double> animation) {
          // Determine if this child is the incoming or outgoing widget
          final bool isIncoming = child.key == ValueKey<int>(_currentIndex);
          final Offset beginOffset = isIncoming
              ? Offset(goingForward ? 1.0 : -1.0, 0.0)
              : Offset(goingForward ? -1.0 : 1.0, 0.0);

          return SlideTransition(
            position: Tween<Offset>(
              begin: beginOffset,
              end: Offset.zero,
            ).animate(animation),
            child: child,
          );
        },
        child: KeyedSubtree(
          key: ValueKey<int>(_currentIndex),
          child: _screens[_currentIndex],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          if (kIsWeb) {
            // On web: open the customer service chat page directly
            const botUrl = String.fromEnvironment('BOT_BASE_URL', defaultValue: '');
            // Default to /bot/ path through Nginx (not direct port 8001)
            const apiUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
            final derivedBotUrl = apiUrl.isNotEmpty
                ? '${Uri.parse(apiUrl).scheme}://${Uri.parse(apiUrl).host}/bot'
                : 'http://localhost:8001';
            final url = botUrl.isNotEmpty ? botUrl : derivedBotUrl;
            await launchUrl(Uri.parse(url), mode: LaunchMode.platformDefault);
          } else {
            // On mobile: use native Flutter chat screen
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ChatSupportScreen()),
            );
          }
        },
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF00FF88), Color(0xFF00AA55)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF00FF88).withOpacity(0.4),
                blurRadius: 12,
                spreadRadius: 1,
              ),
            ],
          ),
          child: const Icon(Icons.support_agent, color: Colors.black, size: 28),
        ),
      ),
      bottomNavigationBar: BottomNavBar(
        currentIndex: _currentIndex,
        onTap: _onTabTapped,
      ),
    );

    // On wide screens: center content with max width for better responsiveness
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

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            await Provider.of<SessionProvider>(context, listen: false).loadActiveSession();
            await Provider.of<ChargerProvider>(context, listen: false).loadNearbyChargers();
          },
          color: AppColors.primaryGreen,
          backgroundColor: AppColors.cardBackground,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ===== HEADER =====
                HeaderWidget(
                  onNotificationTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                    );
                  },
                ),

                const SizedBox(height: 4),

                // ===== HUMAN-FRIENDLY WELCOME CARD =====
                const _WelcomeCard(),

                // ===== ACTIVE SESSION BANNER =====
                Consumer<SessionProvider>(
                  builder: (context, sessionProvider, _) {
                    final session = sessionProvider.activeSession;
                    if (session == null) return const SizedBox.shrink();
                    return _ActiveSessionBanner(session: session);
                  },
                ),

                // ===== QUICK ACTIONS =====
                _sectionHeader(context, 'Quick Actions'),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: GridView.count(
                    crossAxisCount: 4,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: 0.68,
                    children: [
                      CategoryIcon(
                        icon: Icons.bolt_rounded,
                        label: 'DCFC',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const DCFCChargersScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.auto_awesome_rounded,
                        label: 'AutoCharge',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AutoChargeScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.build_rounded,
                        label: 'Offline',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const OfflineChargersScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.new_releases_rounded,
                        label: 'New Sites',
                        badge: 'NEW',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NewSitesScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.percent_rounded,
                        label: 'Promotions',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const PromotionsScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.card_giftcard_rounded,
                        label: 'Rewards',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RewardsScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.share_rounded,
                        label: 'Referral',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const InviteFriendsScreen())),
                      ),
                      CategoryIcon(
                        icon: Icons.business_rounded,
                        label: 'Business',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BusinessAccountsScreen())),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // ===== NEARBY STATIONS =====
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Nearby Stations',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: AppColors.textPrimary, fontWeight: FontWeight.bold)),
                      Consumer<ChargerProvider>(
                        builder: (context, cp, _) => Text(
                          '${cp.nearbyChargers.length} found',
                          style: TextStyle(color: AppColors.textLight, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                Consumer<ChargerProvider>(
                  builder: (context, chargerProvider, _) {
                    if (chargerProvider.isLoading) {
                      return const SizedBox(
                        height: 110,
                        child: Center(child: CircularProgressIndicator(color: AppColors.primaryGreen)),
                      );
                    }
                    if (chargerProvider.nearbyChargers.isEmpty) {
                      return _emptySection('No chargers found', Icons.ev_station_outlined);
                    }
                    return SizedBox(
                      height: 125,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        itemCount: chargerProvider.nearbyChargers.length,
                        itemBuilder: (context, index) {
                          return NearbyStationCard(charger: chargerProvider.nearbyChargers[index]);
                        },
                      ),
                    );
                  },
                ),

                const SizedBox(height: 24),

                // ===== FEATURED / RECOMMENDED =====
                _sectionHeader(context, 'Recommended'),
                const SizedBox(height: 12),
                Consumer<ChargerProvider>(
                  builder: (context, chargerProvider, _) {
                    if (chargerProvider.isLoading) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        child: _shimmerCard(),
                      );
                    }
                    if (chargerProvider.nearbyChargers.isEmpty) {
                      return _emptySection('No chargers available', Icons.ev_station_outlined);
                    }
                    // Show the first available charger, or first charger
                    final featured = chargerProvider.nearbyChargers.first;
                    return FeaturedStationCard(charger: featured);
                  },
                ),

                const SizedBox(height: 24),

                // ===== ALL CHARGERS LIST (compact) =====
                if (true) // Always show
                  Consumer<ChargerProvider>(
                    builder: (context, chargerProvider, _) {
                      if (chargerProvider.nearbyChargers.length <= 1) return const SizedBox.shrink();
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _sectionHeader(context, 'All Chargers'),
                          const SizedBox(height: 12),
                          ...chargerProvider.nearbyChargers.skip(1).map((charger) => _CompactChargerTile(charger: charger)),
                        ],
                      );
                    },
                  ),

                const SizedBox(height: 24),

                // ===== FAVOURITES =====
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Favourite Stations',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: AppColors.textPrimary, fontWeight: FontWeight.bold)),
                      GestureDetector(
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const FavouriteStationsScreen())),
                        child: Text('See all',
                            style: TextStyle(color: AppColors.primaryGreen, fontSize: 13, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Container(
                    height: 100,
                    decoration: BoxDecoration(
                      color: AppColors.surface.withOpacity(0.6),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.bookmark_border_rounded, color: AppColors.textLight.withOpacity(0.3), size: 32),
                          const SizedBox(height: 8),
                          Text('No favourite stations yet',
                              style: TextStyle(color: AppColors.textLight, fontSize: 13)),
                        ],
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 100), // Space for bottom nav
              ],
            ),
          ),
        ),
      ),
    );
  }

  static Widget _sectionHeader(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 16,
            decoration: BoxDecoration(
              color: AppColors.primaryGreen.withOpacity(0.8),
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          const SizedBox(width: 8),
          Text(title,
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(color: AppColors.textPrimary, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }

  static Widget _emptySection(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.surface.withOpacity(0.5),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Center(
          child: Column(
            children: [
              Icon(icon, color: AppColors.textLight.withOpacity(0.3), size: 36),
              const SizedBox(height: 8),
              Text(text, style: TextStyle(color: AppColors.textLight, fontSize: 13)),
            ],
          ),
        ),
      ),
    );
  }

  static Widget _shimmerCard() {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Center(
        child: CircularProgressIndicator(color: AppColors.primaryGreen, strokeWidth: 2),
      ),
    );
  }
}

class _WelcomeCard extends StatelessWidget {
  const _WelcomeCard();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF101A2A),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.handshake_rounded, color: AppColors.primaryGreen, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Welcome back',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Choose an action below to start your charging journey.',
                    style: TextStyle(
                      color: AppColors.textLight,
                      fontSize: 11.5,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== ACTIVE SESSION BANNER ====================

class _ActiveSessionBanner extends StatelessWidget {
  final Map<String, dynamic> session;

  const _ActiveSessionBanner({required this.session});

  @override
  Widget build(BuildContext context) {
    final chargerId = session['charger_id']?.toString() ?? 'Unknown';
    final energy = (session['energy'] ?? 0.0).toDouble();

    return GestureDetector(
      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const LiveChargingScreen())),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: [
            AppColors.primaryGreen.withOpacity(0.15),
            AppColors.primaryGreen.withOpacity(0.08),
          ]),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            // Animated pulse dot
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.bolt_rounded, color: AppColors.primaryGreen, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Charging in progress',
                      style: TextStyle(color: AppColors.primaryGreen, fontSize: 13, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 2),
                  Text('$chargerId · ${energy.toStringAsFixed(2)} kWh',
                      style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Text('View', style: TextStyle(color: AppColors.background, fontSize: 12, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== COMPACT CHARGER TILE ====================

class _CompactChargerTile extends StatelessWidget {
  final Map<String, dynamic> charger;

  const _CompactChargerTile({required this.charger});

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id']?.toString() ?? 'Station';
    final status = charger['status']?.toString() ?? 'unknown';
    final availability = charger['availability']?.toString() ?? 'unknown';
    final vendor = charger['vendor']?.toString() ?? '';
    final model = charger['model']?.toString() ?? '';
    final isOnline = status == 'online';
    final isAvailable = isOnline && (availability == 'available' || availability == 'preparing');
    final isCharging = availability == 'charging';

    Color dotColor;
    String statusText;
    if (!isOnline) {
      dotColor = Colors.grey;
      statusText = 'Offline';
    } else if (isAvailable) {
      dotColor = AppColors.primaryGreen;
      statusText = 'Available';
    } else if (isCharging) {
      dotColor = Colors.orange;
      statusText = 'In Use';
    } else {
      dotColor = Colors.grey;
      statusText = availability;
    }

    return GestureDetector(
      onTap: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => ChargerDetailScreen(charger: charger))),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Row(
          children: [
            // Icon
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [dotColor, dotColor.withOpacity(0.7)]),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.ev_station_rounded, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 12),
            // Name & vendor
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name,
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  if (vendor.isNotEmpty || model.isNotEmpty)
                    Text([vendor, model].where((s) => s.isNotEmpty).join(' · '),
                        style: TextStyle(color: AppColors.textLight, fontSize: 11),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            // Status
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: dotColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(width: 6, height: 6, decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle)),
                  const SizedBox(width: 4),
                  Text(statusText, style: TextStyle(color: dotColor, fontSize: 11, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
            const SizedBox(width: 6),
            Icon(Icons.chevron_right_rounded, color: AppColors.textLight, size: 20),
          ],
        ),
      ),
    );
  }
}
