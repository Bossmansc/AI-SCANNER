#!/bin/bash

# =============================================================================
# CodeCraft AI - Environment Setup Script
# Purpose: Create .env file from template with interactive configuration
# =============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ENV_TEMPLATE=".env.template"
ENV_FILE=".env"
BACKUP_DIR=".env_backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}  CodeCraft AI Environment Setup${NC}"
    echo -e "${CYAN}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_step() {
    echo -e "\n${MAGENTA}▶ $1${NC}"
}

# Check if template exists
check_template() {
    if [ ! -f "$ENV_TEMPLATE" ]; then
        print_error "Template file '$ENV_TEMPLATE' not found!"
        echo "Please ensure the template exists in the current directory."
        exit 1
    fi
    print_success "Found template: $ENV_TEMPLATE"
}

# Backup existing .env file
backup_env() {
    if [ -f "$ENV_FILE" ]; then
        print_step "Backing up existing .env file"
        
        # Create backup directory if it doesn't exist
        mkdir -p "$BACKUP_DIR"
        
        # Create backup
        BACKUP_FILE="$BACKUP_DIR/.env.backup_$TIMESTAMP"
        cp "$ENV_FILE" "$BACKUP_FILE"
        
        print_success "Backup created: $BACKUP_FILE"
        
        # List recent backups
        echo -e "\nRecent backups:"
        ls -lt "$BACKUP_DIR"/*.backup_* 2>/dev/null | head -5 | awk '{print "  " $9}' || true
    fi
}

# Validate required tools
validate_dependencies() {
    print_step "Checking dependencies"
    
    local missing_deps=0
    
    # Check for required commands
    for cmd in grep sed awk; do
        if ! command -v $cmd &> /dev/null; then
            print_error "Required command '$cmd' not found"
            missing_deps=1
        else
            print_success "$cmd is available"
        fi
    done
    
    if [ $missing_deps -eq 1 ]; then
        print_error "Missing required dependencies. Please install them and try again."
        exit 1
    fi
}

# Extract variables from template
extract_variables() {
    print_step "Extracting configuration variables"
    
    # Extract all variable names from template (lines with VAR=value pattern)
    VARIABLES=$(grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_TEMPLATE" | cut -d'=' -f1 | sort)
    
    # Count variables
    VAR_COUNT=$(echo "$VARIABLES" | wc -l)
    print_success "Found $VAR_COUNT configuration variables"
    
    echo "$VARIABLES"
}

# Get variable descriptions from template comments
get_variable_description() {
    local var_name="$1"
    
    # Look for comment lines before the variable definition
    local line_num=$(grep -n "^$var_name=" "$ENV_TEMPLATE" | cut -d':' -f1)
    
    if [ -n "$line_num" ]; then
        # Get the line before the variable (potential comment)
        local prev_line=$((line_num - 1))
        
        if [ $prev_line -gt 0 ]; then
            local comment=$(sed -n "${prev_line}p" "$ENV_TEMPLATE" | grep -E '^#')
            if [ -n "$comment" ]; then
                # Remove # and trim
                echo "$comment" | sed 's/^#\s*//'
            fi
        fi
    fi
}

# Get default value from template
get_default_value() {
    local var_name="$1"
    
    # Extract the entire line and get value after =
    grep "^$var_name=" "$ENV_TEMPLATE" | cut -d'=' -f2-
}

# Prompt user for variable value
prompt_for_value() {
    local var_name="$1"
    local description="$2"
    local default_value="$3"
    
    echo -e "\n${BLUE}▸ $var_name${NC}"
    
    if [ -n "$description" ]; then
        echo -e "  ${YELLOW}$description${NC}"
    fi
    
    if [ -n "$default_value" ]; then
        echo -e "  Default: ${GREEN}$default_value${NC}"
        read -p "  Enter value [press Enter for default]: " user_value
    else
        read -p "  Enter value: " user_value
    fi
    
    # Use default if user didn't enter anything
    if [ -z "$user_value" ] && [ -n "$default_value" ]; then
        user_value="$default_value"
    fi
    
    echo "$user_value"
}

# Generate .env file
generate_env_file() {
    print_step "Generating .env file"
    
    # Create temporary file
    TEMP_FILE=$(mktemp)
    
    # Process template line by line
    while IFS= read -r line; do
        # Check if line is a variable definition
        if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            default_value="${BASH_REMATCH[2]}"
            
            # Get user value from collected responses
            user_value="${USER_VALUES[$var_name]}"
            
            # Write the variable with user value or default
            if [ -n "$user_value" ]; then
                echo "$var_name=$user_value" >> "$TEMP_FILE"
            else
                echo "$var_name=$default_value" >> "$TEMP_FILE"
            fi
        else
            # Copy comments and empty lines as-is
            echo "$line" >> "$TEMP_FILE"
        fi
    done < "$ENV_TEMPLATE"
    
    # Move temp file to final location
    mv "$TEMP_FILE" "$ENV_FILE"
    
    print_success "Generated $ENV_FILE"
}

# Validate generated .env file
validate_env_file() {
    print_step "Validating generated .env file"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file was not created!"
        exit 1
    fi
    
    # Check for empty required values (if any)
    local empty_vars=$(grep -E '^[A-Z_][A-Z0-9_]*=$' "$ENV_FILE" || true)
    
    if [ -n "$empty_vars" ]; then
        print_warning "Some variables are empty:"
        echo "$empty_vars" | sed 's/^/  /'
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Restarting configuration..."
            return 1
        fi
    fi
    
    print_success ".env file validation passed"
    return 0
}

# Show summary of configured values
show_summary() {
    print_step "Configuration Summary"
    
    echo -e "\n${CYAN}Configured Environment Variables:${NC}"
    echo "========================================"
    
    # Show non-empty variables
    grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" | while read -r line; do
        var_name=$(echo "$line" | cut -d'=' -f1)
        var_value=$(echo "$line" | cut -d'=' -f2-)
        
        # Mask sensitive values
        if [[ "$var_name" =~ (PASSWORD|SECRET|KEY|TOKEN) ]]; then
            var_value="********"
        fi
        
        echo -e "${BLUE}$var_name${NC}=${GREEN}$var_value${NC}"
    done
    
    # Count variables
    local total_vars=$(grep -c '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE")
    local non_empty_vars=$(grep -c '^[A-Z_][A-Z0-9_]*=[^[:space:]]' "$ENV_FILE")
    
    echo -e "\n${CYAN}Statistics:${NC}"
    echo "  Total variables: $total_vars"
    echo "  Non-empty variables: $non_empty_vars"
}

# Interactive mode: prompt for each variable
interactive_mode() {
    print_step "Interactive Configuration Mode"
    print_info "You will be prompted for each configuration variable."
    print_info "Press Enter to accept default values shown in green.\n"
    
    # Array to store user responses
    declare -A USER_VALUES
    
    # Get all variables
    local variables=$(extract_variables)
    
    # Prompt for each variable
    while IFS= read -r var_name; do
        [ -z "$var_name" ] && continue
        
        local description=$(get_variable_description "$var_name")
        local default_value=$(get_default_value "$var_name")
        
        local user_value=$(prompt_for_value "$var_name" "$description" "$default_value")
        USER_VALUES["$var_name"]="$user_value"
    done <<< "$variables"
    
    # Generate .env file with collected values
    generate_env_file
    
    # Validate and show summary
    if validate_env_file; then
        show_summary
    else
        # Restart if validation failed
        interactive_mode
    fi
}

# Quick mode: use all defaults
quick_mode() {
    print_step "Quick Setup Mode"
    print_info "Using all default values from template.\n"
    
    # Copy template to .env
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    
    print_success "Created $ENV_FILE with default values"
    show_summary
}

# Edit mode: open in editor
edit_mode() {
    print_step "Editor Mode"
    
    # First copy template if .env doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
    fi
    
    # Check for available editors
    local editor=""
    for ed in nano vim vi; do
        if command -v $ed &> /dev/null; then
            editor=$ed
            break
        fi
    done
    
    if [ -z "$editor" ]; then
        print_error "No text editor found (tried: nano, vim, vi)"
        print_info "Please install nano or vim, or use interactive mode."
        exit 1
    fi
    
    print_info "Opening $ENV_FILE in $editor..."
    $editor "$ENV_FILE"
    
    # Validate after editing
    if validate_env_file; then
        show_summary
    else
        print_error "Validation failed after editing"
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo -e "${CYAN}Usage:${NC}"
    echo "  $0 [OPTION]"
    echo ""
    echo "${CYAN}Options:${NC}"
    echo "  -i, --interactive  Interactive mode (default)"
    echo "  -q, --quick        Quick mode (use all defaults)"
    echo "  -e, --edit         Edit existing .env file"
    echo "  -b, --backup-only  Only backup existing .env"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "${CYAN}Examples:${NC}"
    echo "  $0                 # Interactive setup"
    echo "  $0 --quick         # Quick setup with defaults"
    echo "  $0 --edit          # Edit existing .env file"
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    local mode="interactive"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--interactive)
                mode="interactive"
                shift
                ;;
            -q|--quick)
                mode="quick"
                shift
                ;;
            -e|--edit)
                mode="edit"
                shift
                ;;
            -b|--backup-only)
                mode="backup"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    print_header
    
    # Validate dependencies
    validate_dependencies
    
    # Check template exists
    check_template
    
    # Backup existing .env
    backup_env
    
    # Execute selected mode
    case $mode in
        interactive)
            interactive_mode
            ;;
        quick)
            quick_mode
            ;;
        edit)
            edit_mode
            ;;
        backup)
            print_success "Backup completed. No .env file was created/modified."
            exit 0
            ;;
    esac
    
    # Final instructions
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "\n${CYAN}Next steps:${NC}"
    echo "  1. Review the generated $ENV_FILE"
    echo "  2. Run your application with the new configuration"
    echo "  3. To modify settings, run: $0 --edit"
    echo -e "\n${YELLOW}Note:${NC} Sensitive values (passwords, keys) are masked in the summary above."
}

# Handle script interruption
cleanup() {
    echo -e "\n${YELLOW}Setup interrupted. Cleaning up...${NC}"
    
    # Remove temporary files if they exist
    rm -f "$ENV_FILE.tmp" 2>/dev/null || true
    
    exit 1
}

# Set up trap for cleanup
trap cleanup INT TERM

# Run main function
main "$@"
