import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../constants/app_colors.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';

class SignInMethodsScreen extends StatefulWidget {
  const SignInMethodsScreen({super.key});

  @override
  State<SignInMethodsScreen> createState() => _SignInMethodsScreenState();
}

class _SignInMethodsScreenState extends State<SignInMethodsScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Sign In Methods',
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
            // Header
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    AppColors.primaryGreen,
                    AppColors.darkGreen,
                  ],
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  const Icon(Icons.security, color: Colors.white, size: 40),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Text(
                          'Account Security',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Manage how you sign in to your account',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 24),
            
            Text(
              'SIGN IN METHODS',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            
            // Email/Password
            _SignInMethodTile(
              icon: Icons.email_outlined,
              title: 'Email & Password',
              subtitle: 'Sign in with your email address',
              isConnected: true,
              onTap: () => _showChangePasswordDialog(context),
            ),
            
            // Google
            _SignInMethodTile(
              icon: Icons.g_mobiledata,
              title: 'Google',
              subtitle: 'Connect your Google account',
              isConnected: false,
              onTap: () => _showConnectDialog(context, 'Google'),
            ),
            
            // Apple
            _SignInMethodTile(
              icon: Icons.apple,
              title: 'Apple',
              subtitle: 'Connect your Apple ID',
              isConnected: false,
              onTap: () => _showConnectDialog(context, 'Apple'),
            ),
            
            // Phone
            _SignInMethodTile(
              icon: Icons.phone_outlined,
              title: 'Phone Number',
              subtitle: 'Sign in with SMS verification',
              isConnected: false,
              onTap: () => _showConnectDialog(context, 'Phone'),
            ),
            
            const SizedBox(height: 24),
            
            Text(
              'TWO-FACTOR AUTHENTICATION',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.cardBackground,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Row(
                children: [
                  Icon(Icons.shield_outlined, color: AppColors.primaryGreen),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '2FA Authentication',
                          style: TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        Text(
                          'Add extra security to your account',
                          style: TextStyle(
                            color: AppColors.textLight,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Switch(
                    value: false,
                    onChanged: (value) {
                      showDialog(
                        context: context,
                        builder: (ctx) => AlertDialog(
                          backgroundColor: AppColors.cardBackground,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                            side: BorderSide(color: AppColors.borderLight),
                          ),
                          title: Row(
                            children: [
                              Icon(Icons.shield, color: AppColors.primaryGreen),
                              const SizedBox(width: 12),
                              Text('2FA Setup', style: TextStyle(color: AppColors.textPrimary)),
                            ],
                          ),
                          content: Text(
                            'Two-factor authentication is being implemented and will be available in a future update. '
                            'Your account is secured with email & password authentication.',
                            style: TextStyle(color: AppColors.textLight, fontSize: 14, height: 1.5),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(ctx),
                              child: Text('OK', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.w600)),
                            ),
                          ],
                        ),
                      );
                    },
                    activeColor: AppColors.primaryGreen,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  void _showChangePasswordDialog(BuildContext context) {
    final currentPwCtrl = TextEditingController();
    final newPwCtrl = TextEditingController();
    final confirmPwCtrl = TextEditingController();
    bool loading = false;
    String? error;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.cardBackground,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text('Change Password', style: TextStyle(color: AppColors.textPrimary)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (error != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.withOpacity(0.3)),
                  ),
                  child: Text(error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                ),
              TextField(
                controller: currentPwCtrl,
                obscureText: true,
                style: TextStyle(color: AppColors.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Current Password',
                  labelStyle: TextStyle(color: AppColors.textLight),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.borderLight),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.primaryGreen),
                  ),
                  prefixIcon: Icon(Icons.lock_outline, color: AppColors.primaryGreen),
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: newPwCtrl,
                obscureText: true,
                style: TextStyle(color: AppColors.textPrimary),
                decoration: InputDecoration(
                  labelText: 'New Password',
                  labelStyle: TextStyle(color: AppColors.textLight),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.borderLight),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.primaryGreen),
                  ),
                  prefixIcon: Icon(Icons.lock_reset, color: AppColors.primaryGreen),
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: confirmPwCtrl,
                obscureText: true,
                style: TextStyle(color: AppColors.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Confirm New Password',
                  labelStyle: TextStyle(color: AppColors.textLight),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.borderLight),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: AppColors.primaryGreen),
                  ),
                  prefixIcon: Icon(Icons.lock_outline, color: AppColors.primaryGreen),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: loading ? null : () => Navigator.pop(ctx),
              child: Text('Cancel', style: TextStyle(color: AppColors.textLight)),
            ),
            ElevatedButton(
              onPressed: loading
                  ? null
                  : () async {
                      // Validate
                      if (currentPwCtrl.text.isEmpty || newPwCtrl.text.isEmpty || confirmPwCtrl.text.isEmpty) {
                        setDialogState(() => error = 'Please fill all fields');
                        return;
                      }
                      if (newPwCtrl.text.length < 6) {
                        setDialogState(() => error = 'New password must be at least 6 characters');
                        return;
                      }
                      if (newPwCtrl.text != confirmPwCtrl.text) {
                        setDialogState(() => error = 'New passwords do not match');
                        return;
                      }

                      setDialogState(() { loading = true; error = null; });

                      final auth = Provider.of<AuthProvider>(context, listen: false);
                      final userId = auth.currentUser?.id ?? 0;

                      if (userId == 0) {
                        setDialogState(() { loading = false; error = 'Not logged in'; });
                        return;
                      }

                      final result = await ApiService.changePassword(
                        userId,
                        currentPassword: currentPwCtrl.text,
                        newPassword: newPwCtrl.text,
                      );

                      if (!ctx.mounted) return;

                      if (result['success'] == true) {
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: const Text('Password updated successfully!'),
                            backgroundColor: AppColors.primaryGreen,
                          ),
                        );
                      } else {
                        setDialogState(() {
                          loading = false;
                          error = result['message'] ?? 'Failed to change password';
                        });
                      }
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: loading
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('Update'),
            ),
          ],
        ),
      ),
    );
  }
  
  void _showConnectDialog(BuildContext context, String provider) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.cardBackground,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: AppColors.borderLight),
        ),
        title: Row(
          children: [
            Icon(Icons.link, color: AppColors.primaryGreen),
            const SizedBox(width: 12),
            Text('Connect $provider', style: TextStyle(color: AppColors.textPrimary)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$provider sign-in is currently being configured and will be available in a future update.',
              style: TextStyle(color: AppColors.textLight, fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.06),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.blue.withOpacity(0.15)),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, color: Colors.blue.shade300, size: 18),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'You can currently sign in using your email and password.',
                      style: TextStyle(color: AppColors.textLight, fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('OK', style: TextStyle(color: AppColors.primaryGreen, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _SignInMethodTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool isConnected;
  final VoidCallback onTap;

  const _SignInMethodTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.isConnected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.primaryGreen.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: AppColors.primaryGreen),
        ),
        title: Text(
          title,
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: Text(
          subtitle,
          style: TextStyle(
            color: AppColors.textLight,
            fontSize: 12,
          ),
        ),
        trailing: isConnected
            ? Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.primaryGreen.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Connected',
                  style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              )
            : Icon(Icons.chevron_right, color: AppColors.primaryGreen),
        onTap: onTap,
      ),
    );
  }
}
