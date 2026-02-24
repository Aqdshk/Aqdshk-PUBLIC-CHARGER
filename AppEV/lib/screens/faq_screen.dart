import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class FAQScreen extends StatelessWidget {
  const FAQScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'F.A.Q.',
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
            // Search Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Row(
                children: [
                  Icon(Icons.search, color: AppColors.textLight),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      style: TextStyle(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        hintText: 'Search FAQ...',
                        hintStyle: TextStyle(color: AppColors.textLight),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Categories
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _CategoryChip(label: 'All', isSelected: true),
                _CategoryChip(label: 'Charging'),
                _CategoryChip(label: 'Payment'),
                _CategoryChip(label: 'Account'),
                _CategoryChip(label: 'App'),
              ],
            ),
            
            const SizedBox(height: 24),
            
            // FAQ Items
            _FAQSection(
              title: 'Getting Started',
              items: [
                _FAQItemData(
                  question: 'How do I start charging?',
                  answer: '1. Open the PlagSini app\n'
                      '2. Navigate to the Map tab\n'
                      '3. Find a nearby charger\n'
                      '4. Tap on the charger and press "Start Charging"\n'
                      '5. Connect your vehicle and wait for confirmation',
                ),
                _FAQItemData(
                  question: 'What payment methods are accepted?',
                  answer: 'We accept:\n'
                      '• Credit/Debit cards (Visa, Mastercard)\n'
                      '• PlagSini Wallet (prepaid credits)\n'
                      '• Online banking (FPX)\n'
                      '• E-wallets (Touch \'n Go, GrabPay)',
                ),
                _FAQItemData(
                  question: 'How do I add my vehicle?',
                  answer: 'Go to Me > My Vehicles > Add Vehicle. Enter your vehicle details including make, model, and connector type for a personalized experience.',
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            _FAQSection(
              title: 'Charging',
              items: [
                _FAQItemData(
                  question: 'How long does it take to charge?',
                  answer: 'Charging time depends on:\n'
                      '• Your vehicle\'s battery capacity\n'
                      '• Current charge level\n'
                      '• Charger power output (AC/DC)\n\n'
                      'AC charging: 4-8 hours for full charge\n'
                      'DC fast charging: 30-60 minutes to 80%',
                ),
                _FAQItemData(
                  question: 'Why did charging stop automatically?',
                  answer: 'Charging may stop due to:\n'
                      '• Battery reached full capacity\n'
                      '• Preset energy limit reached\n'
                      '• Connection issue detected\n'
                      '• Charger maintenance required',
                ),
                _FAQItemData(
                  question: 'Can I reserve a charger?',
                  answer: 'Yes! Premium subscribers can reserve chargers up to 30 minutes in advance. Go to the charger details and tap "Reserve".',
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            _FAQSection(
              title: 'Billing & Payment',
              items: [
                _FAQItemData(
                  question: 'How am I charged?',
                  answer: 'You are charged per kWh of energy consumed. Rates vary by charger location and type. The estimated cost is shown before you start charging.',
                ),
                _FAQItemData(
                  question: 'Where can I see my receipts?',
                  answer: 'Go to Me > Charging History to view all your past sessions with detailed receipts. You can also download e-invoices for tax purposes.',
                ),
                _FAQItemData(
                  question: 'How do I top up my wallet?',
                  answer: 'Go to Me > tap on "TOP UP" button. Select your preferred amount and payment method to add credits to your PlagSini wallet.',
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            _FAQSection(
              title: 'Troubleshooting',
              items: [
                _FAQItemData(
                  question: 'Charger not starting?',
                  answer: 'Try these steps:\n'
                      '1. Ensure your vehicle is properly connected\n'
                      '2. Check that your vehicle is ready to charge\n'
                      '3. Try unplugging and reconnecting\n'
                      '4. Contact support if the issue persists',
                ),
                _FAQItemData(
                  question: 'App showing wrong charger status?',
                  answer: 'Pull down to refresh the charger list. If the issue persists, try restarting the app or contact support.',
                ),
              ],
            ),
            
            const SizedBox(height: 32),
            
            // Still need help?
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
              ),
              child: Column(
                children: [
                  Icon(Icons.headset_mic_outlined, color: AppColors.primaryGreen, size: 40),
                  const SizedBox(height: 12),
                  Text(
                    'Still need help?',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Our support team is ready to assist you',
                    style: TextStyle(
                      color: AppColors.textLight,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                    },
                    icon: const Icon(Icons.chat_bubble_outline),
                    label: const Text('CONTACT SUPPORT'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primaryGreen,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
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

class _CategoryChip extends StatelessWidget {
  final String label;
  final bool isSelected;

  const _CategoryChip({
    required this.label,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: isSelected ? AppColors.primaryGreen : AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isSelected ? AppColors.primaryGreen : AppColors.borderLight,
        ),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: isSelected ? Colors.white : AppColors.textPrimary,
          fontSize: 14,
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }
}

class _FAQSection extends StatelessWidget {
  final String title;
  final List<_FAQItemData> items;

  const _FAQSection({
    required this.title,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              title,
              style: TextStyle(
                color: AppColors.primaryGreen,
                fontSize: 14,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
          ),
          Divider(color: AppColors.borderLight, height: 1),
          ...items.map((item) => _FAQItem(data: item)),
        ],
      ),
    );
  }
}

class _FAQItemData {
  final String question;
  final String answer;

  const _FAQItemData({
    required this.question,
    required this.answer,
  });
}

class _FAQItem extends StatefulWidget {
  final _FAQItemData data;

  const _FAQItem({required this.data});

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
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.data.question,
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 15,
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
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Text(
              widget.data.answer,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 14,
                height: 1.5,
              ),
            ),
          ),
        Divider(color: AppColors.borderLight, height: 1),
      ],
    );
  }
}
