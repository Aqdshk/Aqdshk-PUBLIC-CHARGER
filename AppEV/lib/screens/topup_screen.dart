import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../constants/app_colors.dart';

class TopUpScreen extends StatefulWidget {
  const TopUpScreen({super.key});

  @override
  State<TopUpScreen> createState() => _TopUpScreenState();
}

class _TopUpScreenState extends State<TopUpScreen>
    with TickerProviderStateMixin {
  double? _selectedAmount;
  String _selectedPaymentMethod = 'fpx';
  bool _isLoading = false;
  Timer? _statusPollTimer;
  final TextEditingController _customAmountController = TextEditingController();
  late AnimationController _pulseController;

  final List<double> _quickAmounts = [10, 20, 50, 100, 200, 500];

  final List<Map<String, dynamic>> _paymentMethods = [
    {
      'id': 'fpx',
      'name': 'FPX Online Banking',
      'subtitle': 'All Malaysian banks',
      'icon': Icons.account_balance_outlined,
      'color': const Color(0xFF2196F3),
    },
    {
      'id': 'card',
      'name': 'Credit / Debit Card',
      'subtitle': 'Visa, Mastercard',
      'icon': Icons.credit_card_outlined,
      'color': const Color(0xFF9C27B0),
    },
    {
      'id': 'tng',
      'name': "Touch 'n Go eWallet",
      'subtitle': 'Pay via TNG app',
      'icon': Icons.wallet_outlined,
      'color': const Color(0xFF1565C0),
    },
    {
      'id': 'grabpay',
      'name': 'GrabPay',
      'subtitle': 'Pay via Grab app',
      'icon': Icons.local_taxi_outlined,
      'color': const Color(0xFF2E7D32),
    },
    {
      'id': 'duitnow',
      'name': 'DuitNow QR',
      'subtitle': 'Scan & pay',
      'icon': Icons.qr_code_2_outlined,
      'color': const Color(0xFFE65100),
    },
    {
      'id': 'manual',
      'name': 'Manual / Bank Transfer',
      'subtitle': 'Admin will verify',
      'icon': Icons.payments_outlined,
      'color': const Color(0xFF607D8B),
    },
  ];

  double get _amount {
    if (_selectedAmount != null) return _selectedAmount!;
    return double.tryParse(_customAmountController.text) ?? 0;
  }

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _customAmountController.dispose();
    _statusPollTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _processTopUp() async {
    if (_amount < 1) {
      _showSnackBar('Minimum top-up amount is RM 1.00', Colors.red);
      return;
    }
    if (_amount > 5000) {
      _showSnackBar('Maximum top-up amount is RM 5,000.00', Colors.red);
      return;
    }

    final user = context.read<AuthProvider>().currentUser;
    if (user == null) {
      _showSnackBar('Please login first', Colors.red);
      return;
    }

    setState(() => _isLoading = true);

    try {
      // Use the new payment gateway endpoint
      final result = await ApiService.createPaymentTopUp(
        user.id,
        amount: _amount,
        paymentMethod: _selectedPaymentMethod,
      );

      if (!mounted) return;
      setState(() => _isLoading = false);

      if (result['success'] == true) {
        final paymentUrl = result['payment_url'];
        final txnRef = result['transaction_ref'] as String?;
        final status = result['status'] as String?;

        if (paymentUrl != null && paymentUrl.toString().isNotEmpty) {
          // Gateway returned a payment URL — open in browser
          _showPaymentPendingDialog(txnRef ?? '', _amount);

          final uri = Uri.parse(paymentUrl.toString());
          if (await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
          }

          // Start polling for payment status
          _startStatusPolling(txnRef ?? '');
        } else if (status == 'pending_approval' ||
            _selectedPaymentMethod == 'manual') {
          // Manual payment — show confirmation
          _showManualPaymentDialog(txnRef ?? '', _amount);
        } else {
          // Direct success (unlikely but handle it)
          await context.read<AuthProvider>().refreshProfile();
          if (mounted) {
            _showSnackBar(
              'Successfully topped up RM${_amount.toStringAsFixed(2)}!',
              AppColors.primaryGreen,
            );
            Navigator.pop(context);
          }
        }
      } else {
        _showSnackBar(result['message'] ?? 'Top-up failed', Colors.red);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showSnackBar('Error: $e', Colors.red);
      }
    }
  }

  void _startStatusPolling(String txnRef) {
    _statusPollTimer?.cancel();
    int attempts = 0;
    _statusPollTimer = Timer.periodic(const Duration(seconds: 5), (timer) async {
      attempts++;
      if (attempts > 60) {
        // 5 minutes timeout
        timer.cancel();
        return;
      }

      try {
        final result = await ApiService.checkPaymentStatus(txnRef);
        if (!mounted) {
          timer.cancel();
          return;
        }

        final txn = result['transaction'];
        if (txn != null) {
          final status = txn['status'] as String?;
          if (status == 'success') {
            timer.cancel();
            await context.read<AuthProvider>().refreshProfile();
            if (mounted) {
              Navigator.of(context).popUntil((route) => route.isFirst || route.settings.name == '/');
              _showSuccessDialog(txn['amount']?.toDouble() ?? _amount);
            }
          } else if (status == 'failed') {
            timer.cancel();
            if (mounted) {
              Navigator.of(context).pop(); // Close pending dialog
              _showSnackBar('Payment failed. Please try again.', Colors.red);
            }
          }
        }
      } catch (_) {}
    });
  }

  void _showPaymentPendingDialog(String txnRef, double amount) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + (_pulseController.value * 0.1),
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppColors.primaryGreen.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.payment,
                      color: AppColors.primaryGreen,
                      size: 48,
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 20),
            Text(
              'Completing Payment',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'RM${amount.toStringAsFixed(2)}',
              style: TextStyle(
                color: AppColors.primaryGreen,
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Please complete payment in the opened browser.\nThis page will update automatically.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Ref: $txnRef',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 11,
                fontFamily: 'monospace',
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.primaryGreen),
              ),
            ),
            const SizedBox(height: 20),
            TextButton(
              onPressed: () {
                _statusPollTimer?.cancel();
                Navigator.pop(ctx);
              },
              child: Text(
                'Cancel',
                style: TextStyle(color: AppColors.textLight, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showManualPaymentDialog(String txnRef, double amount) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.hourglass_bottom,
                color: Colors.orange,
                size: 48,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Payment Pending',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'RM${amount.toStringAsFixed(2)}',
              style: TextStyle(
                color: Colors.orange,
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Your top-up request has been submitted.\nOur team will verify and approve it shortly.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 13,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Ref: $txnRef',
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  Navigator.pop(context);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('OK, Got it', style: TextStyle(color: Colors.white)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showSuccessDialog(double amount) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.check_circle,
                color: AppColors.primaryGreen,
                size: 56,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Top-Up Successful!',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'RM${amount.toStringAsFixed(2)}',
              style: TextStyle(
                color: AppColors.primaryGreen,
                fontSize: 32,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'has been added to your PlagSini Credits',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(ctx),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: const Text('Done', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showSnackBar(String message, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: color),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Top Up',
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
            // Current balance card
            Consumer<AuthProvider>(
              builder: (context, auth, _) {
                final balance = auth.currentUser?.walletBalance ?? 0;
                final points = auth.currentUser?.walletPoints ?? 0;
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        const Color(0xFF0A1F2F),
                        const Color(0xFF0F2B3D),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primaryGreen.withOpacity(0.05),
                        blurRadius: 20,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.account_balance_wallet, color: AppColors.primaryGreen, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            'PlagSini Credits',
                            style: TextStyle(color: AppColors.textLight, fontSize: 14),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'RM${balance.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 36,
                          fontWeight: FontWeight.bold,
                          letterSpacing: -1,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '🎁 $points reward points',
                        style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.8), fontSize: 12),
                      ),
                    ],
                  ),
                );
              },
            ),

            const SizedBox(height: 28),

            // Quick amount selection
            Text(
              'Select Amount',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),

            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
                childAspectRatio: 2.2,
              ),
              itemCount: _quickAmounts.length,
              itemBuilder: (context, index) {
                final amount = _quickAmounts[index];
                final isSelected = _selectedAmount == amount;
                final isBonus = amount >= 50;

                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _selectedAmount = amount;
                      _customAmountController.clear();
                    });
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    decoration: BoxDecoration(
                      gradient: isSelected
                          ? const LinearGradient(colors: AppColors.primaryGradient)
                          : null,
                      color: isSelected ? null : AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected
                            ? AppColors.primaryGreen
                            : AppColors.borderLight,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    child: Stack(
                      children: [
                        Center(
                          child: Text(
                            'RM${amount.toInt()}',
                            style: TextStyle(
                              color: isSelected ? Colors.white : AppColors.textPrimary,
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        if (isBonus)
                          Positioned(
                            top: 4,
                            right: 4,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                              decoration: BoxDecoration(
                                color: Colors.orange.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                '+BONUS',
                                style: TextStyle(color: Colors.orange, fontSize: 7, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),

            const SizedBox(height: 16),

            // Custom amount
            Text(
              'Or enter custom amount',
              style: TextStyle(color: AppColors.textLight, fontSize: 12),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _customAmountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              style: const TextStyle(color: AppColors.textPrimary, fontSize: 18),
              decoration: InputDecoration(
                hintText: '0.00',
                hintStyle: TextStyle(color: AppColors.textLight),
                prefixText: 'RM ',
                prefixStyle: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
                filled: true,
                fillColor: AppColors.cardBackground,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppColors.borderLight),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppColors.borderLight),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppColors.primaryGreen, width: 2),
                ),
              ),
              onChanged: (value) {
                setState(() => _selectedAmount = null);
              },
            ),

            const SizedBox(height: 28),

            // Payment method selection
            Text(
              'Payment Method',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),

            ...(_paymentMethods.map((method) {
              final isSelected = _selectedPaymentMethod == method['id'];

              return GestureDetector(
                onTap: () {
                  setState(() => _selectedPaymentMethod = method['id']);
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.cardBackground,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isSelected
                          ? AppColors.primaryGreen
                          : AppColors.borderLight,
                      width: isSelected ? 2 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: (method['color'] as Color).withOpacity(0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          method['icon'] as IconData,
                          color: method['color'] as Color,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              method['name'] as String,
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              method['subtitle'] as String,
                              style: TextStyle(
                                color: AppColors.textLight,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isSelected ? AppColors.primaryGreen : AppColors.borderLight,
                            width: 2,
                          ),
                          color: isSelected ? AppColors.primaryGreen : Colors.transparent,
                        ),
                        child: isSelected
                            ? const Icon(Icons.check, color: Colors.white, size: 14)
                            : null,
                      ),
                    ],
                  ),
                ),
              );
            })),

            const SizedBox(height: 24),

            // Summary
            if (_amount > 0) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.primaryGreen.withOpacity(0.2)),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Top-up Amount', style: TextStyle(color: AppColors.textLight)),
                        Text('RM${_amount.toStringAsFixed(2)}', style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                      ],
                    ),
                    if (_amount >= 50) ...[
                      const SizedBox(height: 6),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Bonus Points', style: TextStyle(color: Colors.orange.withOpacity(0.8), fontSize: 12)),
                          Text('+${((_amount.toInt()) * 10) + 50} pts', style: const TextStyle(color: Colors.orange, fontWeight: FontWeight.w600, fontSize: 12)),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    const Divider(height: 1),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Total', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                        Text('RM${_amount.toStringAsFixed(2)}', style: TextStyle(color: AppColors.primaryGreen, fontSize: 22, fontWeight: FontWeight.bold)),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Top up button
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: _isLoading || _amount <= 0 ? null : _processTopUp,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: AppColors.primaryGreen.withOpacity(0.3),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  elevation: 0,
                ),
                child: _isLoading
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.lock_outline, size: 18),
                          const SizedBox(width: 8),
                          Text(
                            _amount > 0
                                ? 'PAY RM${_amount.toStringAsFixed(2)}'
                                : 'SELECT AMOUNT',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
              ),
            ),

            const SizedBox(height: 12),

            Center(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.shield_outlined, color: AppColors.textLight, size: 14),
                  const SizedBox(width: 4),
                  Text(
                    'Secured by PlagSini Payment Gateway',
                    style: TextStyle(color: AppColors.textLight, fontSize: 11),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
