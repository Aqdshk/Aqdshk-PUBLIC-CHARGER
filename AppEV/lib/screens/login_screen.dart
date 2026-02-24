import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../constants/app_colors.dart';
import '../services/api_service.dart';
import '../widgets/ev_illustration.dart';
import 'otp_verification_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _loginFormKey = GlobalKey<FormState>();
  final _registerFormKey = GlobalKey<FormState>();

  // Login controllers
  final _loginEmailController = TextEditingController();
  final _loginPasswordController = TextEditingController();

  // Register controllers
  final _registerNameController = TextEditingController();
  final _registerEmailController = TextEditingController();
  final _registerPhoneController = TextEditingController();
  final _registerPasswordController = TextEditingController();
  final _registerConfirmPasswordController = TextEditingController();

  bool _obscureLoginPassword = true;
  bool _obscureRegisterPassword = true;
  bool _obscureConfirmPassword = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _loginEmailController.dispose();
    _loginPasswordController.dispose();
    _registerNameController.dispose();
    _registerEmailController.dispose();
    _registerPhoneController.dispose();
    _registerPasswordController.dispose();
    _registerConfirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_loginFormKey.currentState!.validate()) return;

    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.login(
      email: _loginEmailController.text.trim(),
      password: _loginPasswordController.text,
    );

    if (mounted) {
      if (success) {
        Navigator.pop(context);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(authProvider.error ?? 'Login failed'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _handleRegister() async {
    if (!_registerFormKey.currentState!.validate()) return;

    final email = _registerEmailController.text.trim();
    final password = _registerPasswordController.text;
    final name = _registerNameController.text.trim();
    final phone = _registerPhoneController.text.trim().isEmpty
        ? null
        : _registerPhoneController.text.trim();

    final authProvider = context.read<AuthProvider>();

    // Step 1: Send OTP to email
    final otpSent = await authProvider.sendOTP(email: email);

    if (mounted) {
      if (otpSent) {
        // Step 2: Navigate to OTP verification screen
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => OTPVerificationScreen(
              email: email,
              password: password,
              name: name,
              phone: phone,
            ),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(authProvider.error ?? 'Failed to send verification code'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Welcome',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppColors.primaryGreen,
          labelColor: AppColors.primaryGreen,
          unselectedLabelColor: AppColors.textLight,
          tabs: const [
            Tab(text: 'LOGIN'),
            Tab(text: 'REGISTER'),
          ],
        ),
      ),
      body: Consumer<AuthProvider>(
        builder: (context, authProvider, _) {
          return TabBarView(
            controller: _tabController,
            children: [
              _buildLoginTab(authProvider),
              _buildRegisterTab(authProvider),
            ],
          );
        },
      ),
    );
  }

  Widget _buildLoginTab(AuthProvider authProvider) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _loginFormKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Flat 2D Illustration - Person charging EV
            const EVChargingIllustration(height: 190),
            const SizedBox(height: 16),
            Center(
              child: ShaderMask(
                shaderCallback: (bounds) => LinearGradient(
                  colors: [AppColors.primaryGreen, AppColors.textPrimary],
                ).createShader(bounds),
                child: const Text(
                  'Welcome Back!',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 6),
            Center(
              child: Text(
                'Login to continue charging',
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 14,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const SizedBox(height: 28),

            // Email field
            Text(
              'Email',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _loginEmailController,
              keyboardType: TextInputType.emailAddress,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Enter your email',
                icon: Icons.email_outlined,
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Please enter your email';
                }
                if (!value.contains('@')) {
                  return 'Please enter a valid email';
                }
                return null;
              },
            ),
            const SizedBox(height: 20),

            // Password field
            Text(
              'Password',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _loginPasswordController,
              obscureText: _obscureLoginPassword,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Enter your password',
                icon: Icons.lock_outline,
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscureLoginPassword ? Icons.visibility_off : Icons.visibility,
                    color: AppColors.textLight,
                  ),
                  onPressed: () {
                    setState(() => _obscureLoginPassword = !_obscureLoginPassword);
                  },
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter your password';
                }
                return null;
              },
            ),
            const SizedBox(height: 12),

            // Forgot password
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => _showForgotPasswordDialog(context),
                child: Text(
                  'Forgot Password?',
                  style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Login button
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: authProvider.isLoading ? null : _handleLogin,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 0,
                ),
                child: authProvider.isLoading
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text(
                        'LOGIN',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRegisterTab(AuthProvider authProvider) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _registerFormKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Flat 2D Illustration - Register
            const EVRegisterIllustration(height: 150),
            const SizedBox(height: 12),
            Center(
              child: ShaderMask(
                shaderCallback: (bounds) => LinearGradient(
                  colors: [AppColors.primaryGreen, AppColors.textPrimary],
                ).createShader(bounds),
                child: const Text(
                  'Create Account',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 6),
            Center(
              child: Text(
                'Start your EV charging journey',
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 14,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Name field
            Text(
              'Full Name',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _registerNameController,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Enter your full name',
                icon: Icons.person_outline,
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Please enter your name';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Email field
            Text(
              'Email',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _registerEmailController,
              keyboardType: TextInputType.emailAddress,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Enter your email',
                icon: Icons.email_outlined,
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Please enter your email';
                }
                if (!value.contains('@')) {
                  return 'Please enter a valid email';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Phone field (optional)
            Text(
              'Phone Number (Optional)',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _registerPhoneController,
              keyboardType: TextInputType.phone,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: '+60123456789',
                icon: Icons.phone_outlined,
              ),
            ),
            const SizedBox(height: 16),

            // Password field
            Text(
              'Password',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _registerPasswordController,
              obscureText: _obscureRegisterPassword,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Create a password',
                icon: Icons.lock_outline,
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscureRegisterPassword ? Icons.visibility_off : Icons.visibility,
                    color: AppColors.textLight,
                  ),
                  onPressed: () {
                    setState(() => _obscureRegisterPassword = !_obscureRegisterPassword);
                  },
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter a password';
                }
                if (value.length < 6) {
                  return 'Password must be at least 6 characters';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Confirm password field
            Text(
              'Confirm Password',
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _registerConfirmPasswordController,
              obscureText: _obscureConfirmPassword,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: _inputDecoration(
                hint: 'Confirm your password',
                icon: Icons.lock_outline,
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscureConfirmPassword ? Icons.visibility_off : Icons.visibility,
                    color: AppColors.textLight,
                  ),
                  onPressed: () {
                    setState(() => _obscureConfirmPassword = !_obscureConfirmPassword);
                  },
                ),
              ),
              validator: (value) {
                if (value != _registerPasswordController.text) {
                  return 'Passwords do not match';
                }
                return null;
              },
            ),
            const SizedBox(height: 24),

            // Register button
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: authProvider.isLoading ? null : _handleRegister,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 0,
                ),
                child: authProvider.isLoading
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text(
                        'SEND VERIFICATION CODE',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),

            const SizedBox(height: 16),

            // Terms
            Center(
              child: Text(
                'By registering, you agree to our Terms of Service\nand Privacy Policy',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _inputDecoration({
    required String hint,
    required IconData icon,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: AppColors.textLight),
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
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Colors.red),
      ),
      prefixIcon: Icon(icon, color: AppColors.primaryGreen),
      suffixIcon: suffixIcon,
    );
  }

  // ==================== FORGOT PASSWORD ====================

  void _showForgotPasswordDialog(BuildContext context) {
    final emailCtrl = TextEditingController(text: _loginEmailController.text);
    final otpCtrl = TextEditingController();
    final newPwCtrl = TextEditingController();
    final confirmPwCtrl = TextEditingController();
    bool otpSent = false;
    bool loading = false;
    String? error;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.cardBackground,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Row(
            children: [
              Icon(Icons.lock_reset, color: AppColors.primaryGreen, size: 24),
              const SizedBox(width: 8),
              Text(
                otpSent ? 'Reset Password' : 'Forgot Password',
                style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (error != null)
                  Container(
                    padding: const EdgeInsets.all(10),
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.red.withOpacity(0.3)),
                    ),
                    child: Text(error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                  ),
                if (!otpSent) ...[
                  Text(
                    'Enter your email address and we\'ll send you a verification code to reset your password.',
                    style: TextStyle(color: AppColors.textLight, fontSize: 13),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    style: TextStyle(color: AppColors.textPrimary),
                    decoration: InputDecoration(
                      hintText: 'Email address',
                      hintStyle: TextStyle(color: AppColors.textLight),
                      filled: true,
                      fillColor: AppColors.surface,
                      prefixIcon: Icon(Icons.email, color: AppColors.primaryGreen),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                ] else ...[
                  Text(
                    'Enter the 6-digit code sent to ${emailCtrl.text} and your new password.',
                    style: TextStyle(color: AppColors.textLight, fontSize: 13),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: otpCtrl,
                    keyboardType: TextInputType.number,
                    maxLength: 6,
                    style: TextStyle(color: AppColors.textPrimary, letterSpacing: 8, fontWeight: FontWeight.bold, fontSize: 20),
                    textAlign: TextAlign.center,
                    decoration: InputDecoration(
                      hintText: '000000',
                      hintStyle: TextStyle(color: AppColors.textLight.withOpacity(0.3)),
                      filled: true,
                      fillColor: AppColors.surface,
                      counterText: '',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: newPwCtrl,
                    obscureText: true,
                    style: TextStyle(color: AppColors.textPrimary),
                    decoration: InputDecoration(
                      hintText: 'New password',
                      hintStyle: TextStyle(color: AppColors.textLight),
                      filled: true,
                      fillColor: AppColors.surface,
                      prefixIcon: Icon(Icons.lock, color: AppColors.primaryGreen),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: confirmPwCtrl,
                    obscureText: true,
                    style: TextStyle(color: AppColors.textPrimary),
                    decoration: InputDecoration(
                      hintText: 'Confirm new password',
                      hintStyle: TextStyle(color: AppColors.textLight),
                      filled: true,
                      fillColor: AppColors.surface,
                      prefixIcon: Icon(Icons.lock_outline, color: AppColors.primaryGreen),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('Cancel', style: TextStyle(color: AppColors.textLight)),
            ),
            ElevatedButton(
              onPressed: loading
                  ? null
                  : () async {
                      setDialogState(() { error = null; loading = true; });
                      if (!otpSent) {
                        // Send OTP
                        if (emailCtrl.text.trim().isEmpty || !emailCtrl.text.contains('@')) {
                          setDialogState(() { error = 'Please enter a valid email'; loading = false; });
                          return;
                        }
                        final result = await ApiService.forgotPassword(email: emailCtrl.text.trim());
                        if (result['success'] == true) {
                          setDialogState(() { otpSent = true; loading = false; });
                        } else {
                          setDialogState(() { error = result['message'] ?? 'Failed to send code'; loading = false; });
                        }
                      } else {
                        // Verify OTP and reset password
                        if (otpCtrl.text.length != 6) {
                          setDialogState(() { error = 'Please enter the 6-digit code'; loading = false; });
                          return;
                        }
                        if (newPwCtrl.text.length < 6) {
                          setDialogState(() { error = 'Password must be at least 6 characters'; loading = false; });
                          return;
                        }
                        if (newPwCtrl.text != confirmPwCtrl.text) {
                          setDialogState(() { error = 'Passwords do not match'; loading = false; });
                          return;
                        }
                        // First verify OTP
                        final verifyResult = await ApiService.verifyOTP(
                          email: emailCtrl.text.trim(),
                          otpCode: otpCtrl.text.trim(),
                        );
                        if (verifyResult['success'] != true) {
                          setDialogState(() { error = verifyResult['message'] ?? 'Invalid code'; loading = false; });
                          return;
                        }
                        // Then reset password
                        final resetResult = await ApiService.resetPassword(
                          email: emailCtrl.text.trim(),
                          otpCode: otpCtrl.text.trim(),
                          newPassword: newPwCtrl.text,
                        );
                        setDialogState(() => loading = false);
                        if (resetResult['success'] == true) {
                          Navigator.pop(ctx);
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: const Text('Password reset successfully! Please login.'),
                                backgroundColor: AppColors.primaryGreen,
                              ),
                            );
                          }
                        } else {
                          setDialogState(() { error = resetResult['message'] ?? 'Reset failed'; });
                        }
                      }
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                foregroundColor: AppColors.background,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: loading
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                  : Text(otpSent ? 'Reset Password' : 'Send Code', style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }
}
