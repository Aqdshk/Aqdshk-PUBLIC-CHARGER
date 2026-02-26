import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../services/secure_storage_service.dart';
import '../models/user.dart';

class AuthProvider with ChangeNotifier {
  User? _currentUser;
  bool _isLoading = false;
  String? _error;

  User? get currentUser => _currentUser;
  bool get isLoading => _isLoading;
  bool get isAuthenticated => _currentUser != null;
  String? get error => _error;

  // For backward compatibility with existing code that uses Map
  Map<String, dynamic>? get currentUserMap => _currentUser?.toJson();

  AuthProvider() {
    _loadUser();
  }

  /// Save JWT tokens to secure storage
  Future<void> _saveTokens(Map<String, dynamic> response) async {
    // Save access token (use 'access_token' first, fall back to 'token')
    final accessToken = response['access_token'] ?? response['token'];
    if (accessToken != null) {
      await SecureStorageService.saveAccessToken(accessToken);
    }

    // Save refresh token
    if (response['refresh_token'] != null) {
      await SecureStorageService.saveRefreshToken(response['refresh_token']);
    }
  }

  /// Clear all auth-related stored data
  Future<void> _clearAuthData() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_id');
    await prefs.remove('auth_token');
    await prefs.remove('refresh_token');
    await SecureStorageService.clearAuthTokens();
  }

  Future<void> _loadUser() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    
    if (userId != null) {
      _isLoading = true;
      notifyListeners();
      
      try {
        final response = await ApiService.getUserProfile(userId);
        if (response['success'] == true && response['user'] != null) {
          _currentUser = User.fromJson(response['user']);
        } else if (response['auth_error'] == true) {
          // Token expired and refresh also failed — force logout
          debugPrint('⚠️ Auth expired, clearing stored data');
          await _clearAuthData();
        } else {
          // Some other error, clear stored data
          await _clearAuthData();
        }
      } catch (e) {
        debugPrint('Error loading user: $e');
      }
      
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Send OTP to email for verification
  Future<bool> sendOTP({required String email}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.sendOTP(email: email);

      _isLoading = false;
      if (response['success'] == true) {
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Failed to send OTP';
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Verify OTP code
  Future<bool> verifyOTP({required String email, required String otpCode}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.verifyOTP(email: email, otpCode: otpCode);

      _isLoading = false;
      if (response['success'] == true && response['verified'] == true) {
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Verification failed';
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register a new user (legacy — no OTP)
  Future<bool> register({
    required String email,
    required String password,
    String name = '',
    String? phone,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.registerUser(
        email: email,
        password: password,
        name: name,
        phone: phone,
      );

      if (response['success'] == true && response['user'] != null) {
        _currentUser = User.fromJson(response['user']);
        
        // Save user ID and JWT tokens
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('user_id', _currentUser!.id);
        await _saveTokens(response);
      
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Registration failed';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register a new user with OTP verification
  Future<bool> registerWithOTP({
    required String email,
    required String password,
    required String otpCode,
    String name = '',
    String? phone,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.registerUserWithOTP(
        email: email,
        password: password,
        otpCode: otpCode,
        name: name,
        phone: phone,
      );

      if (response['success'] == true && response['user'] != null) {
        _currentUser = User.fromJson(response['user']);
        
        // Save user ID and JWT tokens
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('user_id', _currentUser!.id);
        await _saveTokens(response);
      
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Registration failed';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Login user — stores JWT tokens
  Future<bool> login({
    required String email,
    required String password,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.loginUser(
        email: email,
        password: password,
      );

      if (response['success'] == true && response['user'] != null) {
        _currentUser = User.fromJson(response['user']);
        
        // Save user ID and JWT tokens
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('user_id', _currentUser!.id);
        await _saveTokens(response);
        
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Login failed';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout user — clear all tokens
  Future<void> logout() async {
    _currentUser = null;
    _error = null;
    
    await _clearAuthData();
    
    notifyListeners();
  }

  /// Update user profile
  Future<bool> updateProfile({
    String? name,
    String? phone,
    String? avatarUrl,
  }) async {
    if (_currentUser == null) return false;

    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiService.updateUserProfile(
        _currentUser!.id,
        name: name,
        phone: phone,
        avatarUrl: avatarUrl,
      );

      if (response['success'] == true && response['user'] != null) {
        _currentUser = User.fromJson(response['user']);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Update failed';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Refresh user profile from server
  Future<void> refreshProfile() async {
    if (_currentUser == null) return;

    try {
      final response = await ApiService.getUserProfile(_currentUser!.id);
      if (response['success'] == true && response['user'] != null) {
        _currentUser = User.fromJson(response['user']);
        notifyListeners();
      } else if (response['auth_error'] == true) {
        // Session expired, force logout
        await logout();
      }
    } catch (e) {
      debugPrint('Error refreshing profile: $e');
    }
  }

  /// Clear error message
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
