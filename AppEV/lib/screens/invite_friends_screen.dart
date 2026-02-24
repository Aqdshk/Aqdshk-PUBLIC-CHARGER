import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../constants/app_colors.dart';

class InviteFriendsScreen extends StatelessWidget {
  const InviteFriendsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final referralCode = 'PLAGSINI2024';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Invite Friends', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [AppColors.primaryGreen, AppColors.darkGreen]),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [BoxShadow(color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15)],
              ),
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), shape: BoxShape.circle),
                    child: const Icon(Icons.card_giftcard, size: 48, color: Colors.white),
                  ),
                  const SizedBox(height: 16),
                  const Text('Invite & Earn!', style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  const Text('Get RM5 credits for every friend who joins and makes their first charge!', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 14)),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
              child: Column(
                children: [
                  Text('Your Referral Code', style: TextStyle(color: AppColors.textLight, fontSize: 14)),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.primaryGreen, width: 2),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(referralCode, style: TextStyle(color: AppColors.primaryGreen, fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: 4)),
                        const SizedBox(width: 16),
                        IconButton(
                          onPressed: () {
                            Clipboard.setData(ClipboardData(text: referralCode));
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('Referral code copied!'), backgroundColor: AppColors.primaryGreen));
                          },
                          icon: Icon(Icons.copy, color: AppColors.primaryGreen),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {
                            final shareText = '⚡ Join PlagSini EV Charging!\n\n'
                                'Use my referral code: $referralCode\n'
                                'Get RM5 credits on your first charge!\n\n'
                                'Download the PlagSini app now!';
                            Clipboard.setData(ClipboardData(text: shareText));
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: const Text('Referral message copied! Paste it to share with friends.'),
                                backgroundColor: AppColors.primaryGreen,
                              ),
                            );
                          },
                          icon: const Icon(Icons.share),
                          label: const Text('SHARE'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primaryGreen,
                            foregroundColor: AppColors.background,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('How It Works', style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  _HowItWorksStep(number: '1', title: 'Share Your Code', description: 'Send your referral code to friends'),
                  const SizedBox(height: 16),
                  _HowItWorksStep(number: '2', title: 'Friend Signs Up', description: 'They register using your code'),
                  const SizedBox(height: 16),
                  _HowItWorksStep(number: '3', title: 'First Charge', description: 'Your friend completes a charging session'),
                  const SizedBox(height: 16),
                  _HowItWorksStep(number: '4', title: 'Earn Rewards', description: 'Both of you get RM5 credits!'),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Your Referral Stats', style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(child: _StatCard(icon: Icons.people_outline, value: '0', label: 'Friends Invited')),
                      const SizedBox(width: 12),
                      Expanded(child: _StatCard(icon: Icons.check_circle_outline, value: '0', label: 'Completed')),
                      const SizedBox(width: 12),
                      Expanded(child: _StatCard(icon: Icons.account_balance_wallet_outlined, value: 'RM0', label: 'Earned')),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            Text(
              'Terms & Conditions apply. Rewards are credited after your friend\'s first successful charging session.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textLight, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class _HowItWorksStep extends StatelessWidget {
  final String number;
  final String title;
  final String description;

  const _HowItWorksStep({required this.number, required this.title, required this.description});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 32, height: 32,
          decoration: BoxDecoration(color: AppColors.primaryGreen, shape: BoxShape.circle),
          child: Center(child: Text(number, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600)),
              Text(description, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;

  const _StatCard({required this.icon, required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.borderLight)),
      child: Column(
        children: [
          Icon(icon, color: AppColors.primaryGreen, size: 24),
          const SizedBox(height: 8),
          Text(value, style: TextStyle(color: AppColors.primaryGreen, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(label, textAlign: TextAlign.center, style: TextStyle(color: AppColors.textLight, fontSize: 10)),
        ],
      ),
    );
  }
}
