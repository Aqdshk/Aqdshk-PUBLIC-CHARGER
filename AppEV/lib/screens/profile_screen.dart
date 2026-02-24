import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../constants/app_colors.dart';
import 'payment_screen.dart';
import 'history_screen.dart';
import 'edit_profile_screen.dart';
import 'topup_screen.dart';
import 'wallet_history_screen.dart';
import 'login_screen.dart';
import 'sign_in_methods_screen.dart';
import 'einvoice_profile_screen.dart';
import 'invite_friends_screen.dart';
import 'my_vehicles_screen.dart';
import 'subscriptions_screen.dart';
import 'business_accounts_screen.dart';
import 'faq_screen.dart';
import 'contact_us_screen.dart';
import 'chat_support_screen.dart';
import 'app_walkthrough_screen.dart';

// ─────────────────────────────────────────────
// Animated login prompt with EV illustration image
// ─────────────────────────────────────────────

class _AnimatedLoginPrompt extends StatefulWidget {
  const _AnimatedLoginPrompt();
  @override
  State<_AnimatedLoginPrompt> createState() => _AnimatedLoginPromptState();
}

class _AnimatedLoginPromptState extends State<_AnimatedLoginPrompt>
    with TickerProviderStateMixin {
  late AnimationController _sceneCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _floatCtrl;

  @override
  void initState() {
    super.initState();
    _sceneCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))
      ..forward();
    _pulseCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _floatCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 3))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _sceneCtrl.dispose();
    _pulseCtrl.dispose();
    _floatCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final screenW = MediaQuery.of(context).size.width;
    final screenH = MediaQuery.of(context).size.height;
    final bottomPad = MediaQuery.of(context).padding.bottom;
    final topPad = MediaQuery.of(context).padding.top;
    // Full-width image, fills top half of screen
    final illustrationH = (screenH * 0.45).clamp(260.0, 460.0);

    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  children: [
                    // ── Full-width illustration ──
                    AnimatedBuilder(
                      animation: Listenable.merge([_sceneCtrl, _floatCtrl]),
                      builder: (_, __) {
                        final fadeIn = Tween<double>(begin: 0, end: 1)
                            .animate(CurvedAnimation(parent: _sceneCtrl, curve: Curves.easeOut));

                        return Opacity(
                          opacity: fadeIn.value,
                          child: Stack(
                            children: [
                              // EV city night image — FULL, edge-to-edge, fills entire area
                              SizedBox(
                                height: illustrationH,
                                width: screenW,
                                child: Image.asset(
                                  'assets/ev_city_night.jpg',
                                  fit: BoxFit.cover,
                                  alignment: const Alignment(0.0, 0.6), // bias bottom to keep car+road visible, crop sky
                                ),
                              ),
                              // Gradient overlay at bottom for smooth blend
                              Positioned(
                                bottom: 0,
                                left: 0,
                                right: 0,
                                child: Container(
                                  height: illustrationH * 0.35,
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      begin: Alignment.bottomCenter,
                                      end: Alignment.topCenter,
                                      colors: [
                                        AppColors.background,
                                        AppColors.background.withOpacity(0.7),
                                        Colors.transparent,
                                      ],
                                      stops: const [0.0, 0.45, 1.0],
                                    ),
                                  ),
                                ),
                              ),
                              // Charging bolt badge — positioned in top safe area
                              AnimatedBuilder(
                                animation: _pulseCtrl,
                                builder: (_, __) {
                                  final s = 1.0 + _pulseCtrl.value * 0.06;
                                  return Positioned(
                                    top: topPad + 8,
                                    left: 0,
                                    right: 0,
                                    child: Center(
                                      child: Transform.scale(
                                        scale: s,
                                        child: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFF00E5FF).withOpacity(0.15),
                                            borderRadius: BorderRadius.circular(20),
                                            border: Border.all(
                                              color: const Color(0xFF00E5FF).withOpacity(0.35),
                                            ),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Icon(Icons.bolt, color: const Color(0xFF00E5FF), size: 16),
                                              const SizedBox(width: 4),
                                              Text(
                                                'EV Charging',
                                                style: TextStyle(
                                                  color: const Color(0xFF00E5FF),
                                                  fontSize: 11,
                                                  fontWeight: FontWeight.w600,
                                                  letterSpacing: 0.5,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                },
                              ),
                            ],
                          ),
                        );
                      },
                    ),

                    // ── Text & buttons ──
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: Column(
                        children: [
                          // Title with gradient
                          ShaderMask(
                            shaderCallback: (bounds) => const LinearGradient(
                              colors: [AppColors.primaryGreen, Color(0xFF00D977), Color(0xFF88FFD0)],
                            ).createShader(bounds),
                            child: const Text(
                              'Welcome to PlagSini',
                              style: TextStyle(
                                fontSize: 26,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            'Your smart companion for EV charging.\nManage your wallet, track sessions &\nearn rewards — all in one place.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: AppColors.textSecondary.withOpacity(0.8),
                              fontSize: 13,
                              height: 1.5,
                            ),
                          ),

                          const SizedBox(height: 10),

                          // Feature pills row
                          Wrap(
                            alignment: WrapAlignment.center,
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              _FeaturePill(icon: Icons.bolt, label: 'Fast Charging'),
                              _FeaturePill(icon: Icons.account_balance_wallet_outlined, label: 'E-Wallet'),
                              _FeaturePill(icon: Icons.card_giftcard, label: 'Rewards'),
                              _FeaturePill(icon: Icons.qr_code_scanner, label: 'Scan & Go'),
                            ],
                          ),

                          const SizedBox(height: 20),

                          // Login button with glow
                          AnimatedBuilder(
                            animation: _pulseCtrl,
                            builder: (_, __) {
                              final glow = _pulseCtrl.value;
                              return Container(
                                width: double.infinity,
                                constraints: const BoxConstraints(maxWidth: 480),
                                height: 54,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(16),
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppColors.primaryGreen.withOpacity(0.2 + glow * 0.15),
                                      blurRadius: 16 + glow * 8,
                                      spreadRadius: 0,
                                    ),
                                  ],
                                ),
                                child: ElevatedButton(
                                  onPressed: () {
                                    Navigator.push(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
                                  },
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.primaryGreen,
                                    foregroundColor: AppColors.background,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                                    elevation: 0,
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: const [
                                      Icon(Icons.login_rounded, size: 20),
                                      SizedBox(width: 10),
                                      Text(
                                        'LOGIN / REGISTER',
                                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, letterSpacing: 1),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),

                          const SizedBox(height: 10),

                          // Guest button
                          TextButton(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Some features require login'),
                                  backgroundColor: Colors.orange,
                                ),
                              );
                            },
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.explore_outlined, color: AppColors.primaryGreen.withOpacity(0.7), size: 16),
                                const SizedBox(width: 6),
                                Text(
                                  'Continue as Guest',
                                  style: TextStyle(
                                    color: AppColors.primaryGreen.withOpacity(0.7),
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                SizedBox(height: bottomPad + 16),
              ],
            ),
          ),
        );
      },
    );
  }
}

// Small feature pill widget
class _FeaturePill extends StatelessWidget {
  final IconData icon;
  final String label;
  const _FeaturePill({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: AppColors.primaryGreen, size: 14),
          const SizedBox(width: 5),
          Text(label, style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  static String _formatAccountId(dynamic id) {
    if (id == null) return '00000000';
    final idStr = id.toString();
    if (idStr.length >= 8) {
      return idStr.substring(0, 8).toUpperCase();
    }
    return idStr.padLeft(8, '0').toUpperCase();
  }

  void _showInfoDialog(BuildContext context, String title, String content) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: AppColors.borderLight),
        ),
        title: Text(title, style: TextStyle(color: AppColors.primaryGreen)),
        content: Text(content, style: TextStyle(color: AppColors.textLight)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Close', style: TextStyle(color: AppColors.primaryGreen)),
          ),
        ],
      ),
    );
  }

  void _showDeleteAccountDialog(BuildContext context, AuthProvider authProvider) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: Colors.red.withOpacity(0.3)),
        ),
        title: const Text('Delete Account?', style: TextStyle(color: Colors.red)),
        content: Text(
          'This action cannot be undone. All your data, including wallet balance and charging history, will be permanently deleted.',
          style: TextStyle(color: AppColors.textLight),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel', style: TextStyle(color: AppColors.textLight)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              authProvider.logout();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Account deletion request submitted'),
                  backgroundColor: Colors.red,
                ),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text('Account', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, shadows: [Shadow(blurRadius: 6, color: Colors.black54)])),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.25),
                border: Border.all(color: Colors.white24),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  Icon(Icons.flag, color: AppColors.primaryGreen, size: 16),
                  const SizedBox(width: 4),
                  Text('MY', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500)),
                ],
              ),
            ),
          ),
        ],
      ),
      body: Consumer<AuthProvider>(
        builder: (context, authProvider, _) {
          final user = authProvider.currentUser;

          if (user == null && !authProvider.isLoading) {
            return const _AnimatedLoginPrompt();
          }

          if (authProvider.isLoading) {
            return const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen));
          }

          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // User Info Header Card
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [AppColors.primaryGreen, AppColors.darkGreen],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15),
                    ],
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              user?.name.isNotEmpty == true ? user!.name : 'User',
                              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Account ID: ${ProfileScreen._formatAccountId(user?.id)}',
                              style: const TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.eco, color: Colors.white, size: 16),
                            const SizedBox(width: 4),
                            Text(
                              '${user?.walletPoints ?? 0} pts',
                              style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // Go Credits Card
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [const Color(0xFF1A2B40), const Color(0xFF0F1B2D)],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.primaryGreen.withOpacity(0.2)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.account_balance_wallet, color: AppColors.primaryGreen, size: 32),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text('PlagSini Credits', style: TextStyle(color: AppColors.textSecondary, fontSize: 14, fontWeight: FontWeight.w500)),
                                const SizedBox(width: 4),
                                Icon(Icons.flag, color: AppColors.primaryGreen, size: 12),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'RM${(user?.walletBalance ?? 0).toStringAsFixed(2)}',
                              style: TextStyle(color: AppColors.primaryGreen, fontSize: 24, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(colors: AppColors.primaryGradient),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TopUpScreen())),
                            borderRadius: BorderRadius.circular(8),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                              child: Row(
                                children: const [
                                  Icon(Icons.add, color: Colors.white, size: 20),
                                  SizedBox(width: 4),
                                  Text('TOP UP', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                _SectionHeader('My Account'),
                const SizedBox(height: 8),
                _MenuItem(icon: Icons.person_outline, title: 'Edit Profile', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const EditProfileScreen()))),
                _MenuItem(icon: Icons.lock_outline, title: 'Sign In Methods', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SignInMethodsScreen()))),
                _MenuItem(icon: Icons.receipt_long_outlined, title: 'Malaysia e-Invoice Profile', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const EInvoiceProfileScreen()))),
                _MenuItem(icon: Icons.person_add_outlined, title: 'Invite Your Friends', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const InviteFriendsScreen()))),

                const SizedBox(height: 24),
                _SectionHeader('Charging Management'),
                const SizedBox(height: 8),
                _MenuItem(icon: Icons.directions_car_outlined, title: 'My Vehicles', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const MyVehiclesScreen()))),
                _MenuItem(icon: Icons.subscriptions_outlined, title: 'My Subscriptions', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SubscriptionsScreen()))),
                _MenuItem(icon: Icons.history, title: 'Charging History', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const HistoryScreen()))),
                _MenuItem(icon: Icons.business_outlined, title: 'Business Accounts', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BusinessAccountsScreen()))),

                const SizedBox(height: 24),
                _SectionHeader('Payments'),
                const SizedBox(height: 8),
                _MenuItem(icon: Icons.payment_outlined, title: 'Payment Methods', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const PaymentScreen()))),
                _MenuItem(icon: Icons.history_outlined, title: 'PlagSini Credits History', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const WalletHistoryScreen()))),

                const SizedBox(height: 24),
                _SectionHeader('Others'),
                const SizedBox(height: 8),
                _MenuItem(
                  icon: Icons.help_outline,
                  title: 'App Walkthrough',
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AppWalkthroughScreen())),
                ),
                _MenuItem(icon: Icons.help_outline, title: 'F.A.Q.', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const FAQScreen()))),
                _MenuItem(
                  icon: Icons.smart_toy_outlined,
                  title: 'AI Chat Support',
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatSupportScreen())),
                ),
                _MenuItem(icon: Icons.contact_support_outlined, title: 'Contact Us', onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ContactUsScreen()))),
                _MenuItem(
                  icon: Icons.description_outlined,
                  title: 'Terms of Use',
                  onTap: () => _showInfoDialog(context, 'Terms of Use', 'By using PlagSini, you agree to:\n\n• Use the service responsibly\n• Pay for all charging sessions\n• Not damage charging equipment\n• Report any issues promptly\n\nFull terms available at www.plagsini.com.my/terms'),
                ),
                _MenuItem(
                  icon: Icons.privacy_tip_outlined,
                  title: 'Privacy Policy',
                  onTap: () => _showInfoDialog(context, 'Privacy Policy', 'We collect and use your data to:\n\n• Process charging transactions\n• Improve our services\n• Send important notifications\n\nWe never sell your personal data.\n\nFull policy at www.plagsini.com.my/privacy'),
                ),
                _MenuItem(icon: Icons.delete_outline, title: 'Delete Account', textColor: Colors.red, onTap: () => _showDeleteAccountDialog(context, authProvider)),

                const SizedBox(height: 24),

                // Logout Button
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () => authProvider.logout(),
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          border: Border.all(color: AppColors.borderLight),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.logout, color: AppColors.textPrimary, size: 20),
                            const SizedBox(width: 12),
                            Text('LOG OUT', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w500)),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 16),
                Center(
                  child: Text('ver 2.2.0 #1543 [Production]', style: TextStyle(color: AppColors.textLight, fontSize: 11)),
                ),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Text(
        title,
        style: TextStyle(
          color: AppColors.primaryGreen.withOpacity(0.7),
          fontSize: 12,
          fontWeight: FontWeight.w600,
          letterSpacing: 1,
        ),
      ),
    );
  }
}

class _MenuItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final Color? textColor;

  const _MenuItem({
    required this.icon,
    required this.title,
    required this.onTap,
    this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderLight, width: 1),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            child: Row(
              children: [
                Icon(icon, color: textColor ?? AppColors.primaryGreen, size: 20),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(color: textColor ?? AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w400),
                  ),
                ),
                Icon(Icons.chevron_right, color: textColor ?? AppColors.primaryGreen.withOpacity(0.5), size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
