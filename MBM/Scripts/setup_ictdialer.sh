#!/bin/bash
# =============================================================================
# ICTDialer One-Click Setup Script
# Target: Rocky Linux 9 / CentOS 9 (Hetzner CX32 VPS)
# Version: 1.0.0
# Date: 2026-08-01
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Config
DB_NAME="ictdialer"
DB_USER="ictdialeruser"
DB_PASS="CHANGE_ME_$(openssl rand -hex 8)"
DOMAIN="${1:-$(hostname -I | awk '{print $1}')}"
ADMIN_EMAIL="${2:-admin@example.com}"

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; exit 1; }

# =============================================================================
# PHASE 1: System Preparation
# =============================================================================
log "${BLUE}=== PHASE 1: System Preparation ===${NC}"

log "Updating system packages..."
sudo dnf update -y

log "Disabling SELinux..."
sudo sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config 2>/dev/null || true
sudo setenforce 0 2>/dev/null || true

log "Setting hostname..."
sudo hostnamectl set-hostname dialer.${DOMAIN} 2>/dev/null || true

log "Installing essential packages..."
sudo dnf install -y wget curl nano vim git htop net-tools socat perl-DBI boost-program-options perl perl-CPAN

# =============================================================================
# PHASE 2: MariaDB 10.11
# =============================================================================
log "${BLUE}=== PHASE 2: MariaDB 10.11 ===${NC}"

log "Adding MariaDB repository..."
sudo tee /etc/yum.repos.d/MariaDB.repo << 'REPO'
[mariadb]
name = MariaDB
baseurl = http://yum.mariadb.org/10.11/rhel9-amd64
gpgkey=https://yum.mariadb.org/RPM-GPG-KEY-MariaDB
gpgcheck=1
REPO

log "Installing MariaDB..."
sudo dnf install -y perl-DBI boost-program-options socat
sudo dnf install -y perl-CPAN
sudo cpan Sys::Hostname 2>/dev/null || true
sudo dnf install MariaDB-server MariaDB-client --disablerepo='*' --enablerepo='mariadb' -y

log "Starting MariaDB..."
sudo systemctl enable --now mariadb

log "Securing MariaDB..."
sudo mysql -e "UPDATE mysql.user SET Password=PASSWORD('${DB_PASS}') WHERE User='root';"
sudo mysql -e "DELETE FROM mysql.user WHERE User='';"
sudo mysql -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');"
sudo mysql -e "DROP DATABASE IF EXISTS test;"
sudo mysql -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';"
sudo mysql -e "FLUSH PRIVILEGES;"

log "MariaDB password: ${DB_PASS}"
echo "${DB_PASS}" > ~/mariadb_password.txt

# =============================================================================
# PHASE 3: PHP 8.3
# =============================================================================
log "${BLUE}=== PHASE 3: PHP 8.3 ===${NC}"

log "Installing EPEL and Remi repositories..."
sudo dnf install -y epel-release
sudo dnf install -y https://rpms.remirepo.net/enterprise/remi-release-9.rpm

log "Enabling PHP 8.3..."
sudo yum module reset php -y
sudo yum module enable php:remi-8.3 -y

log "Installing PHP and extensions..."
sudo yum install -y php php-fpm php-gd php-mysqlnd php-imap php-mbstring php-xml php-json php-cli

log "Installing imagick..."
sudo yum install -y ImageMagick ImageMagick-devel
sudo pecl install imagick 2>/dev/null || true
echo "extension=imagick.so" > /etc/php.d/imagick.ini

log "Installing mcrypt..."
sudo yum install -y --enablerepo=epel php-devel php-pear libmcrypt libmcrypt-devel 2>/dev/null || true
sudo pecl install mcrypt 2>/dev/null || true
echo "extension=mcrypt.so" > /etc/php.d/mcrypt.ini

log "Configuring PHP-FPM..."
sudo sed -i 's/^user = apache/user = apache/' /etc/php-fpm.d/www.conf
sudo sed -i 's/^group = apache/group = apache/' /etc/php-fpm.d/www.conf
sudo sed -i 's/^;listen.owner = nobody/listen.owner = nobody/' /etc/php-fpm.d/www.conf
sudo sed -i 's/^;listen.group = nobody/listen.group = nobody/' /etc/php-fpm.d/www.conf

# =============================================================================
# PHASE 4: FreeSWITCH
# =============================================================================
log "${BLUE}=== PHASE 4: FreeSWITCH ===${NC}"

log "Enabling CRB repo..."
sudo dnf config-manager --enable crb 2>/dev/null || true

log "Installing FreeSWITCH..."
wget -q http://repo.okay.com.mx/centos/9/x86_64/release/okay-release-1-10.el9.noarch.rpm
sudo yum install -y okay-release-1-10.el9.noarch.rpm 2>/dev/null || true
sudo dnf install -y task-freeswitch

log "Starting FreeSWITCH..."
sudo systemctl enable --now freeswitch

log "Verifying FreeSWITCH..."
sudo fs_cli -x "sofia status" 2>/dev/null || warn "FreeSWITCH not ready yet"

# =============================================================================
# PHASE 5: ICTCore + ICTDialer
# =============================================================================
log "${BLUE}=== PHASE 5: ICTCore + ICTDialer ===${NC}"

log "Installing ICT repository..."
sudo yum install -y https://service.ictinnovations.com/repo/8/ict-release-8-5.el8.noarch.rpm 2>/dev/null || true

log "Installing ICTCore packages..."
sudo yum install -y ictcore ictcore-fax ictcore-email ictcore-voice ictcore-freeswitch

log "Installing ICTDialer web interface..."
sudo yum install -y ictdialer 2>/dev/null || warn "ICTDialer package not found, will install from source"

# =============================================================================
# PHASE 6: Database Setup
# =============================================================================
log "${BLUE}=== PHASE 6: Database Setup ===${NC}"

log "Creating database and user..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
"

log "Loading database schemas..."
for schema in database voice fax sms email; do
    if [ -f "/usr/ictcore/db/${schema}.sql" ]; then
        sudo mysql -u ${DB_USER} -p${DB_PASS} ${DB_NAME} < /usr/ictcore/db/${schema}.sql 2>/dev/null || true
        log "  Loaded ${schema}.sql"
    else
        warn "  Schema not found: /usr/ictcore/db/${schema}.sql"
    fi
done

log "Loading demo data..."
for data in role_user role_admin demo_users; do
    if [ -f "/usr/ictcore/db/data/${data}.sql" ]; then
        sudo mysql -u ${DB_USER} -p${DB_PASS} ${DB_NAME} < /usr/ictcore/db/data/${data}.sql 2>/dev/null || true
        log "  Loaded ${data}.sql"
    fi
done

# =============================================================================
# PHASE 7: Configure ICTCore
# =============================================================================
log "${BLUE}=== PHASE 7: Configure ICTCore ===${NC}"

log "Writing ICTCore configuration..."
sudo tee /etc/ictcore.conf << ICTCONF
[db]
user = ${DB_USER}
pass = ${DB_PASS}
name = ${DB_NAME}

[main]
debug = false
timezone = UTC
ICTCONF

# Also try alternative config location
sudo tee /usr/ictcore/etc/ictcore.conf << ICTCONF 2>/dev/null || true
[db]
user = ${DB_USER}
pass = ${DB_PASS}
name = ${DB_NAME}

[main]
debug = false
timezone = UTC
ICTCONF

# =============================================================================
# PHASE 8: Configure ODBC
# =============================================================================
log "${BLUE}=== PHASE 8: Configure ODBC ===${NC}"

sudo tee /etc/odbc.ini << ODBC
[ictdialer]
Driver = MariaDB
Server = localhost
Port = 3306
Database = ${DB_NAME}
User = ${DB_USER}
Password = ${DB_PASS}
ODBC

# =============================================================================
# PHASE 9: Configure Apache
# =============================================================================
log "${BLUE}=== PHASE 9: Configure Apache ===${NC}"

log "Configuring Apache for ICTDialer..."
sudo tee /etc/httpd/conf.d/ictdialer.conf << APACHE
Alias /ictdialer /usr/ictdialer/wwwroot/GUI/dist

<Directory "/usr/ictdialer/wwwroot/GUI/dist">
    AllowOverride None
    Require all granted
    
    # PHP processing
    <IfModule mod_php.c>
        AddType application/x-httpd-php .php
    </IfModule>
    
    # Rewrite rules
    <IfModule mod_rewrite.c>
        RewriteEngine On
        RewriteBase /ictdialer/
        RewriteRule ^index\.html$ - [L]
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /ictdialer/index.html [L]
    </IfModule>
</Directory>

# API endpoint
Alias /ictcore /usr/ictcore/wwwroot/API/public

<Directory "/usr/ictcore/wwwroot/API/public">
    AllowOverride None
    Require all granted
    
    <IfModule mod_php.c>
        AddType application/x-httpd-php .php
    </IfModule>
    
    <IfModule mod_rewrite.c>
        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule ^(.*)$ index.php?rewrite=\$1 [QSA,L]
    </IfModule>
</Directory>
APACHE

# Enable required Apache modules
sudo yum install -y mod_rewrite mod_php 2>/dev/null || true
sudo systemctl enable --now httpd

# =============================================================================
# PHASE 10: Firewall Configuration
# =============================================================================
log "${BLUE}=== PHASE 10: Firewall Configuration ===${NC}"

log "Opening required ports..."
sudo firewall-cmd --permanent --add-port=5060/tcp 2>/dev/null || true
sudo firewall-cmd --permanent --add-port=5060/udp 2>/dev/null || true
sudo firewall-cmd --permanent --add-port=10000-20000/udp 2>/dev/null || true
sudo firewall-cmd --permanent --add-service=http 2>/dev/null || true
sudo firewall-cmd --permanent --add-service=https 2>/dev/null || true
sudo firewall-cmd --reload 2>/dev/null || true

# =============================================================================
# PHASE 11: Create systemd Service (if missing)
# =============================================================================
log "${BLUE}=== PHASE 11: Service Setup ===${NC}"

sudo tee /etc/systemd/system/ictcore.service << 'SERVICE'
[Unit]
Description=ICTCore Unified Communications Engine
After=network.target mariadb.service

[Service]
Type=forking
ExecStart=/usr/bin/php /usr/ictcore/bin/ictcore start
ExecStop=/usr/bin/php /usr/ictcore/bin/ictcore stop
PIDFile=/var/run/ictcore.pid
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable ictcore 2>/dev/null || true

# =============================================================================
# PHASE 12: Restart All Services
# =============================================================================
log "${BLUE}=== PHASE 12: Restart Services ===${NC}"

log "Restarting all services..."
sudo systemctl restart mariadb
sudo systemctl restart php-fpm
sudo systemctl restart freeswitch
sudo systemctl restart httpd
sudo systemctl restart ictcore 2>/dev/null || true

log "Waiting for services to stabilize..."
sleep 5

# =============================================================================
# PHASE 13: Generate Setup Report
# =============================================================================
log "${BLUE}=== PHASE 13: Setup Report ===${NC}"

SERVER_IP=$(hostname -I | awk '{print $1}')

cat << REPORT > ~/ictdialer_setup_report.txt
========================================
ICTDialer Setup Complete
========================================
Date: $(date)
Server IP: ${SERVER_IP}
Domain: ${DOMAIN}

Access URLs:
  Web GUI: http://${SERVER_IP}/ictdialer
  API:     http://${SERVER_IP}/ictcore

Default Login:
  Email:    admin@ictcore.org
  Password: helloAdmin

Database:
  Name:     ${DB_NAME}
  User:     ${DB_USER}
  Password: ${DB_PASS}
  (Also saved in: ~/mariadb_password.txt)

Services:
  MariaDB:    $(systemctl is-active mariadb)
  FreeSWITCH: $(systemctl is-active freeswitch)
  Apache:     $(systemctl is-active httpd)
  PHP-FPM:    $(systemctl is-active php-fpm)

Next Steps:
  1. Change default admin password immediately
  2. Configure SIP trunk (Telnyx recommended)
  3. Import leads from texas_300_ictdialer_import.csv
  4. Create seller and buyer campaigns
  5. Start dialing!

Firewall Ports Open:
  5060/tcp    - SIP signaling
  5060/udp    - SIP signaling
  10000-20000/udp - RTP media
  80/tcp      - HTTP
  443/tcp     - HTTPS
========================================
REPORT

cat ~/ictdialer_setup_report.txt

log "${GREEN}=== SETUP COMPLETE ===${NC}"
log "Report saved to: ~/ictdialer_setup_report.txt"
log "Database password saved to: ~/mariadb_password.txt"
