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
- PlagSini EV is a mobile app (Android & Web) for finding, using, and paying for EV charging stations in Malaysia
- Users register with email + OTP (one-time password) verification
- The app has an e-wallet system called "PlagSini Credits" in MYR (Malaysian Ringgit)
- Users scan QR codes at physical charging stations to start charging
- The app tracks charging sessions in real-time: energy consumed (kWh), cost (MYR), duration
- Charging auto-stops when the session ends or the car is full
- Users earn reward points for every charging session
- Supports DC Fast Charging (CCS2, CHAdeMO) and AC charging (Type 2)
- App is available in Bahasa Malaysia and English

KEY FEATURES:
1. Account: Register/login with email + OTP, edit profile, manage vehicles, view history
2. E-Wallet (PlagSini Credits): Top up via FPX (online banking), Touch 'n Go eWallet, GrabPay, or Credit/Debit Card; view balance & transaction history
3. Charging: Scan QR code at charger → App connects → Start charging → Monitor real-time → Session ends → Deducted from Credits
4. Vehicles: Register plate number, brand (BYD, Tesla, Proton e.MAS, etc.), model, battery capacity (kWh), connector type
5. Rewards: Earn points per RM spent on charging, redeem for charging discounts or credits
6. Subscriptions: Monthly charging plans available for frequent users
7. Business Accounts: Fleet/company management for multiple vehicles and users
8. Charging History: Full log of all past sessions with energy, cost, duration details
9. Map: Find nearby charging stations, see real-time availability (Available / Charging / Faulted / Offline)
10. Support Chat: This chatbot + ticket system for human escalation

PRICING:
- Charging is billed per kWh consumed
- Rates vary by charger type and location
- No hidden fees — you only pay for energy consumed
- Minimum top-up: RM10

IMPORTANT TECHNICAL NOTES:
- OTP codes expire in 5 minutes
- Password must be at least 6 characters
- After 5 failed login attempts, account is locked for 15 minutes
- Credits are non-refundable except for billing errors
- FPX payments are usually instant; card/TNG may take up to 10 minutes
- Charging stops automatically when car is full OR when Credits run out
- Support email: support@plagsini.com.my
- Business hours: Mon-Fri, 9:00 AM – 6:00 PM (MYT)

RESPONSE GUIDELINES:
- Be friendly, professional, and helpful
- Respond in Bahasa Malaysia if the user writes in BM — mix is OK ("Bahasa rojak" is fine)
- Use simple language, avoid overly technical jargon
- Always give step-by-step guidance for problem-solving
- Keep responses concise but thorough — 3-6 steps max per instruction
- If you cannot solve the issue, offer to create a support ticket for human assistance
- Never make up features or policies that aren't listed above
- If unsure, say so and offer to escalate to human support
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
                "keywords": [
                    "register", "signup", "sign up", "daftar", "tak boleh register", "registration",
                    "create account", "buat akaun", "new account", "akaun baru", "cannot register",
                    "register fail", "daftar gagal", "gagal daftar", "nak daftar", "how to register",
                    "cara daftar", "tak dapat daftar", "pendaftaran"
                ],
                "answer": """**Tak Boleh Register? Cuba langkah ini:**

1. **Format email** — Pastikan email betul (contoh: nama@gmail.com)
2. **Password** — Mesti sekurang-kurangnya **6 aksara**
3. **Email dah ada?** — Cuba log masuk, atau guna "Forgot Password"
4. **OTP tak sampai?** — Check folder spam/junk, tunggu 60 saat, lepas tu tap "Resend"
5. **Sambungan internet** — Pastikan ada internet masa daftar

Kalau masih tak boleh, boleh buat support ticket dan team kami akan follow up! 😊"""
            },
            {
                "q": "OTP code not received",
                "keywords": [
                    "otp", "verification code", "kod", "tak dapat", "not received", "no code",
                    "code", "verify", "pengesahan", "tak sampai", "kod tak masuk", "kod tak dapat",
                    "otp tak masuk", "resend otp", "otp expired", "kod tamat", "tak terima kod",
                    "email tak masuk", "verification email"
                ],
                "answer": """**OTP Tak Sampai? Cuba ni:**

1. ✅ Check folder **spam/junk** dalam email kau
2. ✅ Pastikan **email address betul** (takde typo)
3. ✅ Tunggu sekurang-kurangnya **60 saat** sebelum tap "Resend"
4. ✅ Check **sambungan internet** — kena ada data/WiFi
5. ✅ Cuba guna **Gmail** — kadang email lain lambat sikit

⚠️ Kod OTP **expire dalam 5 minit**. Kalau dah expire, request baru.

Masih tak dapat? Buat ticket dan kami akan check manual."""
            },
            {
                "q": "Forgot password / Can't login",
                "keywords": [
                    "forgot", "password", "lupa", "cant login", "tak boleh login", "wrong password",
                    "login", "masuk", "sign in", "tak lepas", "salah password", "reset",
                    "lupa password", "reset password", "tukar password", "password salah",
                    "cannot login", "login problem", "tak dapat login", "login issue",
                    "account locked", "akaun dikunci", "locked out"
                ],
                "answer": """**Lupa Password / Tak Boleh Log Masuk:**

**Reset Password:**
1. Pergi ke skrin login → tap **"Forgot Password?"**
2. Masukkan email yang berdaftar
3. Check email — ada link reset
4. Buat password baru (min. 6 aksara)

**Kalau dapat error "Wrong Password":**
- Pastikan Caps Lock OFF
- Cuba taip password dalam notepad dulu untuk verify
- Password adalah case-sensitive (huruf besar/kecil berbeza)

**Akaun dikunci?**
- Selepas **5 cubaan gagal**, tunggu **15 minit** sebelum cuba lagi
- Atau guna reset password di atas"""
            },
            {
                "q": "How to change profile / email / phone number",
                "keywords": [
                    "change email", "tukar email", "change phone", "update profile", "edit profile",
                    "tukar nombor", "change number", "kemaskini profil", "update account",
                    "change name", "tukar nama", "profile settings", "tetapan akaun"
                ],
                "answer": """**Nak Kemaskini Profil:**

1. Buka app → pergi tab **Account** (ikon orang)
2. Tap **"Edit Profile"**
3. Kemaskini maklumat yang nak ditukar:
   - Nama
   - Nombor telefon
   - Email (perlu verify semula dengan OTP)
4. Tap **"Save"**

⚠️ Tukar email akan minta OTP verification ke email baru."""
            },
            {
                "q": "How to delete account",
                "keywords": [
                    "delete account", "padam akaun", "remove account", "close account",
                    "hapus akaun", "cancel account", "nak delete", "nak tutup akaun"
                ],
                "answer": """**Padam Akaun:**

Permintaan padam akaun perlu dibuat melalui support team kami atas sebab keselamatan.

Sila email ke **support@plagsini.com.my** dengan:
- Subject: "Permohonan Padam Akaun"
- Email yang berdaftar
- Sebab pemadaman

Atau saya boleh buat support ticket untuk kau sekarang.

⚠️ Nota: Baki Credits yang tinggal tidak boleh dipulangkan selepas akaun dipadam."""
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
                "keywords": [
                    "cant charge", "start charging", "qr", "scan", "tak boleh charge", "not working",
                    "charge", "cas", "pengecas", "nak charge", "how to charge", "macam mana nak charge",
                    "qr tak boleh scan", "qr code", "charger tak respond", "start fail",
                    "cannot start", "charging not starting", "tak boleh mula", "mula cas",
                    "scan qr", "imbas qr", "charger offline", "charger faulted"
                ],
                "answer": """**Tak Boleh Mula Mengecas?**

**QR Scan tak jalan:**
- Enable **camera permission** untuk app PlagSini
- Bersihkan QR code kat charger (mungkin kotor/rosak)
- Cuba **manual entry** — ada nombor kat bawah QR code

**Charger tak respond:**
- Check status charger dalam app — mesti tunjuk **"Available"**
- Pastikan kabel dah sambung betul ke kereta
- Pastikan charging port kereta **dah dibuka/unlock**

**Error "Insufficient Balance":**
- Baki Credits tak cukup — kena **top up** dulu
- Minimum baki bergantung pada charger

**Charger tunjuk "Faulted":**
- Cuba charger lain kat stesen yang sama
- Report charger rosak dalam app"""
            },
            {
                "q": "How to charge / Step by step charging guide",
                "keywords": [
                    "how to use", "cara guna", "step by step", "langkah", "tutorial",
                    "first time charge", "kali pertama cas", "macam mana nak guna",
                    "nak try charge", "charging guide", "panduan cas"
                ],
                "answer": """**Cara Guna PlagSini untuk Mengecas:**

1. **Buka app** → Log masuk ke akaun kau
2. **Pastikan baki** — Check Credits mencukupi di tab Account
3. **Pergi ke charger** — Cari stesen cas kat tab Maps/Explore
4. **Sambung kabel** — Pasang kabel ke kereta kau dulu
5. **Scan QR** — Tap ikon scan kat app, imbas QR kat charger
6. **Sahkan** — Semak maklumat charging, tap "Start Charging"
7. **Monitor** — App tunjuk real-time: kWh, kos, masa
8. **Selesai** — Cabut kabel bila dah siap, bil auto-deduct dari Credits

💡 Tip: Letak kereta kau dulu, baru scan QR — elak tunggu lama!"""
            },
            {
                "q": "Charging stopped unexpectedly",
                "keywords": [
                    "stopped", "disconnected", "berhenti", "cut off", "interrupted",
                    "tiba-tiba berhenti", "cas terhenti", "disconnected suddenly",
                    "charging stopped", "cas stop sendiri", "kenapa berhenti", "why stop"
                ],
                "answer": """**Sesi Cas Terhenti Sendiri?**

Sebab biasa:
1. **Bateri penuh** — Normal! Auto-stop bila target SOC tercapai
2. **Baki Credits habis** — Sesi stop bila Credits tak cukup
3. **Kabel tercabut** — Check sambungan fizikal kabel
4. **Gangguan bekalan kuasa** — Charger ada perlindungan keselamatan
5. **Masa sesi tamat** — Sesetengah charger ada had masa

**Apa nak buat:**
- Check **Charging History** untuk detail sesi
- Kau hanya akan dicaj untuk **tenaga yang sebenarnya digunakan**
- Kalau bil nampak salah → create dispute ticket

Cuba sambung semula dan mulakan sesi baru."""
            },
            {
                "q": "Wrong billing / Overcharged",
                "keywords": [
                    "bill", "overcharged", "wrong amount", "caj lebih", "billing", "charge too much",
                    "salah bil", "lebih caj", "wrong charge", "incorrect bill", "disputing charge",
                    "bil tak betul", "kena tipu", "bil salah", "refund charging"
                ],
                "answer": """**Pertikaian Bil Cas:**

1. Pergi **Account → Charging History**
2. Cari sesi yang bermasalah
3. Catat detail sesi (tarikh, ID charger, kWh, kos)

**Untuk buat dispute:**
Saya boleh buat **support ticket PRIORITY TINGGI** untuk team billing.

Sediakan maklumat ni:
- Tarikh & masa sesi
- Lokasi charger
- Jumlah yang dijangka vs yang dicaj
- Screenshot (kalau ada)

Team kami akan investigate dalam 24 jam dan pulangkan wang kalau berlaku kesilapan."""
            },
            {
                "q": "Charger is offline or unavailable",
                "keywords": [
                    "offline", "unavailable", "charger rosak", "charger tak ada", "broken charger",
                    "charger error", "out of service", "not available", "faulted", "maintenance"
                ],
                "answer": """**Charger Offline / Tidak Tersedia:**

1. **Refresh app** — Tarik ke bawah untuk refresh status
2. **Cuba charger lain** kat stesen yang sama
3. **Check jam operasi** — Sesetengah stesen ada waktu operasi
4. **Report charger rosak** dalam app supaya team kami boleh fix

Kalau semua charger kat stesen tu offline dan kau ada emergency, hubungi:
📧 support@plagsini.com.my"""
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
                "keywords": [
                    "top up", "topup", "balance", "baki", "not reflected", "tak masuk", "pending",
                    "duit", "payment", "bayaran", "kredit", "credit", "tak update", "still pending",
                    "topup pending", "bayaran pending", "duit tak masuk", "credits tak masuk",
                    "topup problem", "topup issue", "reload", "isi baki"
                ],
                "answer": """**Top Up Tak Masuk?**

1. **Tunggu 5-10 minit** — Proses bank kadang ambil masa
2. **Check status transaksi:**
   - Pergi **Account → PlagSini Credits History**
   - Tengok status: Pending / Completed / Failed

3. **Masih pending selepas 30 minit?**
   - Screenshot konfirmasi bayaran dari bank/TNG/GrabPay
   - Saya akan buat **HIGH priority ticket**

4. **Bayaran gagal?**
   - Check dengan bank sama ada jumlah dah ditolak
   - Kalau dah tolak tapi Credits tak masuk → kami akan top up manual

💡 FPX biasanya instant. Card/TNG boleh ambil masa 5-10 minit."""
            },
            {
                "q": "How to top up credits",
                "keywords": [
                    "how to top up", "cara topup", "add money", "tambah baki", "nak reload",
                    "nak top up", "payment method", "cara bayar", "topup cara", "reload cara",
                    "add credits", "isi kredit", "fpx", "tng", "grabpay", "cara isi"
                ],
                "answer": """**Cara Top Up PlagSini Credits:**

1. Buka app → pergi tab **Account**
2. Tap butang **"+ TOP UP"** kat kad credits
3. Masukkan jumlah (minimum **RM10**)
4. Pilih cara bayar:
   - 🏦 **FPX** — Online banking (CIMB, Maybank, dll)
   - 📱 **Touch 'n Go eWallet** — TNG scan QR
   - 💰 **GrabPay** — Guna dalam app Grab
   - 💳 **Credit/Debit Card** — Visa, Mastercard
5. Lengkapkan bayaran
6. Credits akan masuk dengan segera!

💡 Top up RM50 ke atas → dapat **bonus reward points**!"""
            },
            {
                "q": "Refund request",
                "keywords": [
                    "refund", "money back", "bayar balik", "return", "pulangkan", "nak refund",
                    "minta refund", "refund request", "cancel payment", "batal bayaran",
                    "duit balik", "wang balik"
                ],
                "answer": """**Polisi Refund PlagSini:**

Refund boleh dibuat untuk:
- ✅ Sesi cas yang dicaj terlalu banyak (kesilapan bil)
- ✅ Sesi cas yang gagal tapi dah ditolak dari Credits
- ✅ Transaksi double-charged

❌ Credits yang dibeli **tidak boleh di-refund** kecuali ada kesilapan teknikal.

**Cara minta refund:**
Saya boleh buat support ticket untuk kau. Sediakan:
1. Tarikh & jumlah transaksi
2. Sebab refund
3. Screenshot transaksi (kalau ada)

⏱️ Refund biasanya diproses dalam **3-5 hari bekerja**."""
            },
            {
                "q": "Payment failed",
                "keywords": [
                    "payment failed", "bayaran gagal", "failed payment", "transaction failed",
                    "transaksi gagal", "payment error", "card declined", "kad ditolak",
                    "fpx failed", "tng failed", "grabpay failed", "payment unsuccessful"
                ],
                "answer": """**Bayaran Gagal?**

**Cuba benda ni:**
1. **Semak baki** bank/TNG/GrabPay — pastikan mencukupi
2. **Kad kredit/debit** — Pastikan had tidak terlepas, dan card tak expired
3. **Cuba kaedah bayaran lain** — contoh tukar dari card ke FPX
4. **Sambungan internet** — Pastikan stabil masa buat bayaran

**Kalau duit dah ditolak tapi Credits tak masuk:**
- Tunggu 10-15 minit dulu
- Check **Credits History** dalam app
- Kalau masih tak masuk, screenshot dan buat ticket — kami akan resolve!

Bayaran yang gagal **tidak akan ditolak dari akaun bank** — kalau dah fail, duit selamat."""
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
                "keywords": [
                    "add vehicle", "tambah kereta", "remove vehicle", "register car",
                    "daftar kereta", "kereta baru", "new car", "add car", "delete car",
                    "padam kereta", "plate number", "nombor plate", "my vehicles",
                    "kereta saya", "nak tambah", "connector type", "ev model"
                ],
                "answer": """**Urus Kenderaan Kau:**

**Tambah kenderaan:**
1. Pergi **Account → My Vehicles**
2. Tap **"+ Add Vehicle"**
3. Masukkan:
   - Nombor plate (cth: AGG 4)
   - Jenama (BYD, Tesla, Proton e.MAS, dll)
   - Model
   - Kapasiti bateri (kWh)
   - Jenis connector: **Type 2**, **CCS2**, atau **CHAdeMO**
4. Tap **Save**

**Padam kenderaan:**
1. Pergi **My Vehicles**
2. Swipe kiri kat kenderaan atau tap edit
3. Tap **"Delete"**

💡 Set **primary vehicle** untuk setup charging lebih pantas!"""
            },
            {
                "q": "What connector type does my car use",
                "keywords": [
                    "connector", "plug", "type 2", "ccs2", "chademo", "connector type",
                    "jenis connector", "apa connector", "port kereta", "charging port",
                    "my car connector", "which plug"
                ],
                "answer": """**Jenis Connector EV di Malaysia:**

| Connector | Digunakan Oleh |
|-----------|----------------|
| **Type 2 (AC)** | Kebanyakan EV — BYD, Tesla, Volvo, BMW, Hyundai |
| **CCS2 (DC Fast)** | BYD, Tesla (adapter), BMW, Hyundai, Kia |
| **CHAdeMO (DC Fast)** | Nissan Leaf (lama) |

**Tak pasti connector kau?**
- Check manual kereta
- Tengok charging port kat kereta — bentuk dia berbeza
- Google "[model kereta kau] charging connector type"

Kalau masih tak pasti, buat ticket dan kami boleh bantu! 😊"""
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
                "keywords": [
                    "rewards", "points", "mata", "ganjaran", "redeem", "reward points",
                    "how points work", "earn points", "claim rewards", "point system",
                    "mata ganjaran", "dapat points", "claim point", "tukar point"
                ],
                "answer": """**Sistem Rewards PlagSini:**

**Cara Dapat Points:**
- ⚡ Setiap **RM1 digunakan untuk mengecas** = 10 points
- 🎁 Bonus daftar pertama: **100 points**
- 👥 Refer rakan: **200 points** (kau dan rakan)
- 💰 Top up RM50+: **50 bonus points**

**Cara Tukar Points:**
- 1,000 points = RM5 kredit cas
- 2,000 points = RM12 kredit cas (lebih berbaloi!)
- Reward promosi khas mungkin ada dari semasa ke semasa

**Check points kau:**
Pergi tab **Account** → Points ditunjukkan kat kad profil kau.

⚠️ Points akan **expire selepas 12 bulan** tanpa aktiviti."""
            },
            {
                "q": "Points not credited / Missing points",
                "keywords": [
                    "points missing", "points tak masuk", "missing points", "where are my points",
                    "mana points", "points tak dapat", "points hilang", "points not added"
                ],
                "answer": """**Points Tak Masuk?**

Points biasanya dikreditkan dalam **5 minit** selepas sesi cas selesai.

**Cuba ni:**
1. Refresh tab Account dalam app
2. Check **Rewards History** untuk log lengkap

**Points masih takde selepas 30 minit?**
Buat support ticket dengan maklumat:
- Tarikh & masa sesi cas
- ID charger / lokasi
- Jumlah kWh yang dicaj

Team kami akan investigate dan kredit kan points yang sepatutnya."""
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
                "keywords": [
                    "slow", "crash", "hang", "lambat", "not loading", "error", "bug", "stuck",
                    "loading", "tak jalan", "rosak", "problem", "masalah", "app crash",
                    "app hang", "app slow", "tak boleh buka", "cannot open", "loading screen",
                    "app freeze", "beku", "app error", "not responding", "tak respond"
                ],
                "answer": """**App Bermasalah?**

1. **Force close** app dan buka semula
2. **Clear cache:**
   - Android: Settings → Apps → PlagSini → Storage → Clear Cache
3. **Check internet** — Cuba tukar antara WiFi dan mobile data
4. **Update app** — Pastikan guna versi terbaru (check Play Store)
5. **Restart phone** — Kadang perlu fresh start

**Masih bermasalah?**
- Phone model apa?
- Versi Android berapa?
- Bila crash terjadi?

Boleh buat bug report untuk team dev kami!"""
            },
            {
                "q": "Location/GPS not working",
                "keywords": [
                    "location", "gps", "lokasi", "map", "cant find", "station not showing",
                    "maps", "charger not on map", "location permission", "gps problem",
                    "tak nampak charger", "mana charger", "peta", "cari charger"
                ],
                "answer": """**GPS / Lokasi Tak Jalan:**

1. **Bagi permission lokasi:**
   - Android: Settings → Apps → PlagSini → Permissions → Location → "Allow all the time"
2. **Hidupkan GPS** dalam phone kau
3. **Guna mode "High Accuracy"** (GPS + WiFi + Mobile data)
4. **Sambungan internet** — Map perlukan data untuk load

**Charger tak tunjuk kat map?**
- Zoom out lebih jauh di map
- Check kalau ada filter yang diset
- Pull down untuk refresh senarai stesen"""
            },
            {
                "q": "App not available in my area / station not found",
                "keywords": [
                    "not available", "area", "kawasan", "takde charger", "tiada charger",
                    "no charging station", "stesen takde", "tak jumpa stesen"
                ],
                "answer": """**Takde Charger Berdekatan?**

PlagSini sentiasa berkembang — kami tambah stesen baru setiap bulan!

**Apa kau boleh buat:**
1. Check tab **Maps** — Zoom out untuk tengok lebih luas
2. Tengok **jenis connector** yang kau pilih — mungkin ada stesen tapi connector berbeza
3. Suggest lokasi baru kepada kami via email atau support ticket

📧 support@plagsini.com.my — kami suka dapat cadangan dari pengguna!"""
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
                "keywords": [
                    "human", "agent", "person", "manusia", "contact", "hubungi", "talk to",
                    "real person", "cakap dengan orang", "support team", "staff", "customer service",
                    "call", "telefon", "email support", "nak jumpa", "nak cakap"
                ],
                "answer": """**Hubungi Team Support PlagSini:**

Saya boleh buat support ticket dan orang sebenar dari team kami akan follow up!

📧 **Email:** support@plagsini.com.my
🕐 **Waktu operasi:** Isnin–Jumaat, 9:00 AM – 6:00 PM (MYT)

Nak saya buat support ticket sekarang? 😊"""
            },
            {
                "q": "What is PlagSini / About the app",
                "keywords": [
                    "what is plagsini", "apa plagsini", "about app", "about plagsini",
                    "plagsini ni apa", "app ni untuk apa", "ev charging app", "macam mana app ni",
                    "how does it work", "macam mana ia berfungsi"
                ],
                "answer": """**Tentang PlagSini EV** 🔋

PlagSini adalah app cas EV (Electric Vehicle) di Malaysia!

**Kau boleh:**
- 🗺️ **Cari stesen cas** berdekatan dengan Maps
- ⚡ **Mula cas** dengan scan QR code kat charger
- 💳 **Top up** Credits guna FPX, TNG, GrabPay, atau kad
- 📊 **Track sesi** cas secara real-time
- 🎁 **Earn rewards** setiap kali cas
- 🚗 **Urus kenderaan** EV kau

App tersedia untuk **Android** dan juga **Web** kat charger.czeros.tech/app/

Ada soalan lain? Type je! 😊"""
            },
            {
                "q": "How to report a faulty charger",
                "keywords": [
                    "report charger", "charger rosak", "faulty charger", "broken charger",
                    "laporkan charger", "report problem", "charger problem", "stesen rosak"
                ],
                "answer": """**Report Charger Rosak:**

**Dalam app:**
1. Pergi ke halaman stesen cas
2. Tap ikon "Report" atau "⚠️"
3. Pilih jenis masalah dan submit

**Atau:**
Buat support ticket melalui chat ni dengan:
- Nama/lokasi stesen
- ID charger (nombor kat charger)
- Jenis masalah (takde respond, kabel rosak, dll)

Team kami akan hantar technician untuk check! 🔧"""
            },
            {
                "q": "Subscription plans",
                "keywords": [
                    "subscription", "plan", "monthly", "pakej", "langganan", "bayaran bulanan",
                    "monthly plan", "charging plan", "pakej cas", "corporate"
                ],
                "answer": """**Pakej Langganan PlagSini:**

Kami ada pakej langganan bulanan untuk pengguna kerap!

**Kelebihan pakej:**
- Kadar cas lebih murah
- Bayaran tetap setiap bulan
- Sesuai untuk pemandu EV harian

Untuk maklumat lanjut tentang pakej terkini, hubungi:
📧 support@plagsini.com.my

Atau buat ticket dan team kami akan jelaskan pilihan yang ada! 😊"""
            },
        ]
    }
}

# Priority detection rules
PRIORITY_RULES = {
    "critical": {
        "keywords": ["emergency", "stuck", "kecemasan", "dangerous", "bahaya", "fire", "smoke", "api", "asap"],
        "response_time": "< 30 minutes"
    },
    "high": {
        "keywords": [
            "cant charge", "tak boleh charge", "overcharged", "money lost", "duit hilang",
            "wrong billing", "session stuck", "refund", "bil salah", "caj lebih", "tipu",
            "duit kena tolak", "payment deducted", "credits hilang"
        ],
        "response_time": "< 2 hours"
    },
    "medium": {
        "keywords": [
            "login", "otp", "password", "top up", "topup", "balance", "pending",
            "tak masuk", "tak dapat", "lupa", "error", "fail"
        ],
        "response_time": "< 12 hours"
    },
    "low": {
        "keywords": [
            "how to", "macam mana", "question", "soalan", "feature request", "suggestion",
            "apa", "what is", "cara", "tanya", "nak tahu"
        ],
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
                # Word-level match (partial)
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

    # Require at least score of 2 for a match (raised from 1 to reduce false positives)
    return best_match if best_score >= 2 else None
