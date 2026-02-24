# 📱 PlagSini EV Charging — User Manual

> **Version:** 1.0.0  
> **Last Updated:** February 2026  
> **Platform:** Android / iOS / Web

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
   - 2.1 [Download & Install](#21-download--install)
   - 2.2 [Create an Account (Registration)](#22-create-an-account-registration)
   - 2.3 [Email OTP Verification](#23-email-otp-verification)
   - 2.4 [Login](#24-login)
3. [Home Dashboard](#3-home-dashboard)
   - 3.1 [Quick Actions](#31-quick-actions)
   - 3.2 [Active Session Banner](#32-active-session-banner)
   - 3.3 [Nearby Stations](#33-nearby-stations)
   - 3.4 [Featured Stations](#34-featured-stations)
4. [Find Charger (Map)](#4-find-charger-map)
   - 4.1 [Map Navigation](#41-map-navigation)
   - 4.2 [Charger Pins & Status](#42-charger-pins--status)
   - 4.3 [Station Details](#43-station-details)
5. [QR Code Scanner](#5-qr-code-scanner)
   - 5.1 [Scan a Charger QR Code](#51-scan-a-charger-qr-code)
   - 5.2 [Manual Entry](#52-manual-entry)
   - 5.3 [Flashlight Control](#53-flashlight-control)
6. [Start a Charging Session](#6-start-a-charging-session)
   - 6.1 [Select a Charger](#61-select-a-charger)
   - 6.2 [Live Charging Screen](#62-live-charging-screen)
   - 6.3 [Stop Charging](#63-stop-charging)
7. [Rewards & Points](#7-rewards--points)
   - 7.1 [How to Earn Points](#71-how-to-earn-points)
   - 7.2 [Redeem Rewards](#72-redeem-rewards)
   - 7.3 [Redemption History](#73-redemption-history)
8. [Profile & Settings](#8-profile--settings)
   - 8.1 [Edit Profile](#81-edit-profile)
   - 8.2 [Wallet & Top-Up](#82-wallet--top-up)
   - 8.3 [Payment Methods](#83-payment-methods)
   - 8.4 [My Vehicles](#84-my-vehicles)
   - 8.5 [Charging History](#85-charging-history)
   - 8.6 [Invite Friends](#86-invite-friends)
   - 8.7 [FAQ & Support](#87-faq--support)
9. [Admin Web Dashboard (ChargingPlatform)](#9-admin-web-dashboard-chargingplatform)
   - 9.1 [Accessing the Dashboard](#91-accessing-the-dashboard)
   - 9.2 [Dashboard Overview](#92-dashboard-overview)
   - 9.3 [Charger Management](#93-charger-management)
   - 9.4 [Sessions](#94-sessions)
   - 9.5 [Metering](#95-metering)
   - 9.6 [Faults](#96-faults)
   - 9.7 [Maintenance](#97-maintenance)
   - 9.8 [Invoice](#98-invoice)
   - 9.9 [OCPP Operations](#99-ocpp-operations)
   - 9.10 [Settings](#910-settings)
   - 9.11 [Admin Management](#911-admin-management)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Introduction

**PlagSini** is a complete EV (Electric Vehicle) charging ecosystem consisting of:

- **AppEV** — A mobile/web application for EV drivers to find, connect, and charge their vehicles at PlagSini charging stations.
- **ChargingPlatform** — A web-based admin dashboard for station operators to manage chargers, sessions, billing, and OCPP 1.6 operations.
- **ESP-Charger** — The embedded firmware running on the physical charging hardware (ESP32).

This User Manual covers both the **AppEV** (for drivers) and the **ChargingPlatform** (for administrators).

---

## 2. Getting Started

### 2.1 Download & Install

| Platform | Access Method |
|----------|--------------|
| **Android** | Build from source or install APK |
| **iOS** | Build from source via Xcode |
| **Web** | Navigate to `http://<server-ip>:3000` in your browser |

### 2.2 Create an Account (Registration)

1. Open the PlagSini app
2. On the splash screen, wait for the animated charging illustration to finish, then the login screen will appear
3. Tap the **"Register"** tab at the top
4. Fill in the following fields:
   - **Full Name** — Your display name
   - **Email** — A valid email address (used for verification)
   - **Phone Number** — Your mobile number
   - **Password** — Minimum 6 characters
   - **Confirm Password** — Must match the password
5. Tap **"Send Verification Code"**

### 2.3 Email OTP Verification

After tapping "Send Verification Code":

1. An **OTP (One-Time Password)** will be sent to your email
2. You will be redirected to the **OTP Verification Screen**
3. Enter the **6-digit code** from the email
4. The code expires in **5 minutes**
5. If you didn't receive the email:
   - Check your spam/junk folder
   - Tap **"Resend Code"** to get a new OTP
6. After successful verification, your account is created and you are logged in automatically

### 2.4 Login

1. Open the app and navigate to the **"Login"** tab
2. Enter your **email** and **password**
3. Tap **"Login"**
4. You will be taken to the Home Dashboard

---

## 3. Home Dashboard

The Home Dashboard is the main screen after login. It provides an overview of charging stations and quick access to features.

### 3.1 Quick Actions

At the top of the dashboard, you'll find quick action buttons:

| Icon | Action | Description |
|------|--------|-------------|
| 🔍 | **Find Charger** | Opens the map to find nearby chargers |
| ⚡ | **DCFC** | Shows DC Fast Charging stations |
| 🔌 | **Auto Charge** | Configure auto-charging settings |
| 🔴 | **Offline** | View chargers that are currently offline |
| 🆕 | **New Sites** | Recently added charging locations |
| 🎁 | **Promotions** | View current promotions and deals |
| 👥 | **Invite** | Invite friends to earn rewards |
| 🏢 | **Business** | Business account management |

### 3.2 Active Session Banner

When you have an **active charging session**, a green banner appears at the top of the dashboard showing:
- Energy consumed (kWh)
- Charging duration
- Tap to go to the **Live Charging** screen

### 3.3 Nearby Stations

A list of nearby charging stations with:
- Station name and ID
- Distance from your location
- Current status (Available, Charging, Offline)
- Tap to view station details

### 3.4 Featured Stations

Highlighted stations with additional info including charger model, vendor, and availability status.

---

## 4. Find Charger (Map)

### 4.1 Map Navigation

- The map uses **OpenStreetMap** (no API key required)
- Your current location is shown with a blue marker
- Charger locations are shown with green/red markers
- Pinch to zoom, swipe to pan

### 4.2 Charger Pins & Status

| Marker Color | Status |
|-------------|--------|
| 🟢 Green | Available — Ready to charge |
| 🔵 Blue | Charging — Currently in use |
| 🔴 Red | Offline / Unavailable |

### 4.3 Station Details

Tap a charger marker to view:
- Charger ID and location
- Vendor and model information
- Current status and availability
- **"Start Charging"** button (if available)

---

## 5. QR Code Scanner

### 5.1 Scan a Charger QR Code

1. Navigate to the **"Scan"** tab from the bottom navigation
2. Point your camera at the charger's QR code
3. The app will automatically detect and process the QR code
4. A bottom sheet will appear showing the charger's details
5. Tap **"Start Charging"** to begin a session

### 5.2 Manual Entry

If the QR code is damaged or unreadable:
1. Tap the **"Enter Manually"** button at the bottom of the scan screen
2. Type the **Charger ID** displayed on the physical charger
3. Tap **"Submit"** to look up the charger

### 5.3 Flashlight Control

- Tap the **flashlight icon** (🔦) at the top-right corner to toggle the camera flashlight
- Useful in dark environments for scanning QR codes

> **Note:** The app requires camera permission. If prompted, tap "Allow" to enable camera access.

---

## 6. Start a Charging Session

### 6.1 Select a Charger

You can select a charger via:
- **Dashboard** → Tap a station card
- **Map** → Tap a charger pin
- **QR Scanner** → Scan the charger's QR code
- **Manual Entry** → Enter the charger ID

### 6.2 Live Charging Screen

Once charging starts, the Live Charging screen shows:

| Metric | Description |
|--------|-------------|
| ⚡ **Power** | Current charging power (kW) |
| 🔋 **Energy** | Total energy consumed (kWh) |
| ⏱️ **Duration** | Elapsed charging time |
| 💰 **Cost** | Estimated charging cost |
| 📊 **Voltage** | Real-time voltage reading |
| 📊 **Current** | Real-time amperage |

The data updates in **real-time** via the server.

### 6.3 Stop Charging

1. On the Live Charging screen, tap the **"Stop Charging"** button
2. Confirm the stop action in the dialog
3. A charging summary will be displayed with total energy, duration, and cost
4. The session is saved to your charging history

---

## 7. Rewards & Points

### 7.1 How to Earn Points

| Activity | Points |
|----------|--------|
| ⚡ Each kWh charged | +10 points |
| 📅 Daily login | +5 points |
| 👥 Refer a friend | +100 points |
| ⭐ Complete profile | +50 points |

### 7.2 Redeem Rewards

1. Navigate to the **"Rewards"** tab from the bottom navigation
2. View the **Rewards** tab to see available rewards
3. Each reward shows:
   - Reward name and description
   - Points required
   - A **"Redeem"** button (if you have enough points)
   - A **progress bar** (if you don't have enough points yet)
4. Tap **"Redeem"** on a reward you want
5. Confirm the redemption in the dialog
6. Points will be deducted from your balance

### 7.3 Redemption History

1. Switch to the **"History"** tab in the Rewards screen
2. View all past redemptions with:
   - Reward name
   - Points spent
   - Redemption date
   - Status

---

## 8. Profile & Settings

### 8.1 Edit Profile

1. Go to **Profile** tab → Tap **"Edit Profile"**
2. Update your name, phone, or avatar
3. Tap **"Save"**

### 8.2 Wallet & Top-Up

- View your current wallet balance on the Profile screen
- Tap **"Top Up"** to add funds
- Select an amount and payment method
- View transaction history in **"Wallet History"**

### 8.3 Payment Methods

- Navigate to **Profile** → **"Payment"**
- Add or manage payment methods

### 8.4 My Vehicles

- Navigate to **Profile** → **"My Vehicles"**
- Add your EV details (make, model, plate number)
- Manage multiple vehicles

### 8.5 Charging History

- Navigate to **Profile** → **"History"**
- View all past charging sessions with details:
  - Date, time, and duration
  - Energy consumed and cost
  - Charger location

### 8.6 Invite Friends

- Navigate to **Profile** → **"Invite Friends"**
- Share your referral code
- Earn **100 points** for each friend who registers

### 8.7 FAQ & Support

- **FAQ** — Common questions and answers
- **Contact Us** — Submit a support request or feedback

---

## 9. Admin Web Dashboard (ChargingPlatform)

The ChargingPlatform is a web-based admin dashboard for managing the EV charging infrastructure.

### 9.1 Accessing the Dashboard

1. Open a browser and navigate to: `http://<server-ip>:8000`
2. Default admin credentials:
   - **Email:** `1@admin.com`
   - **Password:** `1`
3. ⚠️ **Change the default password immediately after first login!**

### 9.2 Dashboard Overview

The main dashboard shows:

| Widget | Description |
|--------|-------------|
| **Total Chargers** | Number of registered chargers |
| **Online Chargers** | Currently connected chargers |
| **Active Sessions** | Ongoing charging sessions |
| **Total Energy** | Cumulative energy delivered (kWh) |
| **Revenue Chart** | Daily/monthly revenue graph |
| **Session Chart** | Charging sessions over time |

### 9.3 Charger Management

Navigate to **Chargers** from the sidebar.

- View all registered chargers with status indicators
- See details: Charge Point ID, vendor, model, firmware version
- Status: Online ✅, Offline ❌, Charging ⚡
- Last heartbeat timestamp

### 9.4 Sessions

Navigate to **Sessions** from the sidebar.

- View all charging sessions (active and completed)
- Session details: Transaction ID, start/stop time, energy consumed, cost
- Filter by charger, date range, or status

### 9.5 Metering

Navigate to **Metering** from the sidebar.

- Real-time meter values from chargers
- Voltage, current, power, and energy readings
- Historical data with timestamps

### 9.6 Faults

Navigate to **Faults** from the sidebar.

- View all reported faults/errors from chargers
- Fault details: Error code, description, timestamp
- Charger identification

### 9.7 Maintenance

Navigate to **Maintenance** from the sidebar.

- Schedule and track maintenance records
- Maintenance history per charger

### 9.8 Invoice

Navigate to **Invoice** from the sidebar.

- Generate and view invoices for charging sessions
- Invoice details: User, session, energy, cost, date

### 9.9 OCPP Operations

Navigate to **🎛️ OCPP Operations** from the sidebar.

This is a powerful tool for managing chargers via the **OCPP 1.6** protocol. Available operations:

| Operation | Description |
|-----------|-------------|
| **Remote Start Transaction** | Remotely start a charging session |
| **Remote Stop Transaction** | Remotely stop an active session |
| **Change Availability** | Set a charger to Available or Unavailable |
| **Change Configuration** | Modify charger configuration keys |
| **Get Configuration** | Read charger configuration values |
| **Clear Cache** | Clear the charger's authorization cache |
| **Reset** | Soft or Hard reset of the charger |
| **Unlock Connector** | Unlock a connector remotely |
| **Get Diagnostics** | Request diagnostic data from charger |
| **Update Firmware** | Push firmware update to charger |
| **Reserve Now** | Reserve a charger for a user |
| **Cancel Reservation** | Cancel an existing reservation |
| **Trigger Message** | Trigger a specific OCPP message |
| **Get Composite Schedule** | Get the charging schedule |
| **Set Charging Profile** | Configure charging power limits |
| **Clear Charging Profile** | Remove a charging profile |
| **Data Transfer** | Custom data exchange with charger |
| **Get Local List Version** | Check authorization list version |
| **Send Local List** | Update local authorization list |

#### Change Configuration — Predefined vs Custom Keys

When using **Change Configuration**, you can choose between:

- **Predefined Keys** — A dropdown list of 38 standard OCPP 1.6 configuration keys (e.g., `HeartbeatInterval`, `MeterValueSampleInterval`, `AuthorizeRemoteTxRequests`, etc.)
- **Custom Keys** — Enter any custom/vendor-specific configuration key

### 9.10 Settings

Navigate to **Settings** from the sidebar.

- Configure pricing and tariff settings
- System configuration

### 9.11 Admin Management

Navigate to **Admin** from the sidebar.

- Manage admin users
- View registered users and their details
- User wallet and transaction management

---

## 10. Troubleshooting

### App Issues

| Problem | Solution |
|---------|----------|
| **Can't login** | Check email and password. Try "Forgot Password" if available. |
| **OTP not received** | Check spam/junk folder. Tap "Resend Code". Wait 1 minute before resending. |
| **Map not loading** | Ensure internet connection is active. Enable location services. |
| **Camera not working (QR Scanner)** | Go to phone Settings → App Permissions → Enable Camera for PlagSini. |
| **Charger not found after scan** | Ensure the charger is registered in the system. Try manual entry. |
| **Charging won't start** | Verify the charger is "Available". Check that the physical cable is properly connected. |
| **App shows stale data** | Pull down on any screen to refresh. Close and reopen the app. |

### Admin Dashboard Issues

| Problem | Solution |
|---------|----------|
| **Can't access dashboard** | Check that the server is running at port 8000. |
| **Charger shows offline** | Check the charger's internet connection. Verify WebSocket port 9000 is accessible. |
| **OCPP operation fails** | Ensure the charger is online and connected via WebSocket. |
| **No meter data** | Charger must be actively charging to send meter values. |

### Connectivity

| Problem | Solution |
|---------|----------|
| **App can't connect to server** | Verify the API URL in app settings. Check that port 8000 is open. |
| **Charger can't connect** | Verify WebSocket URL `ws://<server-ip>:9000/<charger-id>`. Check firewall rules for port 9000. |

---

> **Need help?** Contact support through the app's **"Contact Us"** section or email the system administrator.

---

*© 2026 PlagSini EV Charging Platform. All rights reserved.*
