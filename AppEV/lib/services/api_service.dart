import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'secure_storage_service.dart';

class AuthSessionExpiredException implements Exception {
  final String message;
  AuthSessionExpiredException([this.message = 'Session expired. Please login again.']);

  @override
  String toString() => message;
}

class ApiService {
  // API base URL
  // Web: Direct connection to API server on port 8000
  // Android/iOS: Must be an absolute URL
  //
  // You can override with:
  //   flutter run --dart-define=API_BASE_URL=http://<YOUR_PC_IP>:8000/api
  static String get baseUrl {
    // Check for environment override first
    const envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
    if (envUrl.isNotEmpty) {
      if (kReleaseMode && envUrl.startsWith('http://')) {
        throw StateError('API_BASE_URL must use HTTPS in release builds.');
      }
      return envUrl;
    }

    if (kReleaseMode) {
      throw StateError('API_BASE_URL is required for release builds.');
    }
    
    if (kIsWeb) {
      // Web: Direct connection to API server
      // In development, API runs on port 8000
      return 'http://localhost:8000/api';
    }

    // Native (Android emulator): use loopback address
    // For real device, use --dart-define=API_BASE_URL=http://<PC_IP>:8000/api
    return 'http://10.0.2.2:8000/api';
  }

  // ── JWT Token Management ──

  static Future<Map<String, String>> _getHeaders() async {
    String? token = await SecureStorageService.getAccessToken();
    if (token == null) {
      // Legacy migration path from SharedPreferences.
      final prefs = await SharedPreferences.getInstance();
      token = prefs.getString('auth_token');
      if (token != null) {
        await SecureStorageService.saveAccessToken(token);
        await prefs.remove('auth_token');
      }
    }
    
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Try to refresh the access token using the stored refresh token.
  /// Returns true if refresh was successful.
  static Future<bool> _refreshToken() async {
    try {
      String? refreshToken = await SecureStorageService.getRefreshToken();
      if (refreshToken == null) {
        // Legacy migration path from SharedPreferences.
        final prefs = await SharedPreferences.getInstance();
        refreshToken = prefs.getString('refresh_token');
        if (refreshToken != null) {
          await SecureStorageService.saveRefreshToken(refreshToken);
          await prefs.remove('refresh_token');
        }
      }
      if (refreshToken == null) return false;

      final response = await http.post(
        Uri.parse('$baseUrl/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'refresh_token': refreshToken}),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success'] == true && data['access_token'] != null) {
          await SecureStorageService.saveAccessToken(data['access_token']);
          if (data['refresh_token'] != null) {
            await SecureStorageService.saveRefreshToken(data['refresh_token']);
          }
          debugPrint('🔄 Token refreshed successfully');
          return true;
        }
      }

      // Refresh failed — clear tokens
      debugPrint('⚠️ Token refresh failed: ${response.statusCode}');
      return false;
    } catch (e) {
      debugPrint('❌ Token refresh error: $e');
      return false;
    }
  }

  /// Make an authenticated GET request. Automatically retries with token refresh on 401.
  static Future<http.Response> _authGet(String url) async {
    var headers = await _getHeaders();
    var response = await http.get(Uri.parse(url), headers: headers);

    // If 401 (expired token), try refresh and retry once
    if (response.statusCode == 401) {
      final refreshed = await _refreshToken();
      if (refreshed) {
        headers = await _getHeaders();
        response = await http.get(Uri.parse(url), headers: headers);
      }
    }
    if (response.statusCode == 401) {
      throw AuthSessionExpiredException();
    }
    return response;
  }

  /// Make an authenticated POST request. Automatically retries with token refresh on 401.
  static Future<http.Response> _authPost(String url, {Object? body}) async {
    var headers = await _getHeaders();
    var response = await http.post(Uri.parse(url), headers: headers, body: body is String ? body : json.encode(body));

    if (response.statusCode == 401) {
      final refreshed = await _refreshToken();
      if (refreshed) {
        headers = await _getHeaders();
        response = await http.post(Uri.parse(url), headers: headers, body: body is String ? body : json.encode(body));
      }
    }
    if (response.statusCode == 401) {
      throw AuthSessionExpiredException();
    }
    return response;
  }

  /// Make an authenticated PUT request. Automatically retries with token refresh on 401.
  static Future<http.Response> _authPut(String url, {Object? body}) async {
    var headers = await _getHeaders();
    var response = await http.put(Uri.parse(url), headers: headers, body: body is String ? body : json.encode(body));

    if (response.statusCode == 401) {
      final refreshed = await _refreshToken();
      if (refreshed) {
        headers = await _getHeaders();
        response = await http.put(Uri.parse(url), headers: headers, body: body is String ? body : json.encode(body));
      }
    }
    if (response.statusCode == 401) {
      throw AuthSessionExpiredException();
    }
    return response;
  }

  /// Make an authenticated DELETE request. Automatically retries with token refresh on 401.
  static Future<http.Response> _authDelete(String url) async {
    var headers = await _getHeaders();
    var response = await http.delete(Uri.parse(url), headers: headers);

    if (response.statusCode == 401) {
      final refreshed = await _refreshToken();
      if (refreshed) {
        headers = await _getHeaders();
        response = await http.delete(Uri.parse(url), headers: headers);
      }
    }
    if (response.statusCode == 401) {
      throw AuthSessionExpiredException();
    }
    return response;
  }

  // ── Charger API ──

  static Future<List<Map<String, dynamic>>> getNearbyChargers(
    double latitude,
    double longitude,
  ) async {
    try {
      final response = await _authGet('$baseUrl/chargers');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        // Ensure all charger data has required fields with defaults
        return data.map<Map<String, dynamic>>((charger) {
          return {
            'id': charger['id'] ?? 0,
            'charge_point_id': charger['charge_point_id']?.toString() ?? '',
            'availability': charger['availability']?.toString() ?? 'unknown',
            'status': charger['status']?.toString() ?? 'unknown',
            'vendor': charger['vendor']?.toString() ?? '',
            'model': charger['model']?.toString() ?? '',
            'firmware_version': charger['firmware_version']?.toString() ?? '',
            // Physical / location info
            'location': charger['location']?.toString(),
            'latitude': charger['latitude'],
            'longitude': charger['longitude'],
            'connector_type': charger['connector_type']?.toString(),
            'max_power_kw': charger['max_power_kw'],
            'number_of_connectors': charger['number_of_connectors'] ?? 1,
            // Pricing
            'price_per_kwh': charger['price_per_kwh'],
            // Active transaction
            'active_transaction_id': charger['active_transaction_id'],
          };
        }).toList();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('Error loading chargers: $e');
      return [];
    }
  }

  static Future<Map<String, dynamic>?> getActiveSession() async {
    try {
      final response = await _authGet('$baseUrl/sessions?limit=1');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        // Find active session
        for (var session in data) {
          if (session['status'] == 'active' || session['status'] == 'pending') {
            return session as Map<String, dynamic>;
          }
        }
      }
      return null;
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      return null;
    }
  }

  static Future<List<Map<String, dynamic>>> getChargingHistory() async {
    try {
      final response = await _authGet('$baseUrl/sessions');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      return [];
    }
  }

  static Future<Map<String, dynamic>> startCharging(
    String chargerId,
    int connectorId, {
    String? idTag,
  }) async {
    try {
      final url = '$baseUrl/charging/start';
      final body = json.encode({
          'charger_id': chargerId,
          'connector_id': connectorId,
        'id_tag': idTag ?? 'APP_USER',
      });
      
      debugPrint('📤 POST $url');
      debugPrint('📤 Body: $body');
      
      final response = await _authPost(url, body: body);

      debugPrint('📥 Response status: ${response.statusCode}');
      if (response.statusCode == 200) {
        final result = json.decode(response.body);
        return result;
      } else {
        debugPrint('❌ HTTP Error: ${response.statusCode}');
        return {
          'success': false,
          'message': 'Failed to start charging: HTTP ${response.statusCode}',
        };
      }
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Exception: $e');
      return {
        'success': false,
        'message': e.toString(),
      };
    }
  }

  static Future<Map<String, dynamic>> stopCharging(int transactionId) async {
    try {
      final response = await _authPost(
        '$baseUrl/charging/stop',
        body: json.encode({'transaction_id': transactionId}),
      );

      if (response.statusCode == 200) {
        final result = json.decode(response.body);
        return result;
      }
      return {
        'success': false,
        'message': 'Failed to stop charging',
      };
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      return {
        'success': false,
        'message': e.toString(),
      };
    }
  }

  static Future<List<Map<String, dynamic>>> getPaymentMethods() async {
    try {
      final response = await _authGet('$baseUrl/payment/methods');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      return [];
    }
  }

  static Future<List<Map<String, dynamic>>> getTransactions() async {
    try {
      final response = await _authGet('$baseUrl/payment/transactions');

      if (response.statusCode == 200) {
        final decoded = json.decode(response.body);
        // API returns {"success": true, "transactions": [...]}
        if (decoded is Map && decoded['transactions'] is List) {
          return List<Map<String, dynamic>>.from(decoded['transactions']);
        }
        // Fallback: if API returns a raw list
        if (decoded is List) {
          return decoded.cast<Map<String, dynamic>>();
        }
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('Error loading transactions: $e');
      return [];
    }
  }

  static Future<Map<String, dynamic>> processPayment({
    required double amount,
    required String paymentMethodId,
    required String chargerId,
  }) async {
    try {
      final response = await _authPost(
        '$baseUrl/payment/process',
        body: json.encode({
          'amount': amount,
          'payment_method_id': paymentMethodId,
          'charger_id': chargerId,
        }),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return {'success': false};
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== OTP VERIFICATION API ====================

  /// Send OTP verification code to email (no auth required)
  static Future<Map<String, dynamic>> sendOTP({required String email}) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/send-otp'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'email': email}),
      );

      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Send OTP error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Verify OTP code (no auth required)
  static Future<Map<String, dynamic>> verifyOTP({
    required String email,
    required String otpCode,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/verify-otp'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'otp_code': otpCode,
        }),
      );

      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Verify OTP error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  // ==================== FORGOT / RESET PASSWORD ====================

  /// Send OTP for password reset (no auth required)
  static Future<Map<String, dynamic>> forgotPassword({required String email}) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/forgot-password'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'email': email}),
      );
      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Forgot password error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Reset password using OTP (no auth required)
  static Future<Map<String, dynamic>> resetPassword({
    required String email,
    required String otpCode,
    required String newPassword,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/reset-password'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'otp_code': otpCode,
          'new_password': newPassword,
        }),
      );
      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Reset password error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Change password for authenticated user
  static Future<Map<String, dynamic>> changePassword(
    int userId, {
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      final response = await _authPut(
        '$baseUrl/users/$userId/change-password',
        body: json.encode({
          'current_password': currentPassword,
          'new_password': newPassword,
        }),
      );
      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Change password error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  // ==================== USER API ====================

  /// Register a new user (legacy — without OTP, no auth required)
  static Future<Map<String, dynamic>> registerUser({
    required String email,
    required String password,
    String name = '',
    String? phone,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/users/register'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'password': password,
          'name': name,
          'phone': phone,
        }),
      );

      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Register error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Register a new user with OTP verification (no auth required)
  static Future<Map<String, dynamic>> registerUserWithOTP({
    required String email,
    required String password,
    required String otpCode,
    String name = '',
    String? phone,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/users/register-with-otp'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'password': password,
          'name': name,
          'phone': phone,
          'otp_code': otpCode,
        }),
      );

      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Register (OTP) error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Login user (no auth required — returns JWT tokens)
  static Future<Map<String, dynamic>> loginUser({
    required String email,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/users/login'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'password': password,
        }),
      );

      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Login error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Get user profile by ID (authenticated)
  static Future<Map<String, dynamic>> getUserProfile(int userId) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId');

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return {'success': false, 'message': 'Failed to get profile'};
    } on AuthSessionExpiredException {
      return {'success': false, 'message': 'Session expired', 'auth_error': true};
    } catch (e) {
      debugPrint('❌ Get profile error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Update user profile (authenticated)
  static Future<Map<String, dynamic>> updateUserProfile(
    int userId, {
    String? name,
    String? phone,
    String? avatarUrl,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (name != null) body['name'] = name;
      if (phone != null) body['phone'] = phone;
      if (avatarUrl != null) body['avatar_url'] = avatarUrl;

      final response = await _authPut(
        '$baseUrl/users/$userId',
        body: json.encode(body),
      );

      return json.decode(response.body);
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Update profile error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  // ==================== WALLET API ====================

  /// Get user wallet (authenticated)
  static Future<Map<String, dynamic>> getWallet(int userId) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId/wallet');

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return {'balance': 0.0, 'points': 0, 'currency': 'MYR'};
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get wallet error: $e');
      return {'balance': 0.0, 'points': 0, 'currency': 'MYR'};
    }
  }

  /// Top up wallet (legacy — still works for backward compat, authenticated)
  static Future<Map<String, dynamic>> topUpWallet(
    int userId, {
    required double amount,
    String paymentMethod = 'manual',
  }) async {
    try {
      final response = await _authPost(
        '$baseUrl/users/$userId/wallet/topup',
        body: json.encode({
          'amount': amount,
          'payment_method': paymentMethod,
        }),
      );

      return json.decode(response.body);
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Top up error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Create top-up via payment gateway (new flow, authenticated)
  /// Returns payment_url for gateway redirect, or direct success for manual
  static Future<Map<String, dynamic>> createPaymentTopUp(
    int userId, {
    required double amount,
    String? paymentMethod,
    String? gatewayName,
  }) async {
    try {
      final body = <String, dynamic>{
        'user_id': userId,
        'amount': amount,
      };
      if (paymentMethod != null) body['payment_method'] = paymentMethod;
      if (gatewayName != null) body['gateway_name'] = gatewayName;

      final response = await _authPost(
        '$baseUrl/payment/topup',
        body: json.encode(body),
      );

      return json.decode(response.body);
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Payment top-up error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Check payment transaction status (authenticated)
  static Future<Map<String, dynamic>> checkPaymentStatus(String transactionRef) async {
    try {
      final response = await _authGet('$baseUrl/payment/transactions/$transactionRef');
      return json.decode(response.body);
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Check payment status error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Get user's payment history (authenticated)
  static Future<List<Map<String, dynamic>>> getPaymentTransactions(int userId) async {
    try {
      final response = await _authGet('$baseUrl/payment/transactions?user_id=$userId&limit=50');
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['transactions'] ?? []);
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get payment transactions error: $e');
      return [];
    }
  }

  /// Get wallet transactions (authenticated)
  static Future<List<Map<String, dynamic>>> getWalletTransactions(
    int userId, {
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final response = await _authGet(
        '$baseUrl/users/$userId/wallet/transactions?limit=$limit&offset=$offset',
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get transactions error: $e');
      return [];
    }
  }

  // ==================== REWARDS API ====================

  /// Get rewards catalog (public)
  static Future<List<Map<String, dynamic>>> getRewardsCatalog() async {
    try {
      final response = await _authGet('$baseUrl/rewards/catalog');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get rewards catalog error: $e');
      return [];
    }
  }

  /// Redeem a reward (authenticated)
  static Future<Map<String, dynamic>> redeemReward(
    int userId, {
    required String rewardType,
    required int pointsCost,
  }) async {
    try {
      final response = await _authPost(
        '$baseUrl/users/$userId/rewards/redeem',
        body: json.encode({
          'reward_type': rewardType,
          'points_cost': pointsCost,
        }),
      );

      return json.decode(response.body);
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Redeem reward error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Get reward redemption history (authenticated)
  static Future<List<Map<String, dynamic>>> getRewardHistory(
    int userId, {
    int limit = 50,
  }) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId/rewards/history?limit=$limit');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get reward history error: $e');
      return [];
    }
  }

  // ==================== SUPPORT TICKET ====================

  /// Create a support ticket via ChargingPlatform
  static Future<Map<String, dynamic>> createSupportTicket({
    required String email,
    required String name,
    required String category,
    required String subject,
    required String description,
  }) async {
    try {
      // Use ChargingPlatform API directly (same base as main API)
      final ticketUrl = '${baseUrl.replaceAll('/api', '')}/api/tickets';
      final response = await http.post(
        Uri.parse(ticketUrl),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_email': email,
          'user_name': name,
          'category': category,
          'subject': subject,
          'description': description,
          'priority': 'medium',
          'source': 'app_contact_form',
        }),
      );
      return json.decode(response.body);
    } catch (e) {
      debugPrint('❌ Create ticket error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  // ==================== VEHICLE API ====================

  /// Get user vehicles (authenticated)
  static Future<List<Map<String, dynamic>>> getUserVehicles(int userId) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId/vehicles');

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Get vehicles error: $e');
      return [];
    }
  }

  /// Add vehicle (authenticated)
  static Future<Map<String, dynamic>> addVehicle(
    int userId,
    Map<String, dynamic> vehicleData,
  ) async {
    try {
      final response = await _authPost(
        '$baseUrl/users/$userId/vehicles',
        body: json.encode(vehicleData),
      );

      if (response.statusCode == 200) {
        return {'success': true, 'vehicle': json.decode(response.body)};
      }
      return {'success': false, 'message': 'Failed to add vehicle'};
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Add vehicle error: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  /// Delete vehicle (authenticated)
  static Future<bool> deleteVehicle(int userId, int vehicleId) async {
    try {
      final response = await _authDelete('$baseUrl/users/$userId/vehicles/$vehicleId');

      return response.statusCode == 200;
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('❌ Delete vehicle error: $e');
      return false;
    }
  }

  // ==================== REVIEWS ====================

  static Future<List<Map<String, dynamic>>> getChargerReviews(String chargePointId) async {
    try {
      final response = await _authGet('$baseUrl/chargers/$chargePointId/reviews');
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(json.decode(response.body));
      }
      return [];
    } catch (e) {
      debugPrint('❌ Get reviews error: $e');
      return [];
    }
  }

  static Future<bool> submitReview(String chargePointId, int rating, String? comment) async {
    try {
      final response = await _authPost(
        '$baseUrl/chargers/$chargePointId/reviews',
        body: json.encode({'rating': rating, 'comment': comment}),
      );
      return response.statusCode == 201;
    } catch (e) {
      debugPrint('❌ Submit review error: $e');
      return false;
    }
  }

  static Future<Map<String, dynamic>> getChargerRating(String chargePointId) async {
    try {
      final response = await _authGet('$baseUrl/chargers/$chargePointId/rating');
      if (response.statusCode == 200) return json.decode(response.body);
      return {'average': null, 'count': 0};
    } catch (e) {
      return {'average': null, 'count': 0};
    }
  }

  // ==================== ISSUE REPORT ====================

  static Future<bool> reportChargerIssue(String chargePointId, String issueType, String? description) async {
    try {
      final response = await _authPost(
        '$baseUrl/chargers/$chargePointId/report',
        body: json.encode({'issue_type': issueType, 'description': description}),
      );
      return response.statusCode == 201;
    } catch (e) {
      debugPrint('❌ Report issue error: $e');
      return false;
    }
  }

  // ==================== COST ESTIMATE ====================

  static Future<Map<String, dynamic>> getCostEstimate(
    String chargePointId, {
    double batteryKwh = 60.0,
    double currentSoc = 20.0,
    double targetSoc  = 80.0,
  }) async {
    try {
      final response = await _authGet(
        '$baseUrl/chargers/$chargePointId/cost-estimate'
        '?battery_kwh=$batteryKwh&current_soc=$currentSoc&target_soc=$targetSoc',
      );
      if (response.statusCode == 200) return json.decode(response.body);
      return {};
    } catch (e) {
      debugPrint('❌ Cost estimate error: $e');
      return {};
    }
  }

  // ==================== kW GRAPH ====================

  static Future<List<Map<String, dynamic>>> getSessionMeterValues(int transactionId) async {
    try {
      final response = await _authGet('$baseUrl/sessions/$transactionId/meter-values?limit=60');
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(json.decode(response.body));
      }
      return [];
    } catch (e) {
      debugPrint('❌ Meter values error: $e');
      return [];
    }
  }

  // ==================== CARBON FOOTPRINT ====================

  static Future<Map<String, dynamic>> getCarbonFootprint(int userId) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId/carbon-footprint');
      if (response.statusCode == 200) return json.decode(response.body);
      return {};
    } catch (e) {
      debugPrint('❌ Carbon footprint error: $e');
      return {};
    }
  }

  // ==================== BOOKING ====================

  static Future<List<dynamic>> getAvailableSlots(String chargePointId, String date) async {
    try {
      final response = await _authGet('$baseUrl/chargers/$chargePointId/available-slots?date=$date');
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return data['slots'] ?? [];
      }
      return [];
    } catch (e) {
      debugPrint('❌ Get slots error: $e');
      return [];
    }
  }

  static Future<Map<String, dynamic>> createBooking(
    String chargePointId, {
    required String startTime,
    required int durationMin,
    int connectorId = 1,
    String? notes,
  }) async {
    try {
      final response = await _authPost(
        '$baseUrl/chargers/$chargePointId/book',
        body: json.encode({
          'start_time':   startTime,
          'duration_min': durationMin,
          'connector_id': connectorId,
          'notes':        notes,
        }),
      );
      if (response.statusCode == 201) return json.decode(response.body);
      final err = json.decode(response.body);
      return {'error': err['detail'] ?? 'Booking failed'};
    } catch (e) {
      return {'error': e.toString()};
    }
  }

  static Future<List<Map<String, dynamic>>> getUserBookings(int userId) async {
    try {
      final response = await _authGet('$baseUrl/users/$userId/bookings');
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(json.decode(response.body));
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  static Future<bool> cancelBooking(int bookingId) async {
    try {
      final response = await _authDelete('$baseUrl/bookings/$bookingId');
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // ── Charger Configuration ──────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getChargerConfiguration(String chargerId) async {
    try {
      final response = await _authGet('$baseUrl/chargers/$chargerId/configuration');
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final List<dynamic> keys = data['configuration'] ?? [];
        return keys.cast<Map<String, dynamic>>();
      }
      return [];
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('Error getChargerConfiguration: $e');
      return [];
    }
  }

  static Future<Map<String, dynamic>> changeChargerConfiguration(
      String chargerId, String key, String value) async {
    try {
      final response = await _authPost(
        '$baseUrl/chargers/$chargerId/configuration/change',
        body: json.encode({'key': key, 'value': value}),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return {'success': false, 'message': 'HTTP ${response.statusCode}'};
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('Error changeChargerConfiguration: $e');
      return {'success': false, 'message': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> changeChargerAvailability(
      String chargerId, String type) async {
    try {
      final response = await _authPost(
        '$baseUrl/ocpp/$chargerId/change-availability',
        body: json.encode({'connector_id': 0, 'type': type}),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return {'success': false, 'message': 'HTTP ${response.statusCode}'};
    } on AuthSessionExpiredException {
      rethrow;
    } catch (e) {
      debugPrint('Error changeChargerAvailability: $e');
      return {'success': false, 'message': e.toString()};
    }
  }
}
