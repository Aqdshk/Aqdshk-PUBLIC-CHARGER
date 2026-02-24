import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../constants/app_colors.dart';

class PromotionsScreen extends StatelessWidget {
  const PromotionsScreen({super.key});

  List<Map<String, dynamic>> get _promotions => [
    {'title': '15% OFF All Charging', 'description': 'Enjoy 15% discount on all charging sessions this week!', 'code': 'CHARGE15', 'validUntil': 'Feb 28, 2026', 'minSpend': 'RM 20', 'type': 'discount', 'color': AppColors.primaryGreen},
    {'title': 'Free First Charge', 'description': 'New users get their first charging session FREE (up to RM 10)', 'code': 'NEWUSER', 'validUntil': 'Mar 31, 2026', 'minSpend': 'No minimum', 'type': 'free', 'color': Colors.blue},
    {'title': 'Double Points Weekend', 'description': 'Earn 2x reward points on all charges this weekend!', 'code': null, 'validUntil': 'This Weekend Only', 'minSpend': null, 'type': 'points', 'color': Colors.purple},
    {'title': 'RM 5 OFF DC Fast Charging', 'description': 'Get RM 5 off when you use DC fast chargers', 'code': 'DCFAST5', 'validUntil': 'Feb 15, 2026', 'minSpend': 'RM 15', 'type': 'discount', 'color': Colors.orange},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Promotions', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
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
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(20)),
                    child: const Text('LIMITED TIME', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 16),
                  const Text('15% OFF', style: TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.bold)),
                  const Text('All Charging Sessions', style: TextStyle(color: Colors.white, fontSize: 18)),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(color: Colors.white.withOpacity(0.15), borderRadius: BorderRadius.circular(12)),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Code: ', style: TextStyle(color: Colors.white70, fontSize: 14)),
                        const Text('CHARGE15', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 2)),
                        const SizedBox(width: 12),
                        GestureDetector(
                          onTap: () {
                            Clipboard.setData(const ClipboardData(text: 'CHARGE15'));
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('Promo code copied!'), backgroundColor: AppColors.primaryGreen));
                          },
                          child: const Icon(Icons.copy, color: Colors.white, size: 18),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Valid until Feb 28, 2026', style: TextStyle(color: Colors.white70, fontSize: 12)),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Have a promo code?', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          textCapitalization: TextCapitalization.characters,
                          style: TextStyle(color: AppColors.textPrimary, letterSpacing: 2),
                          decoration: InputDecoration(
                            hintText: 'Enter code',
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      ElevatedButton(
                        onPressed: () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('Promo code applied!'), backgroundColor: AppColors.primaryGreen)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primaryGreen,
                          foregroundColor: AppColors.background,
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('APPLY'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            Text('AVAILABLE PROMOTIONS', style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
            const SizedBox(height: 12),
            ...(_promotions.map((promo) => _PromoCard(promo: promo))),
            
            const SizedBox(height: 24),
            Text('MY ACTIVE PROMOTIONS', style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
              child: Column(
                children: [
                  Icon(Icons.local_offer_outlined, size: 48, color: AppColors.textLight),
                  const SizedBox(height: 16),
                  Text('No active promotions', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Text('Apply a promo code above to get started', style: TextStyle(color: AppColors.textLight, fontSize: 13)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PromoCard extends StatelessWidget {
  final Map<String, dynamic> promo;

  const _PromoCard({required this.promo});

  @override
  Widget build(BuildContext context) {
    final title = promo['title'] ?? '';
    final description = promo['description'] ?? '';
    final code = promo['code'];
    final validUntil = promo['validUntil'] ?? '';
    final minSpend = promo['minSpend'];
    final color = promo['color'] as Color? ?? AppColors.primaryGreen;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
                  child: Icon(Icons.local_offer, color: color, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text(description, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Divider(color: AppColors.borderLight, height: 1),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                if (code != null) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(8)),
                    child: Row(
                      children: [
                        Text(code, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1)),
                        const SizedBox(width: 8),
                        GestureDetector(
                          onTap: () {
                            Clipboard.setData(ClipboardData(text: code));
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('Code copied!'), backgroundColor: AppColors.primaryGreen));
                          },
                          child: Icon(Icons.copy, size: 14, color: color),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
                if (minSpend != null) ...[
                  Text('Min: $minSpend', style: TextStyle(color: AppColors.textLight, fontSize: 11)),
                  const SizedBox(width: 12),
                ],
                const Spacer(),
                Text(validUntil, style: TextStyle(color: AppColors.textLight, fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
