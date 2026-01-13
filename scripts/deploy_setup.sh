#!/bin/bash

# =============================================================================
# DEPLOYMENT SETUP SCRIPT
# =============================================================================
# Purpose: Automated setup and configuration for production deployment
# Features:
#   - Environment validation
#   - Dependency installation
#   - Database migration
#   - Service configuration
#   - Security hardening
#   - Health checks
# =============================================================================

set -e  # Exit on any error
set -u  # Treat unset variables as errors

# =============================================================================
# CONFIGURATION
# =============================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script version
SCRIPT_VERSION="2.1.0"
DEPLOYMENT_ID="$(date +%Y%m%d_%H%M%S)"

# Default paths
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${BASE_DIR}/config"
LOG_DIR="${BASE_DIR}/logs"
BACKUP_DIR="${BASE_DIR}/backups"
VENV_DIR="${BASE_DIR}/venv"
REQUIREMENTS_FILE="${BASE_DIR}/requirements.txt"

# Deployment environment (override with DEPLOY_ENV env var)
DEPLOY_ENV="${DEPLOY_ENV:-production}"

# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

log_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE} STEP: $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

validate_environment() {
    log_step "Validating Deployment Environment"
    
    # Check if running as root (not recommended for production)
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root user. Consider using a dedicated deployment user."
    fi
    
    # Check OS compatibility
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot determine OS distribution"
        return 1
    fi
    
    source /etc/os-release
    log_info "Detected OS: $NAME $VERSION"
    
    # Check for required system tools
    local required_tools=("git" "python3" "pip3" "curl" "wget" "tar" "gzip")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    # Check Python version
    local python_version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_info "Python version: $python_version"
    
    if [[ $(echo "$python_version < 3.8" | bc -l 2>/dev/null) -eq 1 ]]; then
        log_error "Python 3.8 or higher is required"
        return 1
    fi
    
    # Check available disk space (minimum 1GB)
    local available_space
    available_space=$(df -k "$BASE_DIR" | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 1048576 ]]; then
        log_warning "Low disk space available: $((available_space / 1024))MB"
    fi
    
    # Check memory (minimum 512MB)
    local total_memory
    total_memory=$(free -m | awk '/^Mem:/{print $2}')
    if [[ $total_memory -lt 512 ]]; then
        log_warning "Low memory available: ${total_memory}MB"
    fi
    
    log_success "Environment validation passed"
    return 0
}

validate_configuration() {
    log_step "Validating Configuration Files"
    
    local required_configs=(
        "${CONFIG_DIR}/${DEPLOY_ENV}.env"
        "${CONFIG_DIR}/database.yml"
        "${CONFIG_DIR}/services.yml"
    )
    
    for config in "${required_configs[@]}"; do
        if [[ ! -f "$config" ]]; then
            log_error "Missing configuration file: $config"
            return 1
        fi
        
        # Check if config file is readable
        if [[ ! -r "$config" ]]; then
            log_error "Cannot read configuration file: $config"
            return 1
        fi
        
        log_info "Found configuration: $(basename "$config")"
    done
    
    # Validate .env file has required variables
    if [[ -f "${CONFIG_DIR}/${DEPLOY_ENV}.env" ]]; then
        local required_vars=("DATABASE_URL" "SECRET_KEY" "ALLOWED_HOSTS")
        for var in "${required_vars[@]}"; do
            if ! grep -q "^${var}=" "${CONFIG_DIR}/${DEPLOY_ENV}.env"; then
                log_warning "Missing environment variable: $var"
            fi
        done
    fi
    
    log_success "Configuration validation passed"
    return 0
}

# =============================================================================
# SETUP FUNCTIONS
# =============================================================================

setup_directories() {
    log_step "Setting Up Directory Structure"
    
    local directories=(
        "$LOG_DIR"
        "$BACKUP_DIR"
        "${BACKUP_DIR}/database"
        "${BACKUP_DIR}/config"
        "${BASE_DIR}/static"
        "${BASE_DIR}/media"
        "${BASE_DIR}/temp"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            chmod 755 "$dir"
            log_info "Created directory: $dir"
        else
            log_info "Directory exists: $dir"
        fi
    done
    
    # Set proper permissions
    chmod 750 "$LOG_DIR"
    chmod 700 "$BACKUP_DIR"
    
    log_success "Directory structure created"
}

setup_virtualenv() {
    log_step "Setting Up Python Virtual Environment"
    
    if [[ -d "$VENV_DIR" ]]; then
        log_info "Virtual environment already exists at $VENV_DIR"
        log_info "Removing old virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    
    log_info "Creating new virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
        log_error "Failed to create virtual environment"
        return 1
    fi
    
    # Activate virtual environment
    source "${VENV_DIR}/bin/activate"
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    
    log_success "Virtual environment created at $VENV_DIR"
    return 0
}

install_dependencies() {
    log_step "Installing Dependencies"
    
    if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
        log_error "Requirements file not found: $REQUIREMENTS_FILE"
        return 1
    fi
    
    source "${VENV_DIR}/bin/activate"
    
    log_info "Installing from $REQUIREMENTS_FILE..."
    
    # Install production dependencies
    if [[ "$DEPLOY_ENV" == "production" ]]; then
        pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
    else
        # For staging/development, include dev dependencies if available
        if [[ -f "${BASE_DIR}/requirements-dev.txt" ]]; then
            pip install --no-cache-dir -r "${BASE_DIR}/requirements-dev.txt"
        else
            pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
        fi
    fi
    
    # Verify critical packages
    local critical_packages=("gunicorn" "psycopg2-binary" "redis" "celery")
    for package in "${critical_packages[@]}"; do
        if pip show "$package" &> /dev/null; then
            log_info "Verified package: $package"
        else
            log_warning "Package not installed: $package"
        fi
    done
    
    log_success "Dependencies installed successfully"
    return 0
}

setup_database() {
    log_step "Setting Up Database"
    
    source "${VENV_DIR}/bin/activate"
    source "${CONFIG_DIR}/${DEPLOY_ENV}.env"
    
    # Check if database URL is set
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not set in environment"
        return 1
    fi
    
    log_info "Database URL configured"
    
    # Run database migrations
    log_info "Running database migrations..."
    
    if [[ -f "${BASE_DIR}/manage.py" ]]; then
        # Django project
        python "${BASE_DIR}/manage.py" migrate --noinput
        python "${BASE_DIR}/manage.py" collectstatic --noinput
        
        # Create superuser if in development/staging
        if [[ "$DEPLOY_ENV" != "production" ]]; then
            log_info "Creating default superuser for non-production environment..."
            echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin@example.com', 'admin', 'admin123') if not User.objects.filter(email='admin@example.com').exists() else None" | python "${BASE_DIR}/manage.py" shell || true
        fi
    elif [[ -f "${BASE_DIR}/alembic.ini" ]]; then
        # Alembic migrations
        alembic upgrade head
    else
        log_warning "No migration system detected, skipping migrations"
    fi
    
    # Create database backup
    log_info "Creating initial database backup..."
    local backup_file="${BACKUP_DIR}/database/initial_${DEPLOYMENT_ID}.sql"
    
    # Extract database info from URL
    if [[ "$DATABASE_URL" == postgresql://* ]]; then
        # PostgreSQL backup
        if command -v pg_dump &> /dev/null; then
            # Parse PostgreSQL URL
            local dbname
            dbname=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/.*\/\(.*\)$/\1/p' | cut -d'?' -f1)
            pg_dump "$dbname" > "$backup_file" 2>/dev/null || true
        fi
    fi
    
    if [[ -f "$backup_file" ]] && [[ -s "$backup_file" ]]; then
        log_info "Database backup created: $(basename "$backup_file")"
    fi
    
    log_success "Database setup completed"
    return 0
}

configure_services() {
    log_step "Configuring System Services"
    
    local service_templates=(
        "${CONFIG_DIR}/templates/gunicorn.service"
        "${CONFIG_DIR}/templates/celery.service"
        "${CONFIG_DIR}/templates/celerybeat.service"
    )
    
    local service_dir="/etc/systemd/system"
    
    # Check if we have sudo privileges for service installation
    if [[ $EUID -ne 0 ]] && [[ ! -w "$service_dir" ]]; then
        log_warning "Cannot install system services without root privileges"
        log_info "Service configuration files will be generated in $BASE_DIR/systemd/"
        service_dir="${BASE_DIR}/systemd"
        mkdir -p "$service_dir"
    fi
    
    # Process each service template
    for template in "${service_templates[@]}"; do
        if [[ ! -f "$template" ]]; then
            log_warning "Service template not found: $template"
            continue
        fi
        
        local service_name
        service_name=$(basename "$template")
        local output_file="${service_dir}/${service_name}"
        
        # Replace template variables
        sed \
            -e "s|{{BASE_DIR}}|$BASE_DIR|g" \
            -e "s|{{VENV_DIR}}|$VENV_DIR|g" \
            -e "s|{{DEPLOY_ENV}}|$DEPLOY_ENV|g" \
            -e "s|{{USER}}|$(whoami)|g" \
            "$template" > "$output_file"
        
        chmod 644 "$output_file"
        log_info "Generated service file: $output_file"
        
        # If running as root, enable the service
        if [[ $EUID -eq 0 ]] && [[ "$service_dir" == "/etc/systemd/system" ]]; then
            systemctl daemon-reload
            systemctl enable "${service_name}" 2>/dev/null || true
            log_info "Enabled service: ${service_name%.*}"
        fi
    done
    
    # Configure nginx if template exists
    if [[ -f "${CONFIG_DIR}/templates/nginx.conf" ]] && [[ $EUID -eq 0 ]]; then
        local nginx_conf="/etc/nginx/sites-available/$(basename "$BASE_DIR")"
        cp "${CONFIG_DIR}/templates/nginx.conf" "$nginx_conf"
        
        # Create symlink if doesn't exist
        if [[ ! -L "/etc/nginx/sites-enabled/$(basename "$BASE_DIR")" ]]; then
            ln -s "$nginx_conf" "/etc/nginx/sites-enabled/"
        fi
        
        # Test nginx configuration
        if nginx -t &> /dev/null; then
            systemctl reload nginx
            log_info "Nginx configuration updated"
        else
            log_warning "Nginx configuration test failed"
        fi
    fi
    
    log_success "Service configuration completed"
    return 0
}

setup_security() {
    log_step "Configuring Security Settings"
    
    # Set proper file permissions
    log_info "Setting file permissions..."
    
    # Make sensitive files readable only by owner
    local sensitive_files=(
        "${CONFIG_DIR}/${DEPLOY_ENV}.env"
        "${CONFIG_DIR}/database.yml"
        "${BACKUP_DIR}"/*
    )
    
    for file in "${sensitive_files[@]}"; do
        if [[ -f "$file" ]]; then
            chmod 600 "$file"
            log_info "Secured file: $(basename "$file")"
        fi
    done
    
    # Secure the virtual environment
    if [[ -d "$VENV_DIR" ]]; then
        chmod -R 750 "$VENV_DIR"
    fi
    
    # Configure firewall (if running as root)
    if [[ $EUID -eq 0 ]] && command -v ufw &> /dev/null; then
        log_info "Configuring firewall..."
        ufw allow ssh
        ufw allow http
        ufw allow https
        ufw --force enable 2>/dev/null || true
    fi
    
    # Set up fail2ban if available
    if [[ $EUID -eq 0 ]] && command -v fail2ban-client &> /dev/null; then
        log_info "Configuring fail2ban..."
        systemctl enable fail2ban 2>/dev/null || true
        systemctl start fail2ban 2>/dev/null || true
    fi
    
    # Create deployment user if running as root
    if [[ $EUID -eq 0 ]] && [[ "$DEPLOY_ENV" == "production" ]]; then
        local deploy_user="deploy"
        if ! id "$deploy_user" &> /dev/null; then
            log_info "Creating deployment user: $deploy_user"
            useradd -m -s /bin/bash "$deploy_user"
            usermod -aG sudo "$deploy_user"
            
            # Set up SSH keys
            mkdir -p "/home/$deploy_user/.ssh"
            chmod 700 "/home/$deploy_user/.ssh"
            
            # Copy authorized keys from current user if available
            if [[ -f ~/.ssh/authorized_keys ]]; then
                cp ~/.ssh/authorized_keys "/home/$deploy_user/.ssh/"
                chown -R "$deploy_user:$deploy_user" "/home/$deploy_user/.ssh"
            fi
        fi
    fi
    
    log_success "Security configuration completed"
    return 0
}

create_backup() {
    log_step "Creating Deployment Backup"
    
    local backup_path="${BACKUP_DIR}/deployment_${DEPLOYMENT_ID}.tar.gz"
    
    log_info "Creating backup of current deployment..."
    
    # Exclude unnecessary directories from backup
    tar --exclude="venv" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude="*.pyo" \
        --exclude=".git" \
        --exclude="node_modules" \
        --exclude="*.log" \
        -czf "$backup_path" \
        -C "$BASE_DIR" .
    
    if [[ -f "$backup_path" ]]; then
        local backup_size
        backup_size=$(du -h "$backup_path" | cut -f1)
        log_info "Backup created: $(basename "$backup_path") (${backup_size})"
        
        # Keep only last 5 backups
        find "$BACKUP_DIR" -name "deployment_*.tar.gz" -type f | sort -r | tail -n +6 | xargs rm -f 2>/dev/null || true
    else
        log_warning "Failed to create backup"
    fi
    
    return 0
}

run_health_check() {
    log_step "Running Health Checks"
    
    local health_passed