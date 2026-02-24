import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class SubscriptionsScreen extends StatefulWidget {
  const SubscriptionsScreen({super.key});

  @override
  State<SubscriptionsScreen> createState() => _SubscriptionsScreenState();
}

class _SubscriptionsScreenState extends State<SubscriptionsScreen> {
  String? _currentPlan;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'My Subscriptions',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current Status
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: _currentPlan == null
                      ? [Colors.grey.shade700, Colors.grey.shade900]
                      : [AppColors.primaryGreen, AppColors.darkGreen],
                ),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        _currentPlan == null ? Icons.card_membership_outlined : Icons.workspace_premium,
                        color: Colors.white,
                        size: 32,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _currentPlan ?? 'No Active Plan',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              _currentPlan == null
                                  ? 'Subscribe to save more on charging'
                                  : 'Valid until Dec 31, 2026',
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  if (_currentPlan != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text(
                        '10% OFF on all charging sessions',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Text(
              'AVAILABLE PLANS',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            
            // Free Plan
            _PlanCard(
              planName: 'Free',
              price: 'RM0',
              period: 'forever',
              features: [
                'Pay-per-use charging',
                'Basic app access',
                'Standard customer support',
              ],
              isCurrentPlan: _currentPlan == null,
              isPopular: false,
              onSubscribe: () {},
            ),
            
            const SizedBox(height: 12),
            
            // Basic Plan
            _PlanCard(
              planName: 'Basic',
              price: 'RM29',
              period: 'month',
              features: [
                '5% discount on all charging',
                'Priority customer support',
                'Monthly charging report',
                'Free parking during charge',
              ],
              isCurrentPlan: _currentPlan == 'Basic',
              isPopular: false,
              onSubscribe: () => _subscribeToPlan('Basic'),
            ),
            
            const SizedBox(height: 12),
            
            // Premium Plan
            _PlanCard(
              planName: 'Premium',
              price: 'RM79',
              period: 'month',
              features: [
                '10% discount on all charging',
                '24/7 priority support',
                'Detailed analytics dashboard',
                'Free parking during charge',
                'Charger reservation priority',
                'Exclusive member events',
              ],
              isCurrentPlan: _currentPlan == 'Premium',
              isPopular: true,
              onSubscribe: () => _subscribeToPlan('Premium'),
            ),
            
            const SizedBox(height: 12),
            
            // Business Plan
            _PlanCard(
              planName: 'Business',
              price: 'RM199',
              period: 'month',
              features: [
                '15% discount on all charging',
                'Multi-vehicle support',
                'Fleet management dashboard',
                'Consolidated billing',
                'Dedicated account manager',
                'Custom reporting',
              ],
              isCurrentPlan: _currentPlan == 'Business',
              isPopular: false,
              onSubscribe: () => _subscribeToPlan('Business'),
            ),
            
            const SizedBox(height: 24),
            
            // FAQ Section
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.cardBackground,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Frequently Asked Questions',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  _FAQItem(
                    question: 'Can I cancel anytime?',
                    answer: 'Yes, you can cancel your subscription at any time. Your benefits will remain active until the end of the billing period.',
                  ),
                  _FAQItem(
                    question: 'How are discounts applied?',
                    answer: 'Discounts are automatically applied at checkout when you start a charging session.',
                  ),
                  _FAQItem(
                    question: 'Can I upgrade my plan?',
                    answer: 'Yes, you can upgrade anytime. The difference will be prorated for the remaining period.',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _subscribeToPlan(String plan) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        title: Text('Subscribe to $plan?', style: TextStyle(color: AppColors.textPrimary)),
        content: Text(
          'You will be charged monthly. You can cancel anytime.',
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
              setState(() => _currentPlan = plan);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Successfully subscribed to $plan!'),
                  backgroundColor: AppColors.primaryGreen,
                ),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryGreen),
            child: const Text('Subscribe'),
          ),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  final String planName;
  final String price;
  final String period;
  final List<String> features;
  final bool isCurrentPlan;
  final bool isPopular;
  final VoidCallback onSubscribe;

  const _PlanCard({
    required this.planName,
    required this.price,
    required this.period,
    required this.features,
    required this.isCurrentPlan,
    required this.isPopular,
    required this.onSubscribe,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppColors.cardBackground,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isPopular ? AppColors.primaryGreen : AppColors.borderLight,
              width: isPopular ? 2 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    planName,
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (isCurrentPlan)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.primaryGreen.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        'CURRENT',
                        style: TextStyle(
                          color: AppColors.primaryGreen,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    price,
                    style: TextStyle(
                      color: AppColors.primaryGreen,
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      '/$period',
                      style: TextStyle(
                        color: AppColors.textLight,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ...features.map((feature) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Icon(Icons.check_circle, color: AppColors.primaryGreen, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        feature,
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
              const SizedBox(height: 16),
              if (!isCurrentPlan && price != 'RM0')
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: onSubscribe,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isPopular ? AppColors.primaryGreen : AppColors.surface,
                      foregroundColor: isPopular ? Colors.white : AppColors.primaryGreen,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      'Subscribe',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
            ],
          ),
        ),
        if (isPopular)
          Positioned(
            top: -1,
            right: 20,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen,
                borderRadius: const BorderRadius.vertical(bottom: Radius.circular(8)),
              ),
              child: const Text(
                'POPULAR',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _FAQItem extends StatefulWidget {
  final String question;
  final String answer;

  const _FAQItem({required this.question, required this.answer});

  @override
  State<_FAQItem> createState() => _FAQItemState();
}

class _FAQItemState extends State<_FAQItem> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          onTap: () => setState(() => _isExpanded = !_isExpanded),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.question,
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                Icon(
                  _isExpanded ? Icons.expand_less : Icons.expand_more,
                  color: AppColors.primaryGreen,
                ),
              ],
            ),
          ),
        ),
        if (_isExpanded)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              widget.answer,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 13,
              ),
            ),
          ),
        Divider(color: AppColors.borderLight),
      ],
    );
  }
}
