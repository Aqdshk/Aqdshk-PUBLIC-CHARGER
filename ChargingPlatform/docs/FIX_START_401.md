# Fix: Start Button 401 Unauthorized

## Punca
Request `/api/charging/start` dapat 401 kerana header `X-Staff-Token` tidak sampai ke backend.

## Penyelesaian

### 1. Pastikan Nginx hantar header X-Staff-Token

Edit `/etc/nginx/sites-available/default` dan tambah dalam block `location` yang proxy ke backend:

```nginx
proxy_set_header X-Staff-Token $http_x_staff_token;
```

Contoh (dalam block `location /` untuk HTTPS):

```nginx
location / {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Staff-Token $http_x_staff_token;   # <-- TAMBAH INI
}
```

### 2. Test & reload Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Rebuild & deploy ChargingPlatform

```bash
cd /opt/plagsini-ev
git pull
docker compose -f docker-compose.prod.yml build charging-platform --no-cache
docker compose -f docker-compose.prod.yml up -d charging-platform --force-recreate
```

### 4. Log out & log in semula

1. Klik Sign Out di dashboard
2. Log in semula
3. Hard refresh (Ctrl+Shift+R) pada halaman Chargers / Operations
4. Cuba tekan Start

### 5. Perubahan terkini (fallback token)

- Operations page kini hantar token dalam **query string** (`?token=xxx`) sebagai sandaran jika header `X-Staff-Token` tidak sampai (e.g. Nginx strip header)
- Gunakan `STAFF_AUTH?.token` sebagai fallback jika `localStorage` kosong
- Jika tiada token semasa Remote Start/Stop, user akan diarah ke `/login`
