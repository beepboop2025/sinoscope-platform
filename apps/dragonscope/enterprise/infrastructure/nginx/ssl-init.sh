#!/bin/bash
#
# DragonScope Enterprise SSL Certificate Initialization
# Automates Let's Encrypt certificate provisioning with Certbot
#

set -e

# Configuration
DOMAINS=("api.dragonscope.io" "app.dragonscope.io" "admin.dragonscope.io")
EMAIL="ops@dragonscope.io"
STAGING=${STAGING:-0}
CERT_DIR="/etc/letsencrypt/live"
NGINX_CONF_DIR="/etc/nginx/conf.d"
WEBROOT="/var/www/certbot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
}

# Install Certbot if not present
install_certbot() {
    if ! command -v certbot &> /dev/null; then
        log "Installing Certbot..."
        
        # Detect OS
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            OS=$NAME
        else
            error "Cannot detect OS"
            exit 1
        fi
        
        case $OS in
            "Ubuntu"|"Debian GNU/Linux")
                apt-get update
                apt-get install -y certbot python3-certbot-nginx
                ;;
            "CentOS Linux"|"Red Hat Enterprise Linux"|"Amazon Linux")
                yum install -y certbot python3-certbot-nginx
                ;;
            "Alpine Linux")
                apk add --no-cache certbot
                ;;
            *)
                error "Unsupported OS: $OS"
                exit 1
                ;;
        esac
    else
        log "Certbot already installed"
    fi
}

# Create webroot directory for ACME challenges
setup_webroot() {
    log "Setting up webroot directory..."
    mkdir -p "$WEBROOT"
    chown -R nginx:nginx "$WEBROOT" 2>/dev/null || chown -R www-data:www-data "$WEBROOT"
    chmod 755 "$WEBROOT"
}

# Generate strong Diffie-Hellman parameters
generate_dhparams() {
    local dhpath="/etc/nginx/ssl/dhparam.pem"
    
    if [[ ! -f "$dhpath" ]]; then
        log "Generating DH parameters (this may take a while)..."
        mkdir -p "$(dirname "$dhpath")"
        openssl dhparam -out "$dhpath" 2048
        chmod 600 "$dhpath"
        log "DH parameters generated at $dhpath"
    else
        log "DH parameters already exist"
    fi
}

# Request certificates from Let's Encrypt
request_certificates() {
    log "Requesting certificates from Let's Encrypt..."
    
    local domain_args=""
    for domain in "${DOMAINS[@]}"; do
        domain_args="$domain_args -d $domain"
    done
    
    local staging_arg=""
    if [[ $STAGING -eq 1 ]]; then
        warn "Using Let's Encrypt staging environment"
        staging_arg="--staging"
    fi
    
    certbot certonly \
        $staging_arg \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --webroot \
        --webroot-path "$WEBROOT" \
        $domain_args \
        --rsa-key-size 4096 \
        --must-staple
    
    log "Certificates requested successfully"
}

# Setup auto-renewal
setup_renewal() {
    log "Setting up certificate auto-renewal..."
    
    # Create renewal hook script
    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    
    cat > /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh << 'EOF'
#!/bin/bash
# Reload Nginx after certificate renewal

if pgrep nginx > /dev/null; then
    echo "Reloading Nginx..."
    nginx -t && nginx -s reload
fi

# Notify monitoring (optional)
# curl -X POST "https://monitoring.dragonscope.io/webhook/cert-renewed" \
#     -H "Content-Type: application/json" \
#     -d "{\"domains\":\"$RENEWED_DOMAINS\"}"
EOF
    
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh
    
    # Setup cron job for renewal
    if command -v systemctl &> /dev/null; then
        # Use systemd timer if available
        systemctl enable certbot.timer
        systemctl start certbot.timer
    else
        # Fallback to cron
        (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet") | crontab -
    fi
    
    log "Auto-renewal configured"
}

# Verify certificate installation
verify_certificates() {
    log "Verifying certificate installation..."
    
    for domain in "${DOMAINS[@]}"; do
        local cert_path="$CERT_DIR/$domain/fullchain.pem"
        
        if [[ -f "$cert_path" ]]; then
            log "Certificate for $domain:"
            openssl x509 -in "$cert_path" -noout -subject -dates -issuer
            echo ""
        else
            error "Certificate for $domain not found at $cert_path"
        fi
    done
}

# Test SSL configuration
test_ssl() {
    log "Testing SSL configuration..."
    
    for domain in "${DOMAINS[@]}"; do
        log "Testing $domain..."
        
        # Test with SSL Labs API (optional)
        echo "SSL Labs grade: https://www.ssllabs.com/ssltest/analyze.html?d=$domain&latest"
        
        # Local test
        echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -subject -dates
    done
}

# Generate wildcard certificate using DNS challenge
generate_wildcard() {
    local domain=$1
    
    log "Generating wildcard certificate for *.$domain..."
    
    # This requires DNS provider plugin
    # Example for Route53:
    certbot certonly \
        --dns-route53 \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$domain" \
        -d "*.$domain" \
        --rsa-key-size 4096
    
    log "Wildcard certificate generated"
}

# Backup existing certificates
backup_certificates() {
    local backup_dir="/etc/letsencrypt/backup/$(date +%Y%m%d_%H%M%S)"
    
    if [[ -d "$CERT_DIR" ]]; then
        log "Backing up existing certificates to $backup_dir..."
        mkdir -p "$backup_dir"
        cp -r "$CERT_DIR" "$backup_dir/"
    fi
}

# Revoke certificate (emergency use)
revoke_certificate() {
    local domain=$1
    
    warn "Revoking certificate for $domain..."
    
    certbot revoke \
        --cert-path "$CERT_DIR/$domain/fullchain.pem" \
        --reason cessationofoperation \
        --non-interactive
    
    log "Certificate revoked"
}

# Main function
main() {
    case "${1:-setup}" in
        setup)
            check_root
            install_certbot
            setup_webroot
            generate_dhparams
            backup_certificates
            request_certificates
            setup_renewal
            verify_certificates
            test_ssl
            log "SSL setup complete!"
            ;;
        renew)
            log "Forcing certificate renewal..."
            certbot renew --force-renewal
            ;;
        test)
            test_ssl
            ;;
        wildcard)
            if [[ -z "${2:-}" ]]; then
                error "Domain required for wildcard certificate"
                echo "Usage: $0 wildcard <domain>"
                exit 1
            fi
            check_root
            generate_wildcard "$2"
            ;;
        revoke)
            if [[ -z "${2:-}" ]]; then
                error "Domain required for revocation"
                echo "Usage: $0 revoke <domain>"
                exit 1
            fi
            check_root
            revoke_certificate "$2"
            ;;
        *)
            echo "DragonScope SSL Management Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  setup              - Initial certificate setup (default)"
            echo "  renew              - Force certificate renewal"
            echo "  test               - Test SSL configuration"
            echo "  wildcard <domain>  - Generate wildcard certificate"
            echo "  revoke <domain>    - Revoke a certificate"
            echo ""
            echo "Environment Variables:"
            echo "  STAGING=1          - Use Let's Encrypt staging"
            exit 1
            ;;
    esac
}

main "$@"
