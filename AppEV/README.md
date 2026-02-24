# EV Charging Mobile App (Flutter)

Mobile application for EV charging platform with payment integration.

## Current Status

Recently updated and verified:
- `getTransactions()` now supports both response formats:
  - raw list
  - object wrapper: `{"transactions": [...]}`
- `LiveChargingScreen.dispose()` uses a stored provider reference to avoid unsafe `context` access
- EV illustration asset `assets/ev_city_night.jpg` is confirmed and included in `pubspec.yaml`

## Features

- ✅ **Profile** - User profile management
- ✅ **Find Nearby Charger** - Map view with nearby charging stations
- ✅ **Live Charging** - Real-time charging session monitoring
- ✅ **Payment** - Payment methods and transaction history
- ✅ **Rewards** - Points and rewards system
- ✅ **Charging History** - Past charging sessions
- ✅ **Notifications** - Push notifications for charging updates

## Setup

1. **Install Flutter:**
   ```bash
   # Download Flutter from https://flutter.dev
   # Add Flutter to PATH
   ```

2. **Install Dependencies:**
   ```bash
   cd C:\AppEV
   flutter pub get
   ```

3. **Configure API URL:**
   - Update `lib/services/api_service.dart`
   - Change `baseUrl` to match your server address
   - For Android emulator: use `http://10.0.2.2:8000/api`
   - For physical device: use your computer's IP address

4. **Run the App:**
   ```bash
   flutter run
   ```

## Android Setup

1. **Enable Developer Options** on your Android device
2. **Enable USB Debugging**
3. Connect device via USB
4. Run `flutter devices` to verify connection
5. Run `flutter run` to install and launch app

## Project Structure

```
lib/
├── main.dart                 # App entry point
├── screens/                  # All app screens
│   ├── home_screen.dart
│   ├── find_charger_screen.dart
│   ├── live_charging_screen.dart
│   ├── profile_screen.dart
│   ├── payment_screen.dart
│   ├── rewards_screen.dart
│   └── history_screen.dart
├── providers/                # State management
│   ├── auth_provider.dart
│   ├── charger_provider.dart
│   ├── session_provider.dart
│   └── payment_provider.dart
└── services/                 # API services
    └── api_service.dart
```

## API Integration

The app connects to the charging platform API at `http://localhost:8000/api`.

Required API endpoints:
- `GET /api/chargers` - List all chargers
- `GET /api/sessions` - Get charging sessions
- `POST /api/charging/start` - Start charging
- `POST /api/charging/stop` - Stop charging
- `GET /api/payment/methods` - Get payment methods
- `POST /api/payment/process` - Process payment

## Troubleshooting

- **UI changes not visible on web**:
  - Hard refresh with `Ctrl + Shift + R`
  - If needed, run `flutter clean` and restart `flutter run -d chrome`
- **Image/illustration missing**:
  - Verify asset path in `pubspec.yaml`
  - Perform a full Flutter restart after asset changes
- **API errors on device**:
  - Provide `--dart-define=API_BASE_URL=http://<YOUR_PC_IP>:8000/api`

## Build APK

```bash
flutter build apk --release
```

The APK will be in `build/app/outputs/flutter-apk/app-release.apk`

