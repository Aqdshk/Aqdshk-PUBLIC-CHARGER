import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/payment_provider.dart';
import '../constants/app_colors.dart';

class PaymentScreen extends StatefulWidget {
  const PaymentScreen({super.key});

  @override
  State<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends State<PaymentScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Payment'),
        backgroundColor: Colors.transparent,
      ),
      body: Consumer<PaymentProvider>(
        builder: (context, paymentProvider, _) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'PAYMENT METHODS',
                  style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1),
                ),
                const SizedBox(height: 16),
                if (paymentProvider.paymentMethods.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Center(child: Text('No payment methods added', style: TextStyle(color: AppColors.textLight))),
                  )
                else
                  ...paymentProvider.paymentMethods.map((method) => Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          method['type'] == 'credit_card' ? Icons.credit_card : Icons.account_balance_wallet,
                          color: AppColors.primaryGreen,
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(method['name'] ?? 'Unknown', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                              Text(method['details'] ?? '', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                            ],
                          ),
                        ),
                        if (method['is_default'])
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppColors.primaryGreen.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Text('Default', style: TextStyle(color: AppColors.primaryGreen, fontSize: 11, fontWeight: FontWeight.w600)),
                          ),
                      ],
                    ),
                  )),
                const SizedBox(height: 24),

                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: () => _showAddPaymentDialog(context, paymentProvider),
                    icon: const Icon(Icons.add),
                    label: const Text('Add Payment Method'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primaryGreen,
                      foregroundColor: AppColors.background,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                Text(
                  'RECENT TRANSACTIONS',
                  style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1),
                ),
                const SizedBox(height: 16),
                if (paymentProvider.transactions.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Center(child: Text('No transactions yet', style: TextStyle(color: AppColors.textLight))),
                  )
                else
                  ...paymentProvider.transactions.map((transaction) => Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: transaction['status'] == 'completed' ? AppColors.primaryGreen : Colors.orange,
                          child: const Icon(Icons.receipt, color: Colors.white),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('RM ${transaction['amount']?.toStringAsFixed(2) ?? '0.00'}', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                              Text(transaction['date'] ?? '', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                            ],
                          ),
                        ),
                        Text(
                          transaction['status'] ?? 'pending',
                          style: TextStyle(
                            color: transaction['status'] == 'completed' ? AppColors.primaryGreen : Colors.orange,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  )),
              ],
            ),
          );
        },
      ),
    );
  }

  void _showAddPaymentDialog(BuildContext context, PaymentProvider paymentProvider) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: AppColors.borderLight)),
        title: Text('Add Payment Method', style: TextStyle(color: AppColors.primaryGreen)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _PaymentOption(
              icon: Icons.credit_card,
              title: 'Credit/Debit Card',
              onTap: () {
                Navigator.pop(context);
                _showAddCardForm(context);
              },
            ),
            _PaymentOption(
              icon: Icons.account_balance_wallet,
              title: 'E-Wallet (FPX)',
              onTap: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('FPX e-Wallet will be available when the payment gateway is configured.'),
                    backgroundColor: Colors.orange,
                  ),
                );
              },
            ),
            _PaymentOption(
              icon: Icons.qr_code,
              title: 'DuitNow QR',
              onTap: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('DuitNow QR will be available when the payment gateway is configured.'),
                    backgroundColor: Colors.orange,
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showAddCardForm(BuildContext context) {
    final cardNumberCtrl = TextEditingController();
    final expiryCtrl = TextEditingController();
    final nameCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: AppColors.borderLight)),
        title: Text('Add Card', style: TextStyle(color: AppColors.primaryGreen)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameCtrl,
              style: TextStyle(color: AppColors.textPrimary),
              decoration: InputDecoration(
                labelText: 'Cardholder Name',
                labelStyle: TextStyle(color: AppColors.textLight),
                prefixIcon: Icon(Icons.person_outline, color: AppColors.primaryGreen),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.borderLight)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.primaryGreen)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: cardNumberCtrl,
              keyboardType: TextInputType.number,
              style: TextStyle(color: AppColors.textPrimary),
              decoration: InputDecoration(
                labelText: 'Card Number',
                labelStyle: TextStyle(color: AppColors.textLight),
                hintText: '•••• •••• •••• ••••',
                prefixIcon: Icon(Icons.credit_card, color: AppColors.primaryGreen),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.borderLight)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.primaryGreen)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: expiryCtrl,
              style: TextStyle(color: AppColors.textPrimary),
              decoration: InputDecoration(
                labelText: 'Expiry (MM/YY)',
                labelStyle: TextStyle(color: AppColors.textLight),
                hintText: '12/28',
                prefixIcon: Icon(Icons.date_range, color: AppColors.primaryGreen),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.borderLight)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppColors.primaryGreen)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: TextStyle(color: AppColors.textLight)),
          ),
          ElevatedButton(
            onPressed: () {
              if (cardNumberCtrl.text.isEmpty || expiryCtrl.text.isEmpty || nameCtrl.text.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Please fill all fields'), backgroundColor: Colors.red),
                );
                return;
              }
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: const Text('Card will be saved when the payment gateway is configured.'),
                  backgroundColor: Colors.orange,
                ),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primaryGreen,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: const Text('Add Card'),
          ),
        ],
      ),
    );
  }
}

class _PaymentOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;

  const _PaymentOption({required this.icon, required this.title, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        leading: Icon(icon, color: AppColors.primaryGreen),
        title: Text(title, style: TextStyle(color: AppColors.textPrimary)),
        onTap: onTap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}
