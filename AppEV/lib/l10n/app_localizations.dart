import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ms.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ms')
  ];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'PlagSini EV'**
  String get appName;

  /// No description provided for @home.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// No description provided for @findCharger.
  ///
  /// In en, this message translates to:
  /// **'Find Charger'**
  String get findCharger;

  /// No description provided for @scan.
  ///
  /// In en, this message translates to:
  /// **'Scan'**
  String get scan;

  /// No description provided for @rewards.
  ///
  /// In en, this message translates to:
  /// **'Rewards'**
  String get rewards;

  /// No description provided for @profile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// No description provided for @startCharging.
  ///
  /// In en, this message translates to:
  /// **'Start Charging'**
  String get startCharging;

  /// No description provided for @stopCharging.
  ///
  /// In en, this message translates to:
  /// **'Stop Charging'**
  String get stopCharging;

  /// No description provided for @booking.
  ///
  /// In en, this message translates to:
  /// **'Book Slot'**
  String get booking;

  /// No description provided for @bookingTitle.
  ///
  /// In en, this message translates to:
  /// **'Reserve Charger'**
  String get bookingTitle;

  /// No description provided for @selectDate.
  ///
  /// In en, this message translates to:
  /// **'Select Date'**
  String get selectDate;

  /// No description provided for @selectTime.
  ///
  /// In en, this message translates to:
  /// **'Select Time'**
  String get selectTime;

  /// No description provided for @duration.
  ///
  /// In en, this message translates to:
  /// **'Duration'**
  String get duration;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @available.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get available;

  /// No description provided for @unavailable.
  ///
  /// In en, this message translates to:
  /// **'Unavailable'**
  String get unavailable;

  /// No description provided for @charging.
  ///
  /// In en, this message translates to:
  /// **'Charging'**
  String get charging;

  /// No description provided for @offline.
  ///
  /// In en, this message translates to:
  /// **'Offline'**
  String get offline;

  /// No description provided for @rateCharger.
  ///
  /// In en, this message translates to:
  /// **'Rate This Charger'**
  String get rateCharger;

  /// No description provided for @submitReview.
  ///
  /// In en, this message translates to:
  /// **'Submit Review'**
  String get submitReview;

  /// No description provided for @yourComment.
  ///
  /// In en, this message translates to:
  /// **'Your comment (optional)'**
  String get yourComment;

  /// No description provided for @reportIssue.
  ///
  /// In en, this message translates to:
  /// **'Report Issue'**
  String get reportIssue;

  /// No description provided for @issueType.
  ///
  /// In en, this message translates to:
  /// **'Issue Type'**
  String get issueType;

  /// No description provided for @brokenCable.
  ///
  /// In en, this message translates to:
  /// **'Broken Cable'**
  String get brokenCable;

  /// No description provided for @noPower.
  ///
  /// In en, this message translates to:
  /// **'No Power'**
  String get noPower;

  /// No description provided for @paymentFailed.
  ///
  /// In en, this message translates to:
  /// **'Payment Failed'**
  String get paymentFailed;

  /// No description provided for @screenIssue.
  ///
  /// In en, this message translates to:
  /// **'Screen Issue'**
  String get screenIssue;

  /// No description provided for @other.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get other;

  /// No description provided for @description.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get description;

  /// No description provided for @costEstimate.
  ///
  /// In en, this message translates to:
  /// **'Estimated Cost'**
  String get costEstimate;

  /// No description provided for @batteryCapacity.
  ///
  /// In en, this message translates to:
  /// **'Battery Capacity'**
  String get batteryCapacity;

  /// No description provided for @currentCharge.
  ///
  /// In en, this message translates to:
  /// **'Current Charge'**
  String get currentCharge;

  /// No description provided for @targetCharge.
  ///
  /// In en, this message translates to:
  /// **'Target Charge'**
  String get targetCharge;

  /// No description provided for @estimatedEnergy.
  ///
  /// In en, this message translates to:
  /// **'Estimated Energy'**
  String get estimatedEnergy;

  /// No description provided for @estimatedTime.
  ///
  /// In en, this message translates to:
  /// **'Estimated Time'**
  String get estimatedTime;

  /// No description provided for @estimatedCost.
  ///
  /// In en, this message translates to:
  /// **'Estimated Cost'**
  String get estimatedCost;

  /// No description provided for @carbonFootprint.
  ///
  /// In en, this message translates to:
  /// **'Carbon Footprint'**
  String get carbonFootprint;

  /// No description provided for @co2Saved.
  ///
  /// In en, this message translates to:
  /// **'CO₂ Saved'**
  String get co2Saved;

  /// No description provided for @petrolSaved.
  ///
  /// In en, this message translates to:
  /// **'Petrol Saved'**
  String get petrolSaved;

  /// No description provided for @treesEquivalent.
  ///
  /// In en, this message translates to:
  /// **'Trees Equivalent'**
  String get treesEquivalent;

  /// No description provided for @thisMonth.
  ///
  /// In en, this message translates to:
  /// **'This Month'**
  String get thisMonth;

  /// No description provided for @totalSessions.
  ///
  /// In en, this message translates to:
  /// **'Total Sessions'**
  String get totalSessions;

  /// No description provided for @chargingHistory.
  ///
  /// In en, this message translates to:
  /// **'Charging History'**
  String get chargingHistory;

  /// No description provided for @noHistory.
  ///
  /// In en, this message translates to:
  /// **'No charging history'**
  String get noHistory;

  /// No description provided for @energy.
  ///
  /// In en, this message translates to:
  /// **'Energy'**
  String get energy;

  /// No description provided for @duration2.
  ///
  /// In en, this message translates to:
  /// **'Duration'**
  String get duration2;

  /// No description provided for @cost.
  ///
  /// In en, this message translates to:
  /// **'Cost'**
  String get cost;

  /// No description provided for @status.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get status;

  /// No description provided for @completed.
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get completed;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @english.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get english;

  /// No description provided for @malay.
  ///
  /// In en, this message translates to:
  /// **'Bahasa Malaysia'**
  String get malay;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Logout'**
  String get logout;

  /// No description provided for @wallet.
  ///
  /// In en, this message translates to:
  /// **'Wallet'**
  String get wallet;

  /// No description provided for @topUp.
  ///
  /// In en, this message translates to:
  /// **'Top Up'**
  String get topUp;

  /// No description provided for @balance.
  ///
  /// In en, this message translates to:
  /// **'Balance'**
  String get balance;

  /// No description provided for @minutes.
  ///
  /// In en, this message translates to:
  /// **'min'**
  String get minutes;

  /// No description provided for @kwh.
  ///
  /// In en, this message translates to:
  /// **'kWh'**
  String get kwh;

  /// No description provided for @rm.
  ///
  /// In en, this message translates to:
  /// **'RM'**
  String get rm;

  /// No description provided for @myBookings.
  ///
  /// In en, this message translates to:
  /// **'My Bookings'**
  String get myBookings;

  /// No description provided for @noBookings.
  ///
  /// In en, this message translates to:
  /// **'No bookings yet'**
  String get noBookings;

  /// No description provided for @bookingConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Booking Confirmed!'**
  String get bookingConfirmed;

  /// No description provided for @bookingCancelled.
  ///
  /// In en, this message translates to:
  /// **'Booking Cancelled'**
  String get bookingCancelled;

  /// No description provided for @liveCharging.
  ///
  /// In en, this message translates to:
  /// **'Live Charging'**
  String get liveCharging;

  /// No description provided for @power.
  ///
  /// In en, this message translates to:
  /// **'Power'**
  String get power;

  /// No description provided for @voltage.
  ///
  /// In en, this message translates to:
  /// **'Voltage'**
  String get voltage;

  /// No description provided for @current.
  ///
  /// In en, this message translates to:
  /// **'Current'**
  String get current;

  /// No description provided for @reviews.
  ///
  /// In en, this message translates to:
  /// **'Reviews'**
  String get reviews;

  /// No description provided for @noReviews.
  ///
  /// In en, this message translates to:
  /// **'No reviews yet'**
  String get noReviews;

  /// No description provided for @beFirst.
  ///
  /// In en, this message translates to:
  /// **'Be the first to review!'**
  String get beFirst;

  /// No description provided for @submit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get submit;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ms'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ms':
      return AppLocalizationsMs();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
