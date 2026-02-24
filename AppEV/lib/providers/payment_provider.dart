import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

class PaymentProvider with ChangeNotifier {
  List<Map<String, dynamic>> _paymentMethods = [];
  List<Map<String, dynamic>> _transactions = [];
  bool _isLoading = false;

  List<Map<String, dynamic>> get paymentMethods => _paymentMethods;
  List<Map<String, dynamic>> get transactions => _transactions;
  bool get isLoading => _isLoading;

  Future<void> loadPaymentMethods() async {
    _isLoading = true;
    notifyListeners();

    try {
      final methods = await ApiService.getPaymentMethods();
      _paymentMethods = methods;
    } catch (e) {
      debugPrint('Error loading payment methods: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadTransactions() async {
    _isLoading = true;
    notifyListeners();

    try {
      final transactions = await ApiService.getTransactions();
      _transactions = transactions;
    } catch (e) {
      debugPrint('Error loading transactions: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> processPayment({
    required double amount,
    required String paymentMethodId,
    required String chargerId,
  }) async {
    try {
      final result = await ApiService.processPayment(
        amount: amount,
        paymentMethodId: paymentMethodId,
        chargerId: chargerId,
      );
      return result['success'] ?? false;
    } catch (e) {
      debugPrint('Error processing payment: $e');
      return false;
    }
  }
}

