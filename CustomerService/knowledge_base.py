"""
PlagSini EV App Knowledge Base.
Contains all app-specific knowledge for the AI bot to reference.
"""
import re

# App context for the AI model
APP_CONTEXT = """
You are PlagSini Assistant, a friendly and helpful AI customer support bot for PlagSini EV — 
a Malaysian EV (Electric Vehicle) charging platform app. 

ABOUT THE APP:
- PlagSini EV is a mobile app (Android & Web) for finding, using, and paying for EV charging stations
- Users can register with email + OTP verification
- The app has an e-wallet system (PlagSini Credits) in MYR currency
- Users can scan QR codes at charging stations to start charging
- The app tracks charging sessions, energy consumed, and costs
- Users earn reward points for charging sessions
- Supports DC Fast Charging and AC charging

KEY FEATURES:
1. Account: Register/login with email + OTP, edit profile, manage vehicles
2. E-Wallet: Top up credits via FPX/TNG/GrabPay/Card, view balance & transaction history
3. Charging: Scan QR → Start charging → Monitor real-time → Auto-stop → Pay
4. Vehicles: Register plate number, brand, model, battery capacity, connector type
5. Rewards: Earn points per charging session, redeem for discounts
6. Subscriptions: Monthly charging plans
7. Business Accounts: For fleet/company EV charging management

IMPORTANT NOTES:
- Currency is MYR (Malaysian Ringgit)
- Available connector types: Type 2, CCS2, CHAdeMO
- OTP codes expire in 5 minutes
- Password must be at least 6 characters
- App supports both Bahasa Malaysia and English
- Support email: support@plagsini.com.my

TONE: Be friendly, professional, helpful. Use simple language. Can respond in Bahasa Malaysia if the user writes in BM.
Keep responses concise but thorough. Always provide step-by-step guidance when solving problems.
If you cannot solve the issue, offer to create a support ticket for human assistance.
"""

# Rule-based FAQ categories and responses
FAQ_CATEGORIES = {
    "login_account": {
        "label": "🔐 Login & Account",
        "description": "Registration, login, password, OTP issues",
        "icon": "lock",
        "questions": [
            {
                "q": "I can't register / Registration failed",
                "keywords": ["register", "signup", "sign up", "daftar", "tak boleh register", "registration", "create account", "buat akaun", "new account", "akaun baru"],
                "answer": """**Troubleshooting Registration:**

1. **Check your email format** — Make sure it's a valid email (e.g., name@gmail.com)
2. **Password requirements** — Must be at least 6 characters
3. **Email already registered?** — Try logging in instead, or use "Forgot Password"
4. **OTP not received?** — Check your spam/junk folder, wait 60 seconds, then tap "Resend"

If the problem persists, I can create a support ticket for you."""
            },
            {
                "q": "OTP code not received",
                "keywords": ["otp", "verification code", "kod", "tak dapat", "not received", "no code", "code", "verify", "pengesahan", "tak sampai"],
                "answer": """**OTP Not Received? Try these steps:**

1. ✅ Check your **spam/junk** email folder
2. ✅ Make sure the email address is correct (no typos)
3. ✅ Wait at least **60 seconds** before tapping "Resend"
4. ✅ Check your internet connection
5. ✅ Try using a different email provider (Gmail recommended)

⚠️ OTP codes expire in **5 minutes**. If expired, request a new one.

Still not working? I'll create a ticket for our team."""
            },
            {
                "q": "Forgot password / Can't login",
                "keywords": ["forgot", "password", "lupa", "cant login", "tak boleh login", "wrong password", "login", "masuk", "sign in", "tak lepas", "salah password", "reset"],
                "answer": """**Forgot Password / Login Issues:**

1. On the login screen, tap **"Forgot Password?"**
2. Enter your registered email address
3. Check your email for the reset link
4. Create a new password (min. 6 characters)

**If "Wrong Password" error:**
- Make sure Caps Lock is off
- Try typing the password in a notepad first to verify
- Remember: passwords are case-sensitive

**Account locked?** After 5 failed attempts, wait 15 minutes and try again."""
            },
            {
                "q": "How to change email or phone number",
                "keywords": ["change email", "tukar email", "change phone", "update profile"],
                "answer": """**To change your email or phone:**

1. Open the app → Go to **Account** tab
2. Tap **"Edit Profile"**
3. Update your email or phone number
4. You'll need to verify the new email with OTP

⚠️ Note: Changing email will require re-verification."""
            },
        ]
    },
    "charging": {
        "label": "⚡ Charging Issues",
        "description": "Starting, stopping, or problems during charging",
        "icon": "bolt",
        "questions": [
            {
                "q": "Can't start charging / QR scan not working",
                "keywords": ["cant charge", "start charging", "qr", "scan", "tak boleh charge", "not working", "charge", "cas", "pengecas", "nak charge", "how to charge", "macam mana nak charge"],
                "answer": """**Troubleshooting Charging Start:**

1. **QR Scan not working?**
   - Enable camera permission for PlagSini app
   - Clean the QR code on the charger
   - Try manual code entry (number below QR code)

2. **Charger not responding?**
   - Check if the charger shows "Available" status
   - Make sure the cable is properly connected to your car
   - Check if your car's charging port is unlocked

3. **"Insufficient balance" error?**
   - Top up your PlagSini Credits first
   - Minimum balance required depends on charger pricing

4. **Charger shows "Faulted"?**
   - Try a different charger at the same station
   - Report the faulty charger in the app"""
            },
            {
                "q": "Charging stopped unexpectedly",
                "keywords": ["stopped", "disconnected", "berhenti", "cut off", "interrupted"],
                "answer": """**Charging Stopped Unexpectedly?**

Common reasons:
1. **Car battery is full** — Normal! Charging auto-stops at target SOC
2. **Power fluctuation** — The charger has safety protection
3. **Cable disconnected** — Check physical connection
4. **Session timeout** — Some chargers have max session time

**What to do:**
- Check your charging history for the session details
- If billed incorrectly, create a dispute ticket
- Try reconnecting and starting a new session

⚠️ You will only be billed for the energy actually consumed."""
            },
            {
                "q": "Wrong billing / Overcharged",
                "keywords": ["bill", "overcharged", "wrong amount", "caj lebih", "billing", "charge too much"],
                "answer": """**Billing Dispute:**

1. Go to **Account → Charging History**
2. Find the session in question
3. Note the session details (date, charger ID, energy consumed)

**To dispute:**
I can create a support ticket with HIGH priority for our billing team.
Please provide:
- Session date & time
- Charger location
- Expected vs actual amount charged

Our team will investigate within 24 hours and issue a refund if applicable."""
            },
        ]
    },
    "wallet_payment": {
        "label": "💳 Wallet & Payment",
        "description": "Top up, balance, payment method issues",
        "icon": "wallet",
        "questions": [
            {
                "q": "Top up not reflected / Balance not updated",
                "keywords": ["top up", "topup", "balance", "baki", "not reflected", "tak masuk", "pending", "duit", "payment", "bayaran", "kredit", "credit"],
                "answer": """**Top Up Not Reflected?**

1. **Wait 5-10 minutes** — Sometimes bank processing takes time
2. **Check transaction status:**
   - Go to **Account → PlagSini Credits History**
   - Look for the transaction status (Pending/Completed/Failed)

3. **If still pending after 30 minutes:**
   - Take a screenshot of your bank payment confirmation
   - I'll create a HIGH priority ticket for our team

4. **Payment failed?**
   - Check with your bank if the amount was deducted
   - If deducted but not credited, we'll issue a manual top-up

💡 Tip: FPX payments are usually instant. Card payments may take 5-10 minutes."""
            },
            {
                "q": "How to top up credits",
                "keywords": ["how to top up", "cara topup", "add money", "tambah baki"],
                "answer": """**How to Top Up PlagSini Credits:**

1. Open the app → Go to **Account** tab
2. Tap the **"+ TOP UP"** button on your credits card
3. Enter the amount (minimum RM10)
4. Choose payment method:
   - 🏦 **FPX** (Online banking)
   - 📱 **Touch 'n Go eWallet**
   - 💰 **GrabPay**
   - 💳 **Credit/Debit Card**
5. Complete the payment
6. Credits will be added immediately!

💡 Top up RM50+ and earn bonus reward points!"""
            },
            {
                "q": "Refund request",
                "keywords": ["refund", "money back", "bayar balik", "return"],
                "answer": """**Refund Policy:**

Refunds are available for:
- ✅ Overcharged sessions (billing error)
- ✅ Failed charging sessions where you were billed
- ✅ Double-charged transactions

**To request a refund:**
I'll create a support ticket for you. Please provide:
1. Transaction date & amount
2. Reason for refund
3. Screenshot of the transaction (if available)

⏱️ Refunds are typically processed within 3-5 business days."""
            },
        ]
    },
    "vehicle": {
        "label": "🚗 Vehicle Management",
        "description": "Adding, editing, or removing vehicles",
        "icon": "car",
        "questions": [
            {
                "q": "How to add/remove a vehicle",
                "keywords": ["add vehicle", "tambah kereta", "remove vehicle", "register car"],
                "answer": """**Managing Your Vehicles:**

**To add a vehicle:**
1. Go to **Account → My Vehicles**
2. Tap **"+ Add Vehicle"**
3. Enter details:
   - Plate number (e.g., AGG 4)
   - Brand (Tesla, BYD, etc.)
   - Model
   - Battery capacity (kWh)
   - Connector type (Type 2, CCS2, CHAdeMO)
4. Tap **Save**

**To remove:**
1. Go to **My Vehicles**
2. Swipe left on the vehicle or tap edit
3. Tap **"Delete"**

💡 Set your primary vehicle for faster charging setup!"""
            },
        ]
    },
    "rewards": {
        "label": "🎁 Rewards & Points",
        "description": "Points earning, redemption, subscriptions",
        "icon": "gift",
        "questions": [
            {
                "q": "How do rewards/points work",
                "keywords": ["rewards", "points", "mata", "ganjaran", "redeem"],
                "answer": """**PlagSini Rewards System:**

**Earning Points:**
- ⚡ Every RM1 spent on charging = 10 points
- 🎁 First-time registration bonus: 100 points
- 👥 Refer a friend: 200 points each
- 💰 Top up RM50+: 50 bonus points

**Redeeming Points:**
- 1000 points = RM5 charging credit
- 2000 points = RM12 charging credit (better value!)
- Special promotional rewards may be available

**Check your points:**
Go to **Account** tab → Your points are shown on your profile card.

⚠️ Points expire after 12 months of inactivity."""
            },
        ]
    },
    "app_issue": {
        "label": "📱 App Problems",
        "description": "App crashes, slow performance, location issues",
        "icon": "phone",
        "questions": [
            {
                "q": "App is slow or crashing",
                "keywords": ["slow", "crash", "hang", "lambat", "not loading", "error", "bug", "stuck", "loading", "tak jalan", "rosak", "problem", "masalah"],
                "answer": """**App Performance Issues:**

1. **Force close and reopen** the app
2. **Clear app cache:**
   - Android: Settings → Apps → PlagSini → Storage → Clear Cache
3. **Check internet connection** — Switch between WiFi and mobile data
4. **Update the app** — Make sure you have the latest version
5. **Restart your phone** — Sometimes a fresh start helps

**Still having issues?**
- What phone model are you using?
- What Android/iOS version?
- When does the crash happen?

I can create a detailed bug report for our dev team."""
            },
            {
                "q": "Location/GPS not working",
                "keywords": ["location", "gps", "lokasi", "map", "cant find", "station not showing"],
                "answer": """**Location/GPS Issues:**

1. **Enable location permission:**
   - Android: Settings → Apps → PlagSini → Permissions → Location → "Allow all the time"
2. **Turn on GPS/Location Services** on your phone
3. **Enable "High Accuracy" mode** (uses GPS + WiFi + Mobile)
4. **Check internet** — Map needs data connection to load

**Charging stations not showing?**
- Zoom out on the map
- Check if location filter is set correctly
- Pull down to refresh the station list"""
            },
        ]
    },
    "general": {
        "label": "❓ General Questions",
        "description": "Other questions and inquiries",
        "icon": "help",
        "questions": [
            {
                "q": "Contact support / Talk to human",
                "keywords": ["human", "agent", "person", "manusia", "contact", "hubungi", "talk to"],
                "answer": """**Contact Our Support Team:**

I can help create a support ticket and a real human will follow up with you!

You can also reach us via:
- 📧 Email: support@plagsini.com.my
- 🕐 Operating hours: Mon-Fri, 9:00 AM - 6:00 PM (MYT)

For urgent charging issues (stuck cable, safety), please call our emergency hotline.

Would you like me to create a support ticket now?"""
            },
        ]
    }
}

# Priority detection rules
PRIORITY_RULES = {
    "critical": {
        "keywords": ["emergency", "stuck", "kecemasan", "dangerous", "bahaya", "fire", "smoke"],
        "response_time": "< 30 minutes"
    },
    "high": {
        "keywords": ["cant charge", "tak boleh charge", "overcharged", "money lost", "duit hilang", 
                      "wrong billing", "session stuck", "refund"],
        "response_time": "< 2 hours"
    },
    "medium": {
        "keywords": ["login", "otp", "password", "top up", "topup", "balance", "pending"],
        "response_time": "< 12 hours"
    },
    "low": {
        "keywords": ["how to", "macam mana", "question", "soalan", "feature request", "suggestion"],
        "response_time": "< 24 hours"
    }
}


def detect_category(text: str) -> str:
    """Detect issue category from user text."""
    text_lower = text.lower()
    
    # Score each category
    scores = {}
    for cat_key, cat_data in FAQ_CATEGORIES.items():
        score = 0
        for qa in cat_data["questions"]:
            for kw in qa["keywords"]:
                if kw.lower() in text_lower:
                    score += 1
        scores[cat_key] = score
    
    # Return highest scoring category, or "general" if no match
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def detect_priority(text: str) -> str:
    """Detect ticket priority from user text."""
    text_lower = text.lower()
    
    for priority in ["critical", "high", "medium", "low"]:
        for kw in PRIORITY_RULES[priority]["keywords"]:
            if kw in text_lower:
                return priority
    
    return "medium"  # default


def find_best_faq_answer(text: str, category: str = None) -> str | None:
    """Find the best matching FAQ answer for the user's question.
    
    Uses fuzzy matching: partial keyword matches and word-level matching.
    """
    text_lower = text.lower().strip()
    words = set(re.sub(r'[^\w\s]', '', text_lower).split())
    best_match = None
    best_score = 0
    
    categories = [category] if category else FAQ_CATEGORIES.keys()
    
    for cat_key in categories:
        if cat_key not in FAQ_CATEGORIES:
            continue
        for qa in FAQ_CATEGORIES[cat_key]["questions"]:
            score = 0
            for kw in qa["keywords"]:
                kw_lower = kw.lower()
                # Exact substring match (strongest)
                if kw_lower in text_lower:
                    score += 3
                # Word-level match
                elif any(kw_lower in w or w in kw_lower for w in words if len(w) > 2):
                    score += 1
            
            # Also check if the question text itself partially matches
            q_words = set(re.sub(r'[^\w\s]', '', qa["q"].lower()).split())
            common = words & q_words
            meaningful_common = {w for w in common if len(w) > 3}
            score += len(meaningful_common)
            
            if score > best_score:
                best_score = score
                best_match = qa["answer"]
    
    # Require at least score of 1 for a match
    return best_match if best_score > 0 else None
