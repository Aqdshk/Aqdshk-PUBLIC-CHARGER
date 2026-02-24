import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class AppWalkthroughScreen extends StatefulWidget {
  const AppWalkthroughScreen({super.key});

  @override
  State<AppWalkthroughScreen> createState() => _AppWalkthroughScreenState();
}

class _AppWalkthroughScreenState extends State<AppWalkthroughScreen> {
  final PageController _pageCtrl = PageController();
  int _currentPage = 0;

  final List<_WalkthroughStep> _steps = [
    _WalkthroughStep(
      icon: Icons.ev_station_rounded,
      title: 'Find Chargers',
      description: 'Discover nearby EV charging stations on the interactive map. '
          'Filter by charger type, availability, and power output to find the perfect spot.',
      color: AppColors.primaryGreen,
    ),
    _WalkthroughStep(
      icon: Icons.qr_code_scanner_rounded,
      title: 'Scan & Charge',
      description: 'Simply scan the QR code on the charger to start a session. '
          'Monitor your charging progress in real-time with live updates.',
      color: const Color(0xFF00BCD4),
    ),
    _WalkthroughStep(
      icon: Icons.bolt_rounded,
      title: 'Live Monitoring',
      description: 'Track your charging session live — see power output, energy consumed, '
          'estimated time remaining, and cost all in one dashboard.',
      color: const Color(0xFFFF9800),
    ),
    _WalkthroughStep(
      icon: Icons.receipt_long_rounded,
      title: 'Session History',
      description: 'View your complete charging history with detailed breakdowns '
          'of energy used, session duration, and cost per charge.',
      color: const Color(0xFF9C27B0),
    ),
    _WalkthroughStep(
      icon: Icons.card_giftcard_rounded,
      title: 'Rewards & Referrals',
      description: 'Earn rewards for charging and referring friends. '
          'Collect points and redeem them for free charging credits!',
      color: const Color(0xFFE91E63),
    ),
    _WalkthroughStep(
      icon: Icons.support_agent_rounded,
      title: 'AI Support',
      description: 'Need help? Our AI chatbot is available 24/7 to guide you. '
          'You can also submit a support ticket for personalized assistance.',
      color: const Color(0xFF2196F3),
    ),
  ];

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'App Walkthrough',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              _currentPage == _steps.length - 1 ? 'Done' : 'Skip',
              style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Page view
          Expanded(
            child: PageView.builder(
              controller: _pageCtrl,
              itemCount: _steps.length,
              onPageChanged: (i) => setState(() => _currentPage = i),
              itemBuilder: (context, i) {
                final step = _steps[i];
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 32),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      // Icon circle
                      Container(
                        width: 140,
                        height: 140,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            colors: [
                              step.color.withOpacity(0.2),
                              step.color.withOpacity(0.05),
                            ],
                          ),
                          border: Border.all(color: step.color.withOpacity(0.3), width: 2),
                        ),
                        child: Icon(step.icon, size: 64, color: step.color),
                      ),
                      const SizedBox(height: 40),
                      // Step counter
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        decoration: BoxDecoration(
                          color: step.color.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: step.color.withOpacity(0.3)),
                        ),
                        child: Text(
                          'Step ${i + 1} of ${_steps.length}',
                          style: TextStyle(color: step.color, fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                      const SizedBox(height: 20),
                      // Title
                      Text(
                        step.title,
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 26,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 16),
                      // Description
                      Text(
                        step.description,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppColors.textLight,
                          fontSize: 15,
                          height: 1.6,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),

          // Bottom section — dots + next button
          Padding(
            padding: const EdgeInsets.fromLTRB(32, 0, 32, 40),
            child: Column(
              children: [
                // Page indicators
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(_steps.length, (i) {
                    final isActive = i == _currentPage;
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: isActive ? 28 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: isActive ? _steps[_currentPage].color : AppColors.textLight.withOpacity(0.3),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 28),
                // Next / Get Started button
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: () {
                      if (_currentPage == _steps.length - 1) {
                        Navigator.pop(context);
                      } else {
                        _pageCtrl.nextPage(
                          duration: const Duration(milliseconds: 400),
                          curve: Curves.easeInOut,
                        );
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _steps[_currentPage].color,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      elevation: 4,
                      shadowColor: _steps[_currentPage].color.withOpacity(0.4),
                    ),
                    child: Text(
                      _currentPage == _steps.length - 1 ? 'Get Started' : 'Next',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _WalkthroughStep {
  final IconData icon;
  final String title;
  final String description;
  final Color color;

  const _WalkthroughStep({
    required this.icon,
    required this.title,
    required this.description,
    required this.color,
  });
}
