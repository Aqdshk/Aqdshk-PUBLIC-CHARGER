# 🚀 Deploy PlagSini EV to Google Cloud

## Total Cost: ~RM 35-50/month (or FREE with trial credits)

---

## Step 1: Create Google Cloud VM

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project → "PlagSini EV"
3. Go to **Compute Engine → VM Instances → Create**

**Recommended VM Settings:**
| Setting | Value |
|---------|-------|
| Machine type | `e2-medium` (2 vCPU, 4GB RAM) |
| OS | Ubuntu 22.04 LTS |
| Boot disk | 30 GB SSD |
| Region | `asia-southeast1` (Singapore) — closest to MY |
| Firewall | ✅ Allow HTTP, ✅ Allow HTTPS |

> 💡 Google Cloud gives **$300 free credit** for 90 days!

---

## Step 2: Get a Domain Name

Options:
- **Namecheap**: ~RM 40/year for `.com`
- **Cloudflare**: cheapest `.com`
- **Freenom**: FREE `.tk`, `.ml`, `.cf` domains (for testing)

Point your domain's **A record** to your VM's external IP:
```
Type: A
Name: @
Value: <YOUR_VM_IP>
TTL: 300
```

---

## Step 3: Connect to VM & Upload Code

```bash
# Option A: gcloud CLI
gcloud compute ssh <VM_NAME> --zone=asia-southeast1-a

# Option B: SSH directly
ssh -i ~/.ssh/google_compute_engine <YOUR_VM_IP>
```

Upload your code:
```bash
# From your local machine
gcloud compute scp --recurse "C:\PUBLIC CHARGER RND" <VM_NAME>:~/plagsini --zone=asia-southeast1-a

# OR use git (recommended)
# Push to GitHub/GitLab first, then:
git clone https://github.com/yourname/plagsini-ev.git ~/plagsini
```

---

## Step 4: Configure Environment

```bash
cd ~/plagsini

# Copy and edit environment variables
cp .env.example .env
nano .env
```

**Fill in your `.env`:**
```
DOMAIN=yourdomain.com
EMAIL_SSL=your@email.com

MYSQL_ROOT_PASSWORD=<STRONG_PASSWORD_HERE>
MYSQL_DATABASE=charging_platform
MYSQL_USER=charging_user
MYSQL_PASSWORD=<STRONG_PASSWORD_HERE>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx

API_BASE_URL=https://yourdomain.com/api
BOT_BASE_URL=https://yourdomain.com
```

---

## Step 5: Deploy!

```bash
chmod +x deploy-gcloud.sh
./deploy-gcloud.sh
```

The script will automatically:
1. ✅ Install Docker
2. ✅ Get SSL certificate (HTTPS)
3. ✅ Build all services
4. ✅ Start everything
5. ✅ Setup daily backups

---

## Step 6: Verify

Visit:
- 🌐 App: `https://yourdomain.com`
- 📊 Admin: `https://yourdomain.com/login`
- 🤖 Bot: `https://yourdomain.com/bot/`
- 🔌 API: `https://yourdomain.com/api/chargers`

---

## Architecture (Production)

```
Internet
    │
    ▼
┌─────────────────────┐
│  Nginx (Port 80/443)│  ← SSL termination, rate limiting
│  Reverse Proxy       │  ← Single entry point
└────────┬────────────┘
         │
    ┌────┼────────┬──────────┐
    │    │        │          │
    ▼    ▼        ▼          ▼
  AppEV  API     Bot      Static
 (Web)  (8000)  (8001)    Files
    │    │        │
    │    └────┬───┘
    │         ▼
    │      MySQL
    │     (3306)
    │
    └── Served via Nginx
```

**Rate Limits:**
- API: 30 req/sec per IP
- Login: 5 req/min per IP (prevents brute force)
- Bot: 10 req/sec per IP

---

## Useful Commands

```bash
# View all logs
docker compose -f docker-compose.prod.yml logs -f

# View specific service log
docker compose -f docker-compose.prod.yml logs -f charging-platform

# Restart everything
docker compose -f docker-compose.prod.yml restart

# Update code & redeploy
git pull
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Manual backup
/opt/plagsini/backup.sh

# Check disk space
df -h

# Check memory usage
free -h
docker stats --no-stream
```

---

## Troubleshooting

**SSL certificate failed?**
- Make sure domain DNS is pointing to VM IP
- Wait 5-10 min for DNS propagation
- Check: `dig yourdomain.com`

**Services won't start?**
- Check logs: `docker compose -f docker-compose.prod.yml logs`
- Check memory: `free -h` (need at least 2GB free)

**App loads but API fails?**
- Check Nginx logs: `docker logs plagsini-nginx`
- Check API logs: `docker logs plagsini-api`

---

## Monthly Costs

| Item | Cost |
|------|------|
| GCloud VM (e2-medium) | ~$25/mo (~RM 110) |
| GCloud VM (e2-small, budget) | ~$13/mo (~RM 57) |
| Domain | ~$10/yr (~RM 44/yr) |
| SSL | FREE (Let's Encrypt) |
| **Total (budget)** | **~RM 60/mo** |
| **Total (recommended)** | **~RM 120/mo** |

> First 90 days = **FREE** with Google's $300 credit!
