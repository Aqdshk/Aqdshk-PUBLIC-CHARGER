#!/bin/bash
# ============================================
# PlagSini EV — Google Cloud Deploy Script
# 
# PREREQUISITES:
#   1. Google Cloud account + project
#   2. gcloud CLI installed
#   3. A domain name pointing to your VM's IP
#
# USAGE:
#   chmod +x deploy-gcloud.sh
#   ./deploy-gcloud.sh
# ============================================

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   PlagSini EV — Google Cloud Deployer    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Check if running on GCloud VM ──
echo -e "${CYAN}[1/8] Checking environment...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing Docker...${NC}"
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker installed${NC}"
else
    echo -e "${GREEN}✅ Docker found: $(docker --version)${NC}"
fi

# ── Step 2: Check .env ──
echo -e "${CYAN}[2/8] Checking .env configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}Creating from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}⚠️  PLEASE EDIT .env WITH YOUR ACTUAL VALUES BEFORE CONTINUING!${NC}"
    echo -e "${YELLOW}   nano .env${NC}"
    exit 1
fi

# Load .env
source .env

if [ "$DOMAIN" == "your-domain.com" ] || [ -z "$DOMAIN" ]; then
    echo -e "${RED}❌ Please set your DOMAIN in .env file!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Domain: $DOMAIN${NC}"

# ── Step 3: Configure Firewall ──
echo -e "${CYAN}[3/8] Configuring firewall...${NC}"
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
sudo ufw allow 9000/tcp 2>/dev/null || true  # OCPP WebSocket
echo -e "${GREEN}✅ Firewall configured (80, 443, 9000)${NC}"

# ── Step 4: Get SSL Certificate ──
echo -e "${CYAN}[4/8] Setting up SSL certificate...${NC}"

# First, start nginx without SSL to get the certificate
echo -e "${YELLOW}Starting temporary nginx for ACME challenge...${NC}"

# Create temp nginx config for initial cert
mkdir -p /tmp/nginx-init
cat > /tmp/nginx-init/default.conf << 'INITEOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 'PlagSini EV - Setting up...';
        add_header Content-Type text/plain;
    }
}
INITEOF

# Run temp nginx
docker run -d --name temp-nginx \
    -p 80:80 \
    -v /tmp/nginx-init/default.conf:/etc/nginx/conf.d/default.conf:ro \
    -v plagsini_certbot-webroot:/var/www/certbot \
    nginx:1.25-alpine

sleep 3

# Get certificate
docker run --rm \
    -v plagsini_certbot-webroot:/var/www/certbot \
    -v plagsini_certbot-certs:/etc/letsencrypt \
    certbot/certbot certonly \
    --webroot -w /var/www/certbot \
    --email "$EMAIL_SSL" \
    --agree-tos --no-eff-email \
    -d "$DOMAIN"

# Stop temp nginx
docker stop temp-nginx && docker rm temp-nginx
rm -rf /tmp/nginx-init

echo -e "${GREEN}✅ SSL certificate obtained for $DOMAIN${NC}"

# ── Step 5: Build Services ──
echo -e "${CYAN}[5/8] Building all services...${NC}"
docker compose -f docker-compose.prod.yml build --no-cache
echo -e "${GREEN}✅ All services built${NC}"

# ── Step 6: Start Services ──
echo -e "${CYAN}[6/8] Starting all services...${NC}"
docker compose -f docker-compose.prod.yml up -d
echo -e "${GREEN}✅ All services started${NC}"

# ── Step 7: Wait for health ──
echo -e "${CYAN}[7/8] Waiting for services to be healthy...${NC}"
sleep 15

# Check services
echo -e "  MySQL:    $(docker inspect --format='{{.State.Health.Status}}' plagsini-mysql 2>/dev/null || echo 'checking...')"
echo -e "  API:      $(docker inspect --format='{{.State.Status}}' plagsini-api 2>/dev/null || echo 'checking...')"
echo -e "  Bot:      $(docker inspect --format='{{.State.Status}}' plagsini-bot 2>/dev/null || echo 'checking...')"
echo -e "  Web:      $(docker inspect --format='{{.State.Status}}' plagsini-web 2>/dev/null || echo 'checking...')"
echo -e "  Nginx:    $(docker inspect --format='{{.State.Status}}' plagsini-nginx 2>/dev/null || echo 'checking...')"

# ── Step 8: Setup auto-backup ──
echo -e "${CYAN}[8/8] Setting up daily MySQL backup...${NC}"

mkdir -p /opt/plagsini/backups

# Create backup script
cat > /opt/plagsini/backup.sh << 'BACKEOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/plagsini/backups"
docker exec plagsini-mysql mysqldump -u root -p${MYSQL_ROOT_PASSWORD} charging_platform > "$BACKUP_DIR/backup_$DATE.sql"
# Keep only last 7 days
find "$BACKUP_DIR" -name "backup_*.sql" -mtime +7 -delete
echo "Backup completed: backup_$DATE.sql"
BACKEOF

chmod +x /opt/plagsini/backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null | grep -v "plagsini/backup"; echo "0 3 * * * /opt/plagsini/backup.sh >> /opt/plagsini/backups/cron.log 2>&1") | crontab -

echo -e "${GREEN}✅ Daily backup scheduled at 3:00 AM${NC}"

# ── Done! ──
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      🎉 DEPLOYMENT COMPLETE! 🎉         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐 App:       ${CYAN}https://$DOMAIN${NC}"
echo -e "  📊 Admin:     ${CYAN}https://$DOMAIN/login${NC}"
echo -e "  🤖 Bot:       ${CYAN}https://$DOMAIN/bot/${NC}"
echo -e "  🔌 API:       ${CYAN}https://$DOMAIN/api/${NC}"
echo -e "  ⚡ OCPP:      ${CYAN}wss://$DOMAIN:9000${NC}"
echo ""
echo -e "${YELLOW}📋 Quick Commands:${NC}"
echo -e "  docker compose -f docker-compose.prod.yml logs -f     # View logs"
echo -e "  docker compose -f docker-compose.prod.yml ps          # Status"
echo -e "  docker compose -f docker-compose.prod.yml restart     # Restart all"
echo -e "  /opt/plagsini/backup.sh                               # Manual backup"
echo ""
