import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  static const FlutterSecureStorage _storage = FlutterSecureStorage();

  static const String _authTokenKey = 'auth_token';
  static const String _refreshTokenKey = 'refresh_token';

  static const String einvoiceNameKey = 'einvoice_name';
  static const String einvoiceIcKey = 'einvoice_ic';
  static const String einvoiceTinKey = 'einvoice_tin';
  static const String einvoiceAddressKey = 'einvoice_address';
  static const String einvoiceCityKey = 'einvoice_city';
  static const String einvoicePostcodeKey = 'einvoice_postcode';
  static const String einvoiceStateKey = 'einvoice_state';
  static const String einvoiceIdTypeKey = 'einvoice_id_type';
  static const String einvoiceVerifiedKey = 'einvoice_verified';

  static Future<void> saveAccessToken(String token) async {
    await _storage.write(key: _authTokenKey, value: token);
  }

  static Future<String?> getAccessToken() async {
    return _storage.read(key: _authTokenKey);
  }

  static Future<void> saveRefreshToken(String token) async {
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  static Future<String?> getRefreshToken() async {
    return _storage.read(key: _refreshTokenKey);
  }

  static Future<void> clearAuthTokens() async {
    await _storage.delete(key: _authTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  static Future<void> setString(String key, String value) async {
    await _storage.write(key: key, value: value);
  }

  static Future<String?> getString(String key) async {
    return _storage.read(key: key);
  }

  static Future<void> setBool(String key, bool value) async {
    await _storage.write(key: key, value: value ? 'true' : 'false');
  }

  static Future<bool> getBool(String key, {bool defaultValue = false}) async {
    final value = await _storage.read(key: key);
    if (value == null) return defaultValue;
    return value.toLowerCase() == 'true';
  }
}
