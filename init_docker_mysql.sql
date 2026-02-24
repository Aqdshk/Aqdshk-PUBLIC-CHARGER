-- Create customer_service database and grant access
CREATE DATABASE IF NOT EXISTS customer_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON customer_service.* TO 'charging_user'@'%';
FLUSH PRIVILEGES;
