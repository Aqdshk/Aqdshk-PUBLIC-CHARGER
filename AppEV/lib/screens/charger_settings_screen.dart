import 'dart:async';
import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../services/api_service.dart';
import 'charging_schedule_screen.dart';

class ChargerSettingsScreen extends StatefulWidget {
  final String chargerId;
  final String chargerName;

  const ChargerSettingsScreen({
    super.key,
    required this.chargerId,
    required this.chargerName,
  });

  @override
  State<ChargerSettingsScreen> createState() => _ChargerSettingsScreenState();
}

class _ChargerSettingsScreenState extends State<ChargerSettingsScreen> {
  bool _loading = true;
  bool _saving = false;
  bool _refreshing = false;
  DateTime? _lastSync;
  String? _error;
  Timer? _refreshTimer;

  // Config values
  String _homeNumber = '';
  String _userName = '';
  String _userPass = '';
  bool _statusLight = true;
  bool _logoLight = true;
  bool _backgroundLight = true;
  bool _authSet = false;
  String _backSelection = 'Bio Volt';
  bool _chargerOnline = true; // ChangeAvailability state

  // Text controllers
  final _homeNumberCtrl = TextEditingController();
  final _userNameCtrl = TextEditingController();
  final _userPassCtrl = TextEditingController();
  bool _showPass = false;

  // 8 background options from charger
  static const List<Map<String, dynamic>> _backgrounds = [
    {'name': 'Bio Volt',       'emoji': '🌿', 'color': Color(0xFF1B4332)},
    {'name': 'Verdant Pulse',  'emoji': '💚', 'color': Color(0xFF2D6A4F)},
    {'name': 'Modern Drive',   'emoji': '🚗', 'color': Color(0xFF023E8A)},
    {'name': 'Futuristic City','emoji': '🌆', 'color': Color(0xFF1A1A2E)},
    {'name': 'Eco Wave',       'emoji': '🌊', 'color': Color(0xFF006D77)},
    {'name': 'Solar Ember',    'emoji': '🔥', 'color': Color(0xFF7B2D00)},
    {'name': 'Green Tech',     'emoji': '⚡', 'color': Color(0xFF004B23)},
    {'name': 'Quantum Core',   'emoji': '🔬', 'color': Color(0xFF212121)},
  ];

  @override
  void initState() {
    super.initState();
    _loadConfig();
    // Auto-refresh every 5s so any changes made on the device itself
    // are reflected in the app near-real-time (live sync)
    _refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!_saving && mounted) _silentRefresh();
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _homeNumberCtrl.dispose();
    _userNameCtrl.dispose();
    _userPassCtrl.dispose();
    super.dispose();
  }

  /// Refresh config values in background without showing loading spinner
  Future<void> _silentRefresh() async {
    try {
      final config = await ApiService.getChargerConfiguration(widget.chargerId);
      if (!mounted) return;
      // Skip update if API returned empty (rate-limited, offline, etc)
      // — otherwise toggles would flicker to default values
      if (config.isEmpty) return;
      final Map<String, String> map = {
        for (final c in config) c['key'] as String: c['value'] as String
      };
      setState(() {
        _homeNumber       = map['HomeNumber']      ?? _homeNumber;
        _userName         = map['UserName']        ?? _userName;
        _userPass         = map['UserPass']        ?? _userPass;
        _statusLight      = map['StatusLight']     == 'true';
        _logoLight        = map['LogoLight']       == 'true';
        _backgroundLight  = map['BackgroundLight'] == 'true';
        _authSet          = map['AuthSet']         == 'true';
        _backSelection    = map['BackSelection']   ?? _backSelection;
        _lastSync = DateTime.now();

        // Only update text controllers if not currently being edited
        if (!_homeNumberCtrl.value.composing.isValid) {
          _homeNumberCtrl.text = _homeNumber;
        }
        if (!_userNameCtrl.value.composing.isValid) {
          _userNameCtrl.text = _userName;
        }
      });
    } catch (_) {
      // Silent — don't disturb user on background refresh failure
    }
  }

  Future<void> _loadConfig() async {
    setState(() { _loading = true; _error = null; });
    try {
      final config = await ApiService.getChargerConfiguration(widget.chargerId);
      if (!mounted) return;

      final Map<String, String> map = {
        for (final c in config) c['key'] as String: c['value'] as String
      };

      setState(() {
        _homeNumber = map['HomeNumber'] ?? '';
        _userName   = map['UserName'] ?? '';
        _userPass   = map['UserPass'] ?? '';
        _statusLight      = map['StatusLight']      == 'true';
        _logoLight        = map['LogoLight']        == 'true';
        _backgroundLight  = map['BackgroundLight']  == 'true';
        _authSet          = map['AuthSet']          == 'true';
        _backSelection    = map['BackSelection']    ?? 'Bio Volt';

        _homeNumberCtrl.text = _homeNumber;
        _userNameCtrl.text   = _userName;
        _userPassCtrl.text   = _userPass;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = 'Failed to load settings: $e'; _loading = false; });
    }
  }

  Future<void> _saveKey(String key, String value, {String? displayName}) async {
    setState(() => _saving = true);
    final res = await ApiService.changeChargerConfiguration(widget.chargerId, key, value);
    if (!mounted) return;
    setState(() => _saving = false);

    final ok = res['success'] == true;
    _showSnack(
      ok ? '✅ ${displayName ?? key} updated successfully' : '❌ Failed: ${res['message']}',
      ok ? AppColors.success : AppColors.error,
    );
  }

  Future<void> _toggleAvailability(bool turnOn) async {
    setState(() => _saving = true);
    final type = turnOn ? 'Operative' : 'Inoperative';
    final res = await ApiService.changeChargerAvailability(widget.chargerId, type);
    if (!mounted) return;
    setState(() { _saving = false; _chargerOnline = turnOn; });

    final ok = res['success'] == true;
    _showSnack(
      ok
          ? (turnOn ? '✅ Charger activated' : '✅ Charger deactivated')
          : '❌ Failed: ${res['message']}',
      ok ? AppColors.success : AppColors.error,
    );
  }

  void _showSnack(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(color: Colors.white)),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  void _showEditDialog({
    required String title,
    required TextEditingController controller,
    required String configKey,
    bool obscure = false,
    TextInputType keyboard = TextInputType.text,
  }) {
    showDialog(
      context: context,
      builder: (ctx) {
        bool showPwd = false;
        return StatefulBuilder(builder: (ctx, setDlg) {
          return AlertDialog(
            backgroundColor: AppColors.surface,
            title: Text(title, style: const TextStyle(color: Colors.white)),
            content: TextField(
              controller: controller,
              obscureText: obscure && !showPwd,
              keyboardType: keyboard,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                filled: true,
                fillColor: AppColors.cardBackground,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                enabledBorder: OutlineInputBorder(
                  borderSide: BorderSide(color: AppColors.borderLight),
                  borderRadius: BorderRadius.circular(10),
                ),
                focusedBorder: OutlineInputBorder(
                  borderSide: BorderSide(color: AppColors.primaryGreen),
                  borderRadius: BorderRadius.circular(10),
                ),
                suffixIcon: obscure
                    ? IconButton(
                        icon: Icon(showPwd ? Icons.visibility_off : Icons.visibility,
                            color: AppColors.textSecondary),
                        onPressed: () => setDlg(() => showPwd = !showPwd),
                      )
                    : null,
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryGreen),
                onPressed: () {
                  Navigator.pop(ctx);
                  _saveKey(configKey, controller.text, displayName: title);
                },
                child: const Text('Save', style: TextStyle(color: Colors.black)),
              ),
            ],
          );
        });
      },
    );
  }

  void _showBackgroundPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Select Charger Background',
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            GridView.count(
              crossAxisCount: 4,
              shrinkWrap: true,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              children: _backgrounds.map((bg) {
                final selected = _backSelection == bg['name'];
                return GestureDetector(
                  onTap: () {
                    Navigator.pop(ctx);
                    setState(() => _backSelection = bg['name'] as String);
                    _saveKey('BackSelection', bg['name'] as String,
                        displayName: 'Background');
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    decoration: BoxDecoration(
                      color: bg['color'] as Color,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: selected ? AppColors.primaryGreen : Colors.transparent,
                        width: 2.5,
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(bg['emoji'] as String, style: const TextStyle(fontSize: 22)),
                        const SizedBox(height: 4),
                        Text(
                          (bg['name'] as String).split(' ').first,
                          style: const TextStyle(
                              color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600),
                          textAlign: TextAlign.center,
                        ),
                        if (selected)
                          const Icon(Icons.check_circle, color: Colors.white, size: 14),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Charger Settings',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
            Text(widget.chargerName,
                style: TextStyle(color: AppColors.primaryGreen, fontSize: 12)),
          ],
        ),
        actions: [
          // Live sync indicator — green pulse dot + "LIVE" label
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: AppColors.success,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(color: AppColors.success.withOpacity(0.6), blurRadius: 6, spreadRadius: 1),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                Text('LIVE',
                    style: TextStyle(
                        color: AppColors.success,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1)),
              ],
            ),
          ),
          // Manual refresh (no page reload)
          IconButton(
            icon: _refreshing || _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.refresh, color: Colors.white, size: 22),
            tooltip: 'Refresh settings',
            onPressed: (_refreshing || _saving)
                ? null
                : () async {
                    setState(() => _refreshing = true);
                    await _silentRefresh();
                    if (!mounted) return;
                    setState(() => _refreshing = false);
                    _showSnack('✅ Settings refreshed', AppColors.success);
                  },
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen))
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  color: AppColors.primaryGreen,
                  onRefresh: _loadConfig,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _buildSection(
                        icon: Icons.power_settings_new,
                        title: 'Charger Status',
                        color: _chargerOnline ? AppColors.success : AppColors.error,
                        children: [
                          _buildSwitchTile(
                            icon: _chargerOnline ? Icons.bolt : Icons.bolt_outlined,
                            iconColor: _chargerOnline ? AppColors.success : AppColors.error,
                            title: 'Charging',
                            subtitle: _chargerOnline
                                ? 'Charger is active & ready to charge'
                                : 'Charger is temporarily disabled',
                            value: _chargerOnline,
                            onChanged: (val) {
                              _showConfirmDialog(
                                title: val ? 'Activate Charger?' : 'Deactivate Charger?',
                                content: val
                                    ? 'Charger will be reactivated and available for use.'
                                    : 'Charger will be disabled. No charging sessions can start.',
                                onConfirm: () => _toggleAvailability(val),
                              );
                            },
                          ),
                          _buildDivider(),
                          _buildNavTile(
                            icon: Icons.schedule,
                            title: 'Schedule Charging',
                            subtitle: 'Set auto start/stop times',
                            onTap: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => ChargingScheduleScreen(
                                    chargerId: widget.chargerId,
                                    chargerName: widget.chargerName,
                                  ),
                                ),
                              );
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _buildSection(
                        icon: Icons.lock_outline,
                        title: 'Security',
                        color: AppColors.warning,
                        children: [
                          _buildSwitchTile(
                            icon: _authSet ? Icons.lock : Icons.lock_open,
                            iconColor: _authSet ? AppColors.warning : AppColors.textSecondary,
                            title: 'Lock Charger',
                            subtitle: _authSet
                                ? 'Only authorized users can charge'
                                : 'Anyone can start a charging session',
                            value: _authSet,
                            onChanged: (val) {
                              setState(() => _authSet = val);
                              _saveKey('AuthSet', val.toString(), displayName: 'Lock Charger');
                            },
                          ),
                          _buildDivider(),
                          _buildNavTile(
                            icon: Icons.home_outlined,
                            title: 'Home Number',
                            subtitle: _homeNumber.isNotEmpty ? _homeNumber : 'Not set',
                            onTap: () => _showEditDialog(
                              title: 'Home Number',
                              controller: _homeNumberCtrl,
                              configKey: 'HomeNumber',
                            ),
                          ),
                          _buildDivider(),
                          _buildNavTile(
                            icon: Icons.person_outline,
                            title: 'Username (Admin)',
                            subtitle: _userName.isNotEmpty ? _userName : '-',
                            onTap: () => _showEditDialog(
                              title: 'Username',
                              controller: _userNameCtrl,
                              configKey: 'UserName',
                            ),
                          ),
                          _buildDivider(),
                          _buildNavTile(
                            icon: Icons.key_outlined,
                            title: 'Password (Admin)',
                            subtitle: '••••••••',
                            onTap: () => _showEditDialog(
                              title: 'Password',
                              controller: _userPassCtrl,
                              configKey: 'UserPass',
                              obscure: true,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _buildSection(
                        icon: Icons.lightbulb_outline,
                        title: 'Lights & Display',
                        color: AppColors.primaryGreen,
                        children: [
                          _buildSwitchTile(
                            icon: Icons.sensors,
                            iconColor: _statusLight ? AppColors.primaryGreen : AppColors.textSecondary,
                            title: 'Status Light',
                            subtitle: 'Charger status indicator light',
                            value: _statusLight,
                            onChanged: (val) {
                              setState(() => _statusLight = val);
                              _saveKey('StatusLight', val.toString(), displayName: 'Status Light');
                            },
                          ),
                          _buildDivider(),
                          _buildSwitchTile(
                            icon: Icons.brightness_5_outlined,
                            iconColor: _logoLight ? AppColors.primaryGreen : AppColors.textSecondary,
                            title: 'Logo Light',
                            subtitle: 'Logo lighting on charger',
                            value: _logoLight,
                            onChanged: (val) {
                              setState(() => _logoLight = val);
                              _saveKey('LogoLight', val.toString(), displayName: 'Logo Light');
                            },
                          ),
                          _buildDivider(),
                          _buildSwitchTile(
                            icon: Icons.wb_sunny_outlined,
                            iconColor: _backgroundLight ? AppColors.primaryGreen : AppColors.textSecondary,
                            title: 'Background Light',
                            subtitle: 'Charger screen backlight',
                            value: _backgroundLight,
                            onChanged: (val) {
                              setState(() => _backgroundLight = val);
                              _saveKey('BackgroundLight', val.toString(),
                                  displayName: 'Background Light');
                            },
                          ),
                          _buildDivider(),
                          _buildNavTile(
                            icon: Icons.wallpaper,
                            title: 'Background Image',
                            subtitle: _backSelection,
                            trailing: _buildBgPreview(_backSelection),
                            onTap: _showBackgroundPicker,
                          ),
                        ],
                      ),
                      const SizedBox(height: 32),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppColors.cardBackground,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.borderLight),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.info_outline, color: AppColors.textSecondary, size: 18),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'Every change is sent directly to the charger via OCPP. Charger must be online.',
                                style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],
                  ),
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.wifi_off, color: AppColors.error, size: 48),
          const SizedBox(height: 16),
          Text(_error!, style: TextStyle(color: AppColors.textSecondary), textAlign: TextAlign.center),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryGreen),
            onPressed: _loadConfig,
            icon: const Icon(Icons.refresh, color: Colors.black),
            label: const Text('Try Again', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
  }

  Widget _buildSection({
    required IconData icon,
    required String title,
    required Color color,
    required List<Widget> children,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 10),
          child: Row(
            children: [
              Icon(icon, color: color, size: 16),
              const SizedBox(width: 6),
              Text(title,
                  style: TextStyle(
                      color: color, fontSize: 13, fontWeight: FontWeight.w600,
                      letterSpacing: 0.5)),
            ],
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Column(children: children),
        ),
      ],
    );
  }

  Widget _buildSwitchTile({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: iconColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: iconColor, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
                Text(subtitle, style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: _saving ? null : onChanged,
            activeColor: AppColors.primaryGreen,
            inactiveTrackColor: AppColors.borderLight,
          ),
        ],
      ),
    );
  }

  Widget _buildNavTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    Widget? trailing,
  }) {
    return InkWell(
      onTap: _saving ? null : onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: AppColors.primaryGreen, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
                  Text(subtitle, style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                ],
              ),
            ),
            trailing ?? Icon(Icons.chevron_right, color: AppColors.textSecondary, size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildDivider() => Divider(height: 1, color: AppColors.borderLight, indent: 54);

  Widget _buildBgPreview(String name) {
    final bg = _backgrounds.firstWhere(
      (b) => b['name'] == name,
      orElse: () => _backgrounds.first,
    );
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: bg['color'] as Color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.primaryGreen, width: 1.5),
      ),
      child: Center(child: Text(bg['emoji'] as String, style: const TextStyle(fontSize: 14))),
    );
  }

  void _showConfirmDialog({
    required String title,
    required String content,
    required VoidCallback onConfirm,
  }) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(title, style: const TextStyle(color: Colors.white)),
        content: Text(content, style: TextStyle(color: AppColors.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primaryGreen),
            onPressed: () {
              Navigator.pop(ctx);
              onConfirm();
            },
            child: const Text('Yes, Continue', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
  }
}
