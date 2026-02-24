import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class BusinessAccountsScreen extends StatefulWidget {
  const BusinessAccountsScreen({super.key});

  @override
  State<BusinessAccountsScreen> createState() => _BusinessAccountsScreenState();
}

class _BusinessAccountsScreenState extends State<BusinessAccountsScreen> {
  List<Map<String, dynamic>> _linkedAccounts = [];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Business Accounts', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [AppColors.primaryGreen, AppColors.darkGreen]),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [BoxShadow(color: AppColors.primaryGreen.withOpacity(0.3), blurRadius: 15)],
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
                    child: const Icon(Icons.business_center, color: Colors.white, size: 32),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Text('Business Charging', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                        SizedBox(height: 4),
                        Text('Link your company account for fleet charging', style: TextStyle(color: Colors.white70, fontSize: 12)),
                      ],
                    ),
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
                  Text('Business Account Benefits', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  _BenefitItem(icon: Icons.receipt_long, title: 'Consolidated Billing', description: 'All charges billed directly to your company'),
                  const SizedBox(height: 12),
                  _BenefitItem(icon: Icons.discount, title: 'Corporate Discounts', description: 'Up to 15% off on all charging sessions'),
                  const SizedBox(height: 12),
                  _BenefitItem(icon: Icons.analytics, title: 'Fleet Reports', description: 'Detailed usage reports for each vehicle'),
                  const SizedBox(height: 12),
                  _BenefitItem(icon: Icons.support_agent, title: 'Priority Support', description: 'Dedicated account manager'),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Text('LINKED BUSINESS ACCOUNTS', style: TextStyle(color: AppColors.primaryGreen.withOpacity(0.7), fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1)),
            const SizedBox(height: 12),
            
            if (_linkedAccounts.isEmpty)
              _buildEmptyState()
            else
              ..._linkedAccounts.map((account) => _BusinessAccountCard(
                companyName: account['name'],
                role: account['role'],
                status: account['status'],
                onRemove: () => _removeAccount(account),
              )),
            
            const SizedBox(height: 24),
            
            SizedBox(
              width: double.infinity,
              height: 52,
              child: OutlinedButton.icon(
                onPressed: _showLinkAccountDialog,
                icon: const Icon(Icons.add),
                label: const Text('LINK BUSINESS ACCOUNT'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.primaryGreen,
                  side: BorderSide(color: AppColors.primaryGreen),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withOpacity(0.2)),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, color: Colors.blue.shade300),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Want to register your company?', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Text('Contact our business team to set up a corporate account.', style: TextStyle(color: AppColors.textLight, fontSize: 12)),
                        const SizedBox(height: 8),
                        GestureDetector(
                          onTap: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Contact: business@plagsini.com.my'), backgroundColor: Colors.blue)),
                          child: Text('Contact Business Team →', style: TextStyle(color: Colors.blue.shade300, fontWeight: FontWeight.w600, fontSize: 13)),
                        ),
                      ],
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

  Widget _buildEmptyState() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.borderLight)),
      child: Column(
        children: [
          Icon(Icons.business_center_outlined, size: 48, color: AppColors.textLight),
          const SizedBox(height: 16),
          Text('No Business Account Linked', style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Text('Link your company account to enjoy business charging benefits', textAlign: TextAlign.center, style: TextStyle(color: AppColors.textLight, fontSize: 13)),
        ],
      ),
    );
  }

  void _showLinkAccountDialog() {
    final codeController = TextEditingController();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.cardBackground,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom, left: 20, right: 20, top: 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.borderLight, borderRadius: BorderRadius.circular(2)))),
            const SizedBox(height: 20),
            Text('Link Business Account', style: TextStyle(color: AppColors.primaryGreen, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Enter the invitation code provided by your company administrator.', style: TextStyle(color: AppColors.textLight, fontSize: 13)),
            const SizedBox(height: 20),
            TextField(
              controller: codeController,
              style: TextStyle(color: AppColors.textPrimary, letterSpacing: 2),
              textCapitalization: TextCapitalization.characters,
              decoration: InputDecoration(
                labelText: 'Invitation Code',
                hintText: 'e.g. CORP-XXXX-XXXX',
                prefixIcon: Icon(Icons.vpn_key, color: AppColors.primaryGreen),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: () {
                  if (codeController.text.isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please enter an invitation code'), backgroundColor: Colors.red));
                    return;
                  }
                  Navigator.pop(context);
                  setState(() {
                    _linkedAccounts.add({'name': 'AGMO Holdings Sdn Bhd', 'role': 'Employee', 'status': 'active'});
                  });
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('Business account linked successfully!'), backgroundColor: AppColors.primaryGreen));
                },
                style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryGreen, foregroundColor: AppColors.background, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                child: const Text('LINK ACCOUNT', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  void _removeAccount(Map<String, dynamic> account) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: AppColors.borderLight)),
        title: Text('Remove Account?', style: TextStyle(color: AppColors.primaryGreen)),
        content: Text('Are you sure you want to unlink ${account['name']}?', style: TextStyle(color: AppColors.textLight)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text('Cancel', style: TextStyle(color: AppColors.textLight))),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() { _linkedAccounts.remove(account); });
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Account unlinked'), backgroundColor: Colors.orange));
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
  }
}

class _BenefitItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;

  const _BenefitItem({required this.icon, required this.title, required this.description});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(8)),
          child: Icon(icon, color: AppColors.primaryGreen, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
              Text(description, style: TextStyle(color: AppColors.textLight, fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }
}

class _BusinessAccountCard extends StatelessWidget {
  final String companyName;
  final String role;
  final String status;
  final VoidCallback onRemove;

  const _BusinessAccountCard({required this.companyName, required this.role, required this.status, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.cardBackground, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3))),
      child: Row(
        children: [
          Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(12)), child: Icon(Icons.business, color: AppColors.primaryGreen, size: 28)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(companyName, style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2), decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10)), child: Text(role, style: TextStyle(color: AppColors.textLight, fontSize: 11))),
                    const SizedBox(width: 8),
                    Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2), decoration: BoxDecoration(color: AppColors.primaryGreen.withOpacity(0.12), borderRadius: BorderRadius.circular(10)), child: Text(status.toUpperCase(), style: TextStyle(color: AppColors.primaryGreen, fontSize: 10, fontWeight: FontWeight.bold))),
                  ],
                ),
              ],
            ),
          ),
          IconButton(onPressed: onRemove, icon: Icon(Icons.link_off, color: Colors.red.shade400), tooltip: 'Unlink account'),
        ],
      ),
    );
  }
}
