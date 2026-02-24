class User {
  final int id;
  final String email;
  final String? phone;
  final String name;
  final String? avatarUrl;
  final bool isVerified;
  final DateTime createdAt;
  final double walletBalance;
  final int walletPoints;

  User({
    required this.id,
    required this.email,
    this.phone,
    required this.name,
    this.avatarUrl,
    required this.isVerified,
    required this.createdAt,
    this.walletBalance = 0.0,
    this.walletPoints = 0,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? 0,
      email: json['email'] ?? '',
      phone: json['phone'],
      name: json['name'] ?? '',
      avatarUrl: json['avatar_url'],
      isVerified: json['is_verified'] ?? false,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
      walletBalance: (json['wallet_balance'] ?? 0.0).toDouble(),
      walletPoints: json['wallet_points'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'phone': phone,
      'name': name,
      'avatar_url': avatarUrl,
      'is_verified': isVerified,
      'created_at': createdAt.toIso8601String(),
      'wallet_balance': walletBalance,
      'wallet_points': walletPoints,
    };
  }

  User copyWith({
    int? id,
    String? email,
    String? phone,
    String? name,
    String? avatarUrl,
    bool? isVerified,
    DateTime? createdAt,
    double? walletBalance,
    int? walletPoints,
  }) {
    return User(
      id: id ?? this.id,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      name: name ?? this.name,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      isVerified: isVerified ?? this.isVerified,
      createdAt: createdAt ?? this.createdAt,
      walletBalance: walletBalance ?? this.walletBalance,
      walletPoints: walletPoints ?? this.walletPoints,
    );
  }
}


class Wallet {
  final double balance;
  final int points;
  final String currency;

  Wallet({
    required this.balance,
    required this.points,
    this.currency = 'MYR',
  });

  factory Wallet.fromJson(Map<String, dynamic> json) {
    return Wallet(
      balance: (json['balance'] ?? 0.0).toDouble(),
      points: json['points'] ?? 0,
      currency: json['currency'] ?? 'MYR',
    );
  }
}


class WalletTransaction {
  final int id;
  final String transactionType;
  final double amount;
  final double balanceBefore;
  final double balanceAfter;
  final int pointsAmount;
  final String? description;
  final String status;
  final DateTime createdAt;

  WalletTransaction({
    required this.id,
    required this.transactionType,
    required this.amount,
    required this.balanceBefore,
    required this.balanceAfter,
    this.pointsAmount = 0,
    this.description,
    required this.status,
    required this.createdAt,
  });

  factory WalletTransaction.fromJson(Map<String, dynamic> json) {
    return WalletTransaction(
      id: json['id'] ?? 0,
      transactionType: json['transaction_type'] ?? '',
      amount: (json['amount'] ?? 0.0).toDouble(),
      balanceBefore: (json['balance_before'] ?? 0.0).toDouble(),
      balanceAfter: (json['balance_after'] ?? 0.0).toDouble(),
      pointsAmount: json['points_amount'] ?? 0,
      description: json['description'],
      status: json['status'] ?? 'unknown',
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  // Helper to get display icon based on transaction type
  String get displayIcon {
    switch (transactionType) {
      case 'topup':
        return '💰';
      case 'charge_payment':
        return '⚡';
      case 'refund':
        return '↩️';
      case 'points_earned':
        return '🌟';
      case 'points_redeemed':
        return '🎁';
      default:
        return '📝';
    }
  }

  // Helper to get display title
  String get displayTitle {
    switch (transactionType) {
      case 'topup':
        return 'Top Up';
      case 'charge_payment':
        return 'Charging Payment';
      case 'refund':
        return 'Refund';
      case 'points_earned':
        return 'Points Earned';
      case 'points_redeemed':
        return 'Points Redeemed';
      default:
        return 'Transaction';
    }
  }

  // Check if this is a credit (positive) or debit (negative) transaction
  bool get isCredit => amount > 0;
}


class Vehicle {
  final int id;
  final String? plateNumber;
  final String? brand;
  final String? model;
  final int? year;
  final double? batteryCapacityKwh;
  final String? connectorType;
  final bool isPrimary;
  final DateTime createdAt;

  Vehicle({
    required this.id,
    this.plateNumber,
    this.brand,
    this.model,
    this.year,
    this.batteryCapacityKwh,
    this.connectorType,
    this.isPrimary = false,
    required this.createdAt,
  });

  factory Vehicle.fromJson(Map<String, dynamic> json) {
    return Vehicle(
      id: json['id'] ?? 0,
      plateNumber: json['plate_number'],
      brand: json['brand'],
      model: json['model'],
      year: json['year'],
      batteryCapacityKwh: json['battery_capacity_kwh']?.toDouble(),
      connectorType: json['connector_type'],
      isPrimary: json['is_primary'] ?? false,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'plate_number': plateNumber,
      'brand': brand,
      'model': model,
      'year': year,
      'battery_capacity_kwh': batteryCapacityKwh,
      'connector_type': connectorType,
      'is_primary': isPrimary,
    };
  }

  // Display name helper
  String get displayName {
    if (brand != null && model != null) {
      return '$brand $model';
    } else if (brand != null) {
      return brand!;
    } else if (plateNumber != null) {
      return plateNumber!;
    }
    return 'My Vehicle';
  }
}
