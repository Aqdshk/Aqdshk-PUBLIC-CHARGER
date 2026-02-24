# 📖 PlagSini EV Charging Platform — User Manual

> **Version:** 1.0.0  
> **Last Updated:** February 2026  
> **Platform:** Android / iOS / Web

---

## What's New (Feb 2026)

- Admin dashboard pages are now more responsive across different screen sizes.
- Admin cards/charts are more compact for better readability on laptop screens.
- Sidebar menu toggle behavior on admin pages is fixed.
- Web users: if style updates do not appear immediately, do a hard refresh (`Ctrl + Shift + R`).

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
   - 2.1 [Download & Install](#21-download--install)
   - 2.2 [Create an Account](#22-create-an-account)
   - 2.3 [Email OTP Verification](#23-email-otp-verification)
   - 2.4 [Login](#24-login)
3. [App Navigation](#3-app-navigation)
4. [Dashboard (Home)](#4-dashboard-home)
   - 4.1 [Active Session Banner](#41-active-session-banner)
   - 4.2 [Quick Actions](#42-quick-actions)
   - 4.3 [Nearby Stations](#43-nearby-stations)
   - 4.4 [Favourite Stations](#44-favourite-stations)
5. [Find Charger (Map)](#5-find-charger-map)
   - 5.1 [Map View](#51-map-view)
   - 5.2 [Charger Details](#52-charger-details)
   - 5.3 [Start Charging](#53-start-charging)
6. [Scan QR Code](#6-scan-qr-code)
   - 6.1 [Camera Permission](#61-camera-permission)
   - 6.2 [Scanning a Charger](#62-scanning-a-charger)
   - 6.3 [Manual Entry](#63-manual-entry)
7. [Rewards](#7-rewards)
   - 7.1 [View Points](#71-view-points)
   - 7.2 [Redeem Rewards](#72-redeem-rewards)
   - 7.3 [Redemption History](#73-redemption-history)
8. [Profile & Settings](#8-profile--settings)
   - 8.1 [Edit Profile](#81-edit-profile)
   - 8.2 [Wallet & Top-Up](#82-wallet--top-up)
   - 8.3 [My Vehicles](#83-my-vehicles)
   - 8.4 [Charging History](#84-charging-history)
   - 8.5 [Payment Methods](#85-payment-methods)
   - 8.6 [Subscriptions](#86-subscriptions)
   - 8.7 [Invite Friends](#87-invite-friends)
   - 8.8 [FAQ & Contact Us](#88-faq--contact-us)
   - 8.9 [Logout & Delete Account](#89-logout--delete-account)
9. [Live Charging Session](#9-live-charging-session)
10. [Admin Web Dashboard](#10-admin-web-dashboard)
    - 10.1 [Dashboard Overview](#101-dashboard-overview)
    - 10.2 [Charger Management](#102-charger-management)
    - 10.3 [Sessions](#103-sessions)
    - 10.4 [Metering](#104-metering)
    - 10.5 [Faults](#105-faults)
    - 10.6 [Maintenance](#106-maintenance)
    - 10.7 [Invoice](#107-invoice)
    - 10.8 [OCPP Operations](#108-ocpp-operations)
    - 10.9 [Admin & Settings](#109-admin--settings)
11. [Troubleshooting](#11-troubleshooting)
12. [FAQ](#12-faq)

---

## 1. Introduction

**PlagSini** is a comprehensive EV (Electric Vehicle) charging platform that connects EV drivers with charging stations. The platform consists of:

- **Mobile App (AppEV)** — A Flutter-based mobile/web application for EV drivers to find chargers, start/stop charging sessions, manage wallets, and earn rewards.
- **Admin Web Dashboard (ChargingPlatform)** — A web-based management panel for administrators to monitor chargers, sessions, faults, and perform OCPP 1.6 operations.
- **ESP32 Charger Firmware** — Embedded firmware running on physical charging stations that communicates with the platform via OCPP 1.6 WebSocket protocol.

---

## 2. Getting Started

### 2.1 Download & Install

| Platform | Access |
|----------|--------|
| **Web** | Open your browser and go to `http://<server-ip>:3000` |
| **Android** | Build the APK from source or install from the provided APK file |
| **iOS** | Build from source using Xcode (requires macOS) |

### 2.2 Create an Account

1. Open the PlagSini app.
2. You will see the animated **splash screen** with the PlagSini logo, a car, and a charging station.
3. After the splash animation, you will be taken to the **Login/Register** screen.
4. Tap the **"Register"** tab at the top.
5. Fill in the registration form:
   - **Full Name** — Your display name
   - **Email Address** — A valid email (verification code will be sent here)
   - **Phone Number** — Your contact number
   - **Password** — Minimum 6 characters
   - **Confirm Password** — Must match password
6. Tap **"Send Verification Code"**.

### 2.3 Email OTP Verification

1. After tapping "Send Verification Code", an email containing a **6-digit OTP code** will be sent to your email address.
2. You will be redirected to the **OTP Verification** screen.
3. Check your email inbox (also check spam/junk folder).
4. Enter the 6-digit code in the input fields.
5. The code expires in **5 minutes**. If it expires, tap **"Resend Code"** to get a new one.
6. Once verified, your account will be created and you'll be logged in automatically.

### 2.4 Login

1. On the Login/Register screen, ensure the **"Login"** tab is selected.
2. Enter your **Email** and **Password**.
3. Tap **"Login"**.
4. Upon successful login, you'll be taken to the Dashboard.

---

## 3. App Navigation

The app uses a bottom navigation bar with 5 main tabs:

| Icon | Tab | Description |
|------|-----|-------------|
| 🏠 | **Home** | Dashboard with quick actions, nearby stations, and active session info |
| 🗺️ | **Map** | Interactive map to find charging stations near you |
| 📷 | **Scan** | QR code scanner to quickly connect to a charger |
| 🎁 | **Rewards** | View and redeem reward points |
| 👤 | **Profile** | Account settings, wallet, vehicles, and more |

---

## 4. Dashboard (Home)

The Dashboard is the main landing page after login. It provides an overview of your charging activity and quick access to key features.

### 4.1 Active Session Banner

- If you have an **active charging session**, a green banner appears at the top showing:
  - Charger ID
  - Energy consumed (kWh)
  - Elapsed time
  - **"View Session"** button to go to the live charging screen

### 4.2 Quick Actions

A horizontal scrollable row of shortcut icons:

| Icon | Action |
|------|--------|
| ⚡ DCFC | Browse DC Fast Chargers |
| 🔌 Auto Charge | Set up auto-charge preferences |
| 📴 Offline | View offline chargers |
| 🆕 New Sites | Discover newly added stations |
| 🎉 Promotions | View current promotions |
| 👥 Invite | Invite friends and earn points |
| 🏢 Business | Business account settings |

### 4.3 Nearby Stations

- Displays a list of **nearby charging stations** with:
  - Station name / Charger ID
  - Status indicator (Available, Charging, Offline)
  - Vendor and model information
  - Distance (if location is available)
- Tap on any station to view details and start charging.

### 4.4 Favourite Stations

- Stations you have marked as favourite appear in a dedicated section.
- Quick access to your most-used chargers.

---

## 5. Find Charger (Map)

### 5.1 Map View

- An **interactive OpenStreetMap** showing your current location and all nearby charging stations.
- Charger pins are color-coded:
  - 🟢 **Green** — Available
  - 🔵 **Blue** — Charging (in use)
  - 🔴 **Red** — Offline / Faulted
- The map automatically centers on your current GPS location.
- Pinch to zoom, drag to pan.

### 5.2 Charger Details

- Tap on a charger pin to see:
  - Charger ID
  - Status
  - Vendor & Model
  - Address / Location
  - Connector type
  - Pricing info
- Tap **"Start Charging"** to begin a session (if available).

### 5.3 Start Charging

1. Select an available charger.
2. Ensure your EV is plugged into the charger.
3. Tap **"Start Charging"**.
4. The app sends a **RemoteStartTransaction** command to the charger via OCPP.
5. You will be redirected to the **Live Charging** screen.

---

## 6. Scan QR Code

### 6.1 Camera Permission

- When you first open the Scan tab, the app requests **camera permission**.
- **Allow** camera access to use the QR scanner.
- If denied, you can still use **Manual Entry** (see 6.3).

### 6.2 Scanning a Charger

1. Point your camera at the **QR code** on the charging station.
2. The scanner will automatically detect and read the QR code.
3. The app will look up the charger:
   - First checks local cache
   - Then queries the server API
4. A **bottom sheet** appears showing charger details:
   - Charger ID
   - Status
   - Model & Vendor
   - Action button to start charging or view details
5. Use the **flashlight toggle** (torch icon) for scanning in dark environments.

### 6.3 Manual Entry

- If the QR code is damaged or unreadable:
  1. Tap the **"Enter Charger ID"** button at the bottom.
  2. Type the charger ID manually.
  3. Tap **"Search"** to look up the charger.

---

## 7. Rewards

### 7.1 View Points

- The Rewards screen shows your **current reward points** in an animated card at the top.
- **How to Earn Points:**
  - Complete charging sessions → earn points based on kWh consumed
  - Refer friends → earn bonus points
  - Daily check-in → earn points
  - Promotions & campaigns

### 7.2 Redeem Rewards

1. Browse the **Rewards Catalog** showing available rewards:
   - Reward name & description
   - Points required
   - Category (Discount, Voucher, Free Charge, etc.)
2. If you have **enough points**, the reward card shows a green **"Redeem"** button.
3. If you don't have enough points, the card shows:
   - **"Locked"** label
   - A **progress bar** showing how close you are
4. To redeem:
   - Tap **"Redeem"**
   - A confirmation dialog appears showing the reward and points to be deducted
   - Tap **"Confirm"** to proceed
   - A success animation confirms the redemption
5. Pull down to **refresh** the catalog and points balance.

### 7.3 Redemption History

1. Tap the **"History"** tab on the Rewards screen.
2. View a list of past redemptions including:
   - Reward name
   - Points spent
   - Date & time of redemption
   - Redemption status

---

## 8. Profile & Settings

### 8.1 Edit Profile

- Tap **"Edit Profile"** to update:
  - Display name
  - Email address
  - Phone number
  - Avatar / Profile picture

### 8.2 Wallet & Top-Up

- View your **wallet balance** on the profile card.
- Tap **"Top Up"** to add funds to your wallet.
- View **Wallet History** for all transactions (top-ups, charges, refunds).

### 8.3 My Vehicles

- Add and manage your electric vehicles:
  - Vehicle brand & model
  - License plate number
  - Battery capacity
  - Connector type

### 8.4 Charging History

- View all past and current charging sessions:
  - Date & time
  - Charger used
  - Energy consumed (kWh)
  - Duration
  - Cost

### 8.5 Payment Methods

- Manage payment methods for wallet top-ups and direct charging payments.

### 8.6 Subscriptions

- View and manage charging subscription plans if available.

### 8.7 Invite Friends

- Share your referral code or link with friends.
- Earn bonus reward points when they sign up and complete their first charge.

### 8.8 FAQ & Contact Us

- **FAQ** — Frequently asked questions about the platform.
- **Contact Us** — Get in touch with support for help.

### 8.9 Logout & Delete Account

- **Logout** — Sign out of your account. You can log back in anytime.
- **Delete Account** — Permanently delete your account and all associated data. This action cannot be undone.

---

## 9. Live Charging Session

When a charging session is active:

1. The **Live Charging Screen** shows real-time data:
   - ⚡ **Power** (kW) — Current charging power
   - 🔋 **Energy** (kWh) — Total energy consumed
   - ⏱️ **Duration** — Elapsed charging time
   - 💰 **Cost** — Estimated cost so far
   - 📊 **Voltage** (V) & **Current** (A) — Real-time electrical readings
2. A **progress animation** shows the charging status.
3. Tap **"Stop Charging"** to end the session:
   - A confirmation dialog appears
   - The app sends a **RemoteStopTransaction** command
   - Session summary is displayed with total energy and cost

---

## 10. Admin Web Dashboard

Access the admin dashboard at: `http://<server-ip>:8000`

**Default Admin Credentials:**
- Email: `1@admin.com`
- Password: `1`

> ⚠️ **Important:** Change the default credentials after first login!

### 10.1 Dashboard Overview

- **Statistics Cards:**
  - Total Chargers
  - Active Sessions
  - Total Energy (kWh)
  - Total Users
- **Charts:**
  - Energy consumption over time
  - Session activity trends
  - Revenue breakdown

### 10.2 Charger Management

- View all registered chargers with:
  - Charger ID
  - Vendor & Model
  - Firmware Version
  - Status (Online / Offline / Charging / Faulted)
  - Last Heartbeat time
- Real-time status updates via WebSocket

### 10.3 Sessions

- View all charging sessions (active and completed):
  - Transaction ID
  - Charger ID
  - Start/Stop time
  - Energy consumed
  - Status

### 10.4 Metering

- Real-time and historical meter values:
  - Voltage (V)
  - Current (A)
  - Power (kW)
  - Total Energy (kWh)
- Data is collected during active charging sessions via OCPP MeterValues.

### 10.5 Faults

- View all fault/error reports from chargers:
  - Error code
  - Charger ID
  - Timestamp
  - Severity
  - Description

### 10.6 Maintenance

- Track maintenance records:
  - Scheduled maintenance
  - Completed maintenance
  - Maintenance notes

### 10.7 Invoice

- View and manage invoices for charging sessions.

### 10.8 OCPP Operations

The OCPP Operations page allows administrators to send OCPP 1.6 commands directly to connected chargers. This is similar to the **SteVe** OCPP server interface.

**Available Operations:**

| Operation | Description |
|-----------|-------------|
| **Change Availability** | Set charger availability (Operative/Inoperative) |
| **Change Configuration** | Change charger configuration keys (Predefined or Custom) |
| **Clear Cache** | Clear the charger's authorization cache |
| **Get Configuration** | Retrieve current charger configuration |
| **Remote Start Transaction** | Remotely start a charging session |
| **Remote Stop Transaction** | Remotely stop an active charging session |
| **Reset** | Reset the charger (Hard/Soft) |
| **Unlock Connector** | Unlock a specific connector |
| **Get Diagnostics** | Request diagnostics upload from charger |
| **Update Firmware** | Trigger firmware update on charger |
| **Reserve Now** | Reserve a connector for a specific ID tag |
| **Cancel Reservation** | Cancel an existing reservation |
| **Data Transfer** | Send custom data to charger |
| **Get Local List Version** | Get the version of the local authorization list |
| **Send Local List** | Update the local authorization list |
| **Trigger Message** | Trigger a specific OCPP message from the charger |
| **Get Composite Schedule** | Get the composite charging schedule |
| **Clear Charging Profile** | Clear charging profiles |
| **Set Charging Profile** | Set a charging profile for smart charging |

**Change Configuration — Key Types:**

- **Predefined Keys** — Select from 38 standard OCPP 1.6 configuration keys via dropdown:
  - `AllowOfflineTxForUnknownId`, `AuthorizationCacheEnabled`, `HeartbeatInterval`, `MeterValueSampleInterval`, `NumberOfConnectors`, and more.
- **Custom Keys** — Enter any custom vendor-specific key manually.

**How to Use:**

1. Navigate to **OCPP Operations** in the sidebar.
2. Select the **Charger** from the dropdown (only online chargers are shown).
3. Select the **Operation** from the dropdown.
4. Fill in the required parameters for the selected operation.
5. Click **"Execute"** to send the command.
6. The response from the charger is displayed below.

### 10.9 Admin & Settings

- **Admin** — Manage admin users and permissions.
- **Settings** — Configure platform settings:
  - Pricing
  - Email/SMTP settings
  - System preferences

---

## 11. Troubleshooting

| Problem | Solution |
|---------|----------|
| **Can't login** | Check email and password. Try resetting password. |
| **OTP email not received** | Check spam/junk folder. Wait 1-2 minutes. Tap "Resend Code". |
| **Camera not working (Scan)** | Go to phone Settings > Apps > PlagSini > Permissions > Enable Camera. |
| **Charger shows "Offline"** | The charger may be disconnected from the network. Contact support. |
| **Charging won't start** | Ensure the EV cable is properly plugged in. Try scanning QR again. |
| **App crashes on startup** | Clear app cache and restart. Reinstall if persistent. |
| **Map not loading** | Check internet connection. Enable GPS/Location services. |
| **Wallet balance not updating** | Pull down to refresh. Wait a few seconds and try again. |
| **Rewards not loading** | Check internet connection. Pull down to refresh the rewards page. |

---

## 12. FAQ

**Q: Is PlagSini free to use?**  
A: The app is free to download and use. You only pay for the electricity consumed during charging sessions.

**Q: What payment methods are accepted?**  
A: Currently, the app supports wallet-based payments. Top up your wallet to start charging.

**Q: How do I earn reward points?**  
A: You earn points by completing charging sessions, referring friends, and participating in promotions.

**Q: Can I use multiple vehicles?**  
A: Yes! You can add and manage multiple vehicles in your profile under "My Vehicles".

**Q: What OCPP version is supported?**  
A: The platform supports **OCPP 1.6** (JSON/WebSocket).

**Q: How do I report a faulty charger?**  
A: Use the "Contact Us" option in your profile, or report directly from the charger detail screen.

**Q: Can I reserve a charger?**  
A: Reservation functionality is available through the admin dashboard. User-facing reservations may be available in future updates.

**Q: What happens if I lose internet during charging?**  
A: The charger continues to charge offline. The session data will sync when connectivity is restored.

---

> **Need Help?** Contact support through the app (Profile > Contact Us) or email support at the administrator's configured email address.

---

*© 2026 PlagSini EV Charging Platform. All rights reserved.*
