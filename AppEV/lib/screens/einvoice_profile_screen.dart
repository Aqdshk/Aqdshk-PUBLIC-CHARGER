import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../services/secure_storage_service.dart';

class EInvoiceProfileScreen extends StatefulWidget {
  const EInvoiceProfileScreen({super.key});

  @override
  State<EInvoiceProfileScreen> createState() => _EInvoiceProfileScreenState();
}

class _EInvoiceProfileScreenState extends State<EInvoiceProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _icController = TextEditingController();
  final _tinController = TextEditingController();
  final _addressController = TextEditingController();
  final _cityController = TextEditingController();
  final _postcodeController = TextEditingController();
  final _stateController = TextEditingController();
  String _selectedIdType = 'NRIC';
  bool _isVerified = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _loadSavedProfile();
  }

  Future<void> _loadSavedProfile() async {
    final name = await SecureStorageService.getString(SecureStorageService.einvoiceNameKey) ?? '';
    final ic = await SecureStorageService.getString(SecureStorageService.einvoiceIcKey) ?? '';
    final tin = await SecureStorageService.getString(SecureStorageService.einvoiceTinKey) ?? '';
    final address = await SecureStorageService.getString(SecureStorageService.einvoiceAddressKey) ?? '';
    final city = await SecureStorageService.getString(SecureStorageService.einvoiceCityKey) ?? '';
    final postcode = await SecureStorageService.getString(SecureStorageService.einvoicePostcodeKey) ?? '';
    final state = await SecureStorageService.getString(SecureStorageService.einvoiceStateKey) ?? '';
    final idType = await SecureStorageService.getString(SecureStorageService.einvoiceIdTypeKey) ?? 'NRIC';
    final verified = await SecureStorageService.getBool(
      SecureStorageService.einvoiceVerifiedKey,
      defaultValue: false,
    );

    if (!mounted) return;
    setState(() {
      _nameController.text = name;
      _icController.text = ic;
      _tinController.text = tin;
      _addressController.text = address;
      _cityController.text = city;
      _postcodeController.text = postcode;
      _stateController.text = state;
      _selectedIdType = idType;
      _isVerified = verified;
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _icController.dispose();
    _tinController.dispose();
    _addressController.dispose();
    _cityController.dispose();
    _postcodeController.dispose();
    _stateController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'e-Invoice Profile',
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
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Info Banner
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blue.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.blue.withOpacity(0.3)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.blue),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'This information will be used for e-Invoice generation as required by LHDN Malaysia.',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 24),
              
              // Status
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.borderLight),
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: _isVerified ? AppColors.primaryGreen.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        _isVerified ? Icons.verified : Icons.pending,
                        color: _isVerified ? AppColors.primaryGreen : Colors.orange,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Verification Status',
                            style: TextStyle(
                              color: AppColors.textLight,
                              fontSize: 12,
                            ),
                          ),
                          Text(
                            _isVerified ? 'Verified' : 'Not Verified',
                            style: TextStyle(
                              color: _isVerified ? AppColors.primaryGreen : Colors.orange,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 24),
              _buildSectionTitle('PERSONAL INFORMATION'),
              const SizedBox(height: 12),
              
              _buildTextField(
                controller: _nameController,
                label: 'Full Name (as per IC)',
                hint: 'Enter your full name',
                icon: Icons.person_outline,
              ),
              
              const SizedBox(height: 16),
              
              Text(
                'Identification Type',
                style: TextStyle(
                  color: AppColors.textLight,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.borderLight),
                ),
                child: DropdownButtonFormField<String>(
                  value: _selectedIdType,
                  dropdownColor: AppColors.cardBackground,
                  style: TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(horizontal: 16),
                  ),
                  items: ['NRIC', 'Passport', 'BRN', 'Army ID'].map((type) {
                    return DropdownMenuItem(
                      value: type,
                      child: Text(type),
                    );
                  }).toList(),
                  onChanged: (value) {
                    setState(() => _selectedIdType = value!);
                  },
                ),
              ),
              
              const SizedBox(height: 16),
              
              _buildTextField(
                controller: _icController,
                label: _selectedIdType == 'NRIC' ? 'IC Number' : '${_selectedIdType} Number',
                hint: _selectedIdType == 'NRIC' ? 'e.g. 901231-14-1234' : 'Enter number',
                icon: Icons.badge_outlined,
              ),
              
              const SizedBox(height: 16),
              
              _buildTextField(
                controller: _tinController,
                label: 'TIN (Tax Identification Number)',
                hint: 'e.g. C12345678901',
                icon: Icons.receipt_long_outlined,
                isRequired: false,
              ),
              
              const SizedBox(height: 24),
              _buildSectionTitle('ADDRESS'),
              const SizedBox(height: 12),
              
              _buildTextField(
                controller: _addressController,
                label: 'Street Address',
                hint: 'Enter your address',
                icon: Icons.home_outlined,
                maxLines: 2,
              ),
              
              const SizedBox(height: 16),
              
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: _buildTextField(
                      controller: _cityController,
                      label: 'City',
                      hint: 'e.g. Cyberjaya',
                      icon: Icons.location_city_outlined,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildTextField(
                      controller: _postcodeController,
                      label: 'Postcode',
                      hint: 'e.g. 63000',
                      icon: Icons.pin_drop_outlined,
                      isNumber: true,
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              _buildTextField(
                controller: _stateController,
                label: 'State',
                hint: 'e.g. Selangor',
                icon: Icons.map_outlined,
              ),
              
              const SizedBox(height: 32),
              
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _isSaving ? null : _saveProfile,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primaryGreen,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: _isSaving
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Text(
                          'SAVE e-INVOICE PROFILE',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                ),
              ),
              
              const SizedBox(height: 16),
              
              Center(
                child: TextButton.icon(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (context) => AlertDialog(
                        backgroundColor: AppColors.cardBackground,
                        title: Text('What is e-Invoice?', style: TextStyle(color: AppColors.textPrimary)),
                        content: SingleChildScrollView(
                          child: Text(
                            'e-Invoice is Malaysia\'s electronic invoicing system by LHDN. '
                            'Starting 2024, businesses must issue e-Invoices for transactions.\n\n'
                            'By providing your details, you can receive valid e-Invoices for your '
                            'charging sessions, which can be used for tax purposes.',
                            style: TextStyle(color: AppColors.textLight),
                          ),
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(context),
                            child: Text('Got it', style: TextStyle(color: AppColors.primaryGreen)),
                          ),
                        ],
                      ),
                    );
                  },
                  icon: Icon(Icons.help_outline, color: AppColors.primaryGreen, size: 18),
                  label: Text(
                    'Learn more about e-Invoice',
                    style: TextStyle(color: AppColors.primaryGreen),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: TextStyle(
        color: AppColors.textLight,
        fontSize: 12,
        fontWeight: FontWeight.w600,
        letterSpacing: 1,
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    bool isNumber = false,
    bool isRequired = true,
    int maxLines = 1,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              label,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            if (isRequired)
              Text(
                ' *',
                style: TextStyle(color: Colors.red, fontSize: 12),
              ),
          ],
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          keyboardType: isNumber ? TextInputType.number : TextInputType.text,
          maxLines: maxLines,
          style: TextStyle(color: AppColors.textPrimary),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: AppColors.textLight),
            prefixIcon: Icon(icon, color: AppColors.primaryGreen, size: 20),
            filled: true,
            fillColor: AppColors.surface,
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
              borderSide: BorderSide(color: AppColors.primaryGreen),
            ),
          ),
          validator: isRequired
              ? (value) {
                  if (value == null || value.isEmpty) {
                    return 'This field is required';
                  }
                  return null;
                }
              : null,
        ),
      ],
    );
  }

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSaving = true);

    try {
      await SecureStorageService.setString(
        SecureStorageService.einvoiceNameKey,
        _nameController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceIcKey,
        _icController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceTinKey,
        _tinController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceAddressKey,
        _addressController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceCityKey,
        _cityController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoicePostcodeKey,
        _postcodeController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceStateKey,
        _stateController.text.trim(),
      );
      await SecureStorageService.setString(
        SecureStorageService.einvoiceIdTypeKey,
        _selectedIdType,
      );
      await SecureStorageService.setBool(
        SecureStorageService.einvoiceVerifiedKey,
        true,
      );

      if (!mounted) return;
      setState(() => _isVerified = true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('e-Invoice profile saved successfully!'),
          backgroundColor: AppColors.primaryGreen,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error saving profile: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }
}
