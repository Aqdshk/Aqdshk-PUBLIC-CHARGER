import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class AutoChargeScreen extends StatefulWidget {
  const AutoChargeScreen({super.key});

  @override
  State<AutoChargeScreen> createState() => _AutoChargeScreenState();
}

class _AutoChargeScreenState extends State<AutoChargeScreen> {
  bool _autoChargeEnabled = false;
  bool _autoPayEnabled = false;
  double _maxChargeLimit = 80;
  double _maxSpendLimit = 50;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('AutoCharge', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
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
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), shape: BoxShape.circle),
                    child: const Icon(Icons.auto_awesome, color: Colors.white, size: 48),
                  ),
                  const SizedBox(height: 16),
                  const Text('Plug & Charge', style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  const Text('Just plug in and charging starts automatically.\nNo app interaction needed!', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 14)),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            _ToggleCard(
              icon: Icons.flash_auto,
              title: 'Enable AutoCharge',
              subtitle: 'Start charging automatically when plugged in',
              value: _autoChargeEnabled,
              onChanged: (value) {
                setState(() => _autoChargeEnabled = value);
                if (value) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: const Text('AutoCharge enabled! Link your vehicle to get started.'), backgroundColor: AppColors.primaryGreen),
                  );
                }
              },
            ),
            
            const SizedBox(height: 16),
            
            _ToggleCard(
              icon: Icons.payment,
              title: 'Auto Payment',
              subtitle: 'Automatically pay from wallet when session ends',
              value: _autoPayEnabled,
              onChanged: (value) => setState(() => _autoPayEnabled = value),
            ),
            
            const SizedBox(height: 24),
            
            Text('CHARGE LIMITS', style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
            const SizedBox(height: 12),
            
            _SliderCard(
              title: 'Max Charge Level',
              value: _maxChargeLimit,
              suffix: '%',
              min: 50, max: 100, divisions: 10,
              description: 'Stop charging when battery reaches this level',
              onChanged: (value) => setState(() => _maxChargeLimit = value),
            ),
            
            const SizedBox(height: 12),
            
            _SliderCard(
              title: 'Max Spend Limit',
              value: _maxSpendLimit,
              prefix: 'RM ',
              min: 10, max: 200, divisions: 19,
              description: 'Stop charging when session cost reaches this limit',
              onChanged: (value) => setState(() => _maxSpendLimit = value),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.cardBackground,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('How It Works', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  _HowItWorksStep(number: '1', title: 'Link Your Vehicle', description: 'Add your EV in My Vehicles section'),
                  const SizedBox(height: 12),
                  _HowItWorksStep(number: '2', title: 'Enable AutoCharge', description: 'Turn on the AutoCharge toggle above'),
                  const SizedBox(height: 12),
                  _HowItWorksStep(number: '3', title: 'Just Plug In', description: 'Charging starts automatically at supported stations'),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.08),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.blue.withOpacity(0.2)),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, color: Colors.blue.shade300),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'AutoCharge is available at stations marked with the ⚡ symbol. More stations coming soon!',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
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

class _ToggleCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleCard({required this.icon, required this.title, required this.subtitle, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: AppColors.primaryGreen, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                Text(subtitle, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
              ],
            ),
          ),
          Switch(value: value, onChanged: onChanged, activeColor: AppColors.primaryGreen),
        ],
      ),
    );
  }
}

class _SliderCard extends StatelessWidget {
  final String title;
  final double value;
  final String? prefix;
  final String? suffix;
  final double min, max;
  final int divisions;
  final String description;
  final ValueChanged<double> onChanged;

  const _SliderCard({required this.title, required this.value, this.prefix, this.suffix, required this.min, required this.max, required this.divisions, required this.description, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
              Text('${prefix ?? ''}${value.toInt()}${suffix ?? ''}', style: TextStyle(color: AppColors.primaryGreen, fontSize: 18, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 8),
          Slider(value: value, min: min, max: max, divisions: divisions, onChanged: onChanged),
          Text(description, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
        ],
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
