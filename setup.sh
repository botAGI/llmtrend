#!/usr/bin/env bash
# ============================================================================
# AI Trend Monitor -- Setup Wizard
# ============================================================================
# Interactive setup script that configures Docker, Ollama, Telegram,
# API tokens, scheduling, and generates a .env file.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
# ============================================================================

set -euo pipefail

# ── ANSI Colors ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# ── Helper functions ─────────────────────────────────────────────────────────

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_ok() {
    echo -e "  ${GREEN}[OK]${NC} $1"
}

print_warn() {
    echo -e "  ${YELLOW}[!!]${NC} $1"
}

print_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
}

print_skip() {
    echo -e "  ${CYAN}[SKIP]${NC} $1"
}

print_info() {
    echo -e "  ${CYAN}[i]${NC} $1"
}

confirm() {
    local prompt="${1:-Продолжить?}"
    local default="${2:-y}"
    local answer

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    echo -en "  ${YELLOW}${prompt}${NC}"
    read -r answer
    answer="${answer:-$default}"

    case "$answer" in
        [Yy]|[Yy][Ee][Ss]|[Дд]|[Дд][Аа]) return 0 ;;
        *) return 1 ;;
    esac
}

# ── State variables ──────────────────────────────────────────────────────────
OS=""
ARCH=""
DOCKER_OK=false
DOCKER_COMPOSE_OK=false
GIT_OK=false
OLLAMA_ENABLED=false
OLLAMA_MODEL="llama3.1:8b"
OLLAMA_BASE_URL="http://ollama:11434"
OLLAMA_MODE=""
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
TELEGRAM_ENABLED=false
HUGGINGFACE_TOKEN=""
GITHUB_TOKEN=""
COLLECTION_SCHEDULE_HOURS=6
POSTGRES_PASSWORD=""
REDIS_PASSWORD=""
SECRET_KEY=""
APP_API_KEY=""

# ── ASCII header ─────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}"
cat << 'BANNER'
     _    ___   _____                    _
    / \  |_ _| |_   _| _ __  ___  _ __ | |_
   / _ \  | |    | |  | '__|/ _ \| '_ \| __|
  / ___ \ | |    | |  | |  |  __/| | | | |_
 /_/   \_\|___|  |_|  |_|   \___||_| |_|\__|

  __  __                _  _
 |  \/  | ___   _ __   (_)| |_  ___   _ __
 | |\/| |/ _ \ | '_ \  | || __|/ _ \ | '__|
 | |  | | (_) || | | | | || |_| (_) || |
 |_|  |_|\___/ |_| |_| |_| \__|\___/ |_|

BANNER
echo -e "${NC}"
echo -e "${BOLD}  AI Trend Monitor -- Setup Wizard${NC}"
echo -e "  Интерактивная настройка проекта"
echo ""
echo -e "  Этот скрипт поможет настроить все компоненты:"
echo -e "  - Docker и Docker Compose"
echo -e "  - Git"
echo -e "  - Ollama (локальный LLM)"
echo -e "  - Telegram-бот"
echo -e "  - API-токены (HuggingFace, GitHub)"
echo -e "  - Расписание сбора данных"
echo -e "  - Генерация файла .env"
echo ""

if ! confirm "Начать настройку?"; then
    echo ""
    echo -e "  Настройка отменена."
    exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 0: Detect OS and architecture
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 0: Определение системы"

case "$(uname -s)" in
    Linux*)   OS="linux" ;;
    Darwin*)  OS="macos" ;;
    MINGW*|CYGWIN*|MSYS*)
        OS="windows"
        print_warn "Windows обнаружена. Рекомендуется использовать setup.ps1."
        print_warn "Продолжение в совместимом режиме (Git Bash / WSL)."
        ;;
    *)
        OS="unknown"
        print_warn "Неизвестная ОС: $(uname -s)"
        ;;
esac

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    armv7l)  ARCH="armv7" ;;
esac

print_ok "ОС: ${OS}"
print_ok "Архитектура: ${ARCH}"

# Detect GPU (NVIDIA)
HAS_NVIDIA_GPU=false
if command -v nvidia-smi &>/dev/null; then
    HAS_NVIDIA_GPU=true
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    print_ok "NVIDIA GPU обнаружена: ${GPU_INFO}"
elif [[ "$OS" == "macos" ]] && [[ "$ARCH" == "arm64" ]]; then
    print_info "Apple Silicon обнаружен (GPU Metal доступен для Ollama)."
else
    print_info "NVIDIA GPU не обнаружена. Ollama будет работать на CPU."
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 1: Check Docker + Docker Compose
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 1: Docker и Docker Compose"

# Check Docker
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>/dev/null | sed 's/Docker version //' | cut -d',' -f1)
    print_ok "Docker установлен: v${DOCKER_VERSION}"
    DOCKER_OK=true

    # Check if Docker daemon is running
    if docker info &>/dev/null; then
        print_ok "Docker daemon запущен."
    else
        print_fail "Docker daemon не запущен."
        print_info "Запустите Docker Desktop или systemctl start docker."
        if [[ "$OS" == "linux" ]]; then
            if confirm "Попробовать запустить Docker (sudo systemctl start docker)?"; then
                sudo systemctl start docker
                if docker info &>/dev/null; then
                    print_ok "Docker daemon успешно запущен."
                else
                    print_fail "Не удалось запустить Docker daemon."
                fi
            fi
        elif [[ "$OS" == "macos" ]]; then
            if confirm "Попробовать запустить Docker Desktop?"; then
                open -a Docker 2>/dev/null || true
                print_info "Ожидание запуска Docker Desktop (до 30 секунд)..."
                for i in $(seq 1 30); do
                    if docker info &>/dev/null; then
                        print_ok "Docker Desktop запущен."
                        break
                    fi
                    sleep 1
                done
                if ! docker info &>/dev/null; then
                    print_warn "Docker Desktop не запустился. Продолжаем настройку."
                fi
            fi
        fi
    fi
else
    print_fail "Docker не установлен."
    DOCKER_OK=false

    if [[ "$OS" == "linux" ]]; then
        print_info "Для установки Docker на Linux выполните:"
        echo ""
        echo "    curl -fsSL https://get.docker.com | sh"
        echo "    sudo usermod -aG docker \$USER"
        echo ""
        if confirm "Установить Docker автоматически?"; then
            print_info "Запуск установки Docker..."
            if curl -fsSL https://get.docker.com | sh; then
                sudo usermod -aG docker "$USER" 2>/dev/null || true
                print_ok "Docker установлен."
                print_warn "Вам может потребоваться перелогиниться для применения группы docker."
                DOCKER_OK=true
            else
                print_fail "Ошибка установки Docker."
            fi
        fi
    elif [[ "$OS" == "macos" ]]; then
        print_info "Установите Docker Desktop: https://docs.docker.com/desktop/install/mac-install/"
        if command -v brew &>/dev/null; then
            if confirm "Установить Docker Desktop через Homebrew?"; then
                if brew install --cask docker; then
                    print_ok "Docker Desktop установлен. Запустите его из Applications."
                    DOCKER_OK=true
                else
                    print_fail "Ошибка установки через Homebrew."
                fi
            fi
        fi
    fi
fi

# Check Docker Compose
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version 2>/dev/null | sed 's/.*v//' | cut -d' ' -f1)
    print_ok "Docker Compose (plugin): v${COMPOSE_VERSION}"
    DOCKER_COMPOSE_OK=true
elif command -v docker-compose &>/dev/null; then
    COMPOSE_VERSION=$(docker-compose --version 2>/dev/null | sed 's/.*version //' | cut -d',' -f1)
    print_ok "Docker Compose (standalone): v${COMPOSE_VERSION}"
    print_warn "Рекомендуется перейти на docker compose plugin (V2)."
    DOCKER_COMPOSE_OK=true
else
    print_fail "Docker Compose не найден."
    DOCKER_COMPOSE_OK=false
    if [[ "$DOCKER_OK" == true ]]; then
        print_info "Docker Compose V2 обычно входит в Docker Desktop."
        print_info "Для Linux: sudo apt install docker-compose-plugin"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 2: Check Git
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 2: Git"

if command -v git &>/dev/null; then
    GIT_VERSION=$(git --version 2>/dev/null | sed 's/git version //')
    print_ok "Git установлен: v${GIT_VERSION}"
    GIT_OK=true
else
    print_fail "Git не установлен."
    GIT_OK=false

    if [[ "$OS" == "linux" ]]; then
        if confirm "Установить Git?"; then
            if command -v apt &>/dev/null; then
                sudo apt update && sudo apt install -y git
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y git
            elif command -v yum &>/dev/null; then
                sudo yum install -y git
            elif command -v pacman &>/dev/null; then
                sudo pacman -S --noconfirm git
            else
                print_warn "Неизвестный пакетный менеджер. Установите git вручную."
            fi
            if command -v git &>/dev/null; then
                GIT_OK=true
                print_ok "Git успешно установлен."
            fi
        fi
    elif [[ "$OS" == "macos" ]]; then
        print_info "Установите Xcode Command Line Tools: xcode-select --install"
        if confirm "Установить через xcode-select?"; then
            xcode-select --install 2>/dev/null || true
            print_info "Следуйте инструкциям установщика."
        fi
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 3: Ollama setup (optional)
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 3: Ollama (локальный LLM)"

echo -e "  Ollama позволяет запускать LLM локально для анализа трендов."
echo -e "  Это опционально -- проект работает и без AI-анализа."
echo ""

if confirm "Включить Ollama для AI-анализа?" "y"; then
    OLLAMA_ENABLED=true

    # Model selection
    echo ""
    echo -e "  ${BOLD}Выберите модель:${NC}"
    echo -e "    ${CYAN}1)${NC} llama3.1:8b   (по умолчанию, ~4.7 GB, хороший баланс)"
    echo -e "    ${CYAN}2)${NC} llama3.2:3b   (~2 GB, быстрая, меньше качество)"
    echo -e "    ${CYAN}3)${NC} mistral:7b    (~4.1 GB, альтернатива)"
    echo -e "    ${CYAN}4)${NC} gemma2:9b     (~5.4 GB, от Google)"
    echo -e "    ${CYAN}5)${NC} qwen2.5:7b    (~4.4 GB, от Alibaba)"
    echo -e "    ${CYAN}6)${NC} Другая (ввести вручную)"
    echo ""
    echo -en "  ${YELLOW}Выбор [1-6, по умолчанию 1]: ${NC}"
    read -r model_choice
    model_choice="${model_choice:-1}"

    case "$model_choice" in
        1) OLLAMA_MODEL="llama3.1:8b" ;;
        2) OLLAMA_MODEL="llama3.2:3b" ;;
        3) OLLAMA_MODEL="mistral:7b" ;;
        4) OLLAMA_MODEL="gemma2:9b" ;;
        5) OLLAMA_MODEL="qwen2.5:7b" ;;
        6)
            echo -en "  ${YELLOW}Введите название модели (напр. phi3:mini): ${NC}"
            read -r custom_model
            if [[ -n "$custom_model" ]]; then
                OLLAMA_MODEL="$custom_model"
            else
                OLLAMA_MODEL="llama3.1:8b"
                print_warn "Пустой ввод. Используем llama3.1:8b."
            fi
            ;;
        *)
            OLLAMA_MODEL="llama3.1:8b"
            print_warn "Неверный выбор. Используем llama3.1:8b."
            ;;
    esac

    print_ok "Выбрана модель: ${OLLAMA_MODEL}"

    # Mode selection
    echo ""
    echo -e "  ${BOLD}Режим работы Ollama:${NC}"
    echo -e "    ${CYAN}1)${NC} Docker контейнер (по умолчанию, из docker-compose)"
    echo -e "    ${CYAN}2)${NC} Локальная установка (уже установлен на хосте)"
    echo -e "    ${CYAN}3)${NC} Удалённый сервер (ввести URL)"
    echo -e "    ${CYAN}4)${NC} Установить Ollama на хост сейчас"
    echo ""
    echo -en "  ${YELLOW}Выбор [1-4, по умолчанию 1]: ${NC}"
    read -r ollama_mode
    ollama_mode="${ollama_mode:-1}"

    case "$ollama_mode" in
        1)
            OLLAMA_MODE="docker"
            OLLAMA_BASE_URL="http://ollama:11434"
            print_ok "Ollama будет запущен в Docker контейнере."
            if [[ "$HAS_NVIDIA_GPU" == true ]]; then
                print_info "Обнаружена NVIDIA GPU."
                print_info "Для GPU-ускорения раскомментируйте секцию deploy в docker-compose.yml."
            fi
            ;;
        2)
            OLLAMA_MODE="local"
            if command -v ollama &>/dev/null; then
                OLLAMA_VERSION=$(ollama --version 2>/dev/null | tail -1 || echo "unknown")
                print_ok "Ollama найден: ${OLLAMA_VERSION}"
                OLLAMA_BASE_URL="http://host.docker.internal:11434"

                # Check if ollama is running
                if curl -sf http://localhost:11434/api/tags &>/dev/null; then
                    print_ok "Ollama сервер запущен."

                    # Check if model is available
                    if curl -sf http://localhost:11434/api/tags 2>/dev/null | grep -q "\"${OLLAMA_MODEL}\""; then
                        print_ok "Модель ${OLLAMA_MODEL} уже загружена."
                    else
                        print_warn "Модель ${OLLAMA_MODEL} не найдена."
                        if confirm "Загрузить модель ${OLLAMA_MODEL}?"; then
                            print_info "Загрузка ${OLLAMA_MODEL}... (это может занять несколько минут)"
                            if ollama pull "$OLLAMA_MODEL"; then
                                print_ok "Модель ${OLLAMA_MODEL} загружена."
                            else
                                print_fail "Ошибка загрузки модели."
                            fi
                        fi
                    fi
                else
                    print_warn "Ollama сервер не запущен."
                    print_info "Запустите: ollama serve"
                fi
            else
                print_fail "Ollama не найден в PATH."
                print_warn "Переключаемся на Docker-режим."
                OLLAMA_MODE="docker"
                OLLAMA_BASE_URL="http://ollama:11434"
            fi
            ;;
        3)
            OLLAMA_MODE="remote"
            echo -en "  ${YELLOW}Введите URL Ollama (напр. http://192.168.1.100:11434): ${NC}"
            read -r remote_url
            if [[ -n "$remote_url" ]]; then
                OLLAMA_BASE_URL="$remote_url"
                # Test connection
                print_info "Проверка подключения к ${OLLAMA_BASE_URL}..."
                if curl -sf "${OLLAMA_BASE_URL}/api/tags" &>/dev/null; then
                    print_ok "Подключение к Ollama успешно."
                else
                    print_warn "Не удалось подключиться к ${OLLAMA_BASE_URL}."
                    print_info "Убедитесь, что Ollama доступен по этому адресу."
                fi
            else
                print_warn "Пустой URL. Используем Docker-режим."
                OLLAMA_MODE="docker"
                OLLAMA_BASE_URL="http://ollama:11434"
            fi
            ;;
        4)
            OLLAMA_MODE="install"
            print_info "Установка Ollama..."
            if [[ "$OS" == "linux" ]]; then
                if confirm "Установить Ollama через официальный скрипт?"; then
                    if curl -fsSL https://ollama.com/install.sh | sh; then
                        print_ok "Ollama установлен."
                        OLLAMA_BASE_URL="http://host.docker.internal:11434"
                        OLLAMA_MODE="local"

                        # Start ollama serve in background
                        print_info "Запуск Ollama..."
                        ollama serve &>/dev/null &
                        sleep 3

                        if curl -sf http://localhost:11434/api/tags &>/dev/null; then
                            print_ok "Ollama сервер запущен."
                            if confirm "Загрузить модель ${OLLAMA_MODEL}?"; then
                                print_info "Загрузка ${OLLAMA_MODEL}..."
                                ollama pull "$OLLAMA_MODEL" || print_warn "Ошибка загрузки модели."
                            fi
                        else
                            print_warn "Не удалось запустить Ollama."
                        fi
                    else
                        print_fail "Ошибка установки Ollama."
                        print_warn "Переключаемся на Docker-режим."
                        OLLAMA_MODE="docker"
                        OLLAMA_BASE_URL="http://ollama:11434"
                    fi
                fi
            elif [[ "$OS" == "macos" ]]; then
                print_info "Скачайте Ollama: https://ollama.com/download/mac"
                if command -v brew &>/dev/null; then
                    if confirm "Установить Ollama через Homebrew?"; then
                        if brew install ollama; then
                            print_ok "Ollama установлен."
                            OLLAMA_BASE_URL="http://host.docker.internal:11434"
                            OLLAMA_MODE="local"
                            print_info "Запустите: ollama serve"
                            print_info "Затем: ollama pull ${OLLAMA_MODEL}"
                        else
                            print_fail "Ошибка установки."
                            OLLAMA_MODE="docker"
                            OLLAMA_BASE_URL="http://ollama:11434"
                        fi
                    fi
                else
                    print_warn "Homebrew не найден. Скачайте Ollama вручную."
                    OLLAMA_MODE="docker"
                    OLLAMA_BASE_URL="http://ollama:11434"
                fi
            else
                print_warn "Автоматическая установка недоступна для ${OS}."
                OLLAMA_MODE="docker"
                OLLAMA_BASE_URL="http://ollama:11434"
            fi
            ;;
        *)
            OLLAMA_MODE="docker"
            OLLAMA_BASE_URL="http://ollama:11434"
            print_warn "Неверный выбор. Используем Docker-режим."
            ;;
    esac
else
    OLLAMA_ENABLED=false
    print_skip "Ollama отключен. AI-анализ не будет доступен."
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 4: Telegram Bot
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 4: Telegram-бот"

echo -e "  Telegram-бот позволяет получать уведомления о трендах"
echo -e "  и управлять сбором данных прямо из мессенджера."
echo ""
echo -e "  Для создания бота:"
echo -e "    1. Откройте @BotFather в Telegram"
echo -e "    2. Отправьте /newbot"
echo -e "    3. Следуйте инструкциям и скопируйте токен"
echo ""

if confirm "Настроить Telegram-бот?" "y"; then
    # Token input
    while true; do
        echo -en "  ${YELLOW}Введите токен бота (формат 123456:ABC-DEF...): ${NC}"
        read -r bot_token

        if [[ -z "$bot_token" ]]; then
            print_warn "Токен не введён."
            if confirm "Пропустить настройку Telegram?" "n"; then
                print_skip "Telegram-бот пропущен."
                break
            fi
            continue
        fi

        # Validate format
        if [[ ! "$bot_token" =~ ^[0-9]+:.+$ ]]; then
            print_fail "Неверный формат токена. Ожидается: 123456:ABC-DEF..."
            continue
        fi

        # Test via Telegram API
        print_info "Проверка токена через Telegram API..."
        response=$(curl -sf "https://api.telegram.org/bot${bot_token}/getMe" 2>/dev/null || echo "")

        if echo "$response" | grep -q '"ok":true'; then
            bot_name=$(echo "$response" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
            print_ok "Бот найден: @${bot_name}"
            TELEGRAM_BOT_TOKEN="$bot_token"
            TELEGRAM_ENABLED=true
        else
            print_warn "Не удалось проверить токен (возможно, нет интернета)."
            if confirm "Использовать этот токен всё равно?"; then
                TELEGRAM_BOT_TOKEN="$bot_token"
                TELEGRAM_ENABLED=true
            else
                continue
            fi
        fi

        # Chat ID
        echo ""
        echo -e "  ${BOLD}Идентификатор чата (Chat ID):${NC}"
        echo -e "  Чтобы узнать свой Chat ID:"
        echo -e "    1. Напишите боту /start в Telegram"
        echo -e "    2. Откройте: https://api.telegram.org/bot<TOKEN>/getUpdates"
        echo -e "    3. Найдите значение chat.id"
        echo ""
        echo -en "  ${YELLOW}Введите Chat ID (или Enter для пропуска): ${NC}"
        read -r chat_id

        if [[ -n "$chat_id" ]]; then
            TELEGRAM_CHAT_ID="$chat_id"
            print_ok "Chat ID сохранён: ${chat_id}"
        else
            print_skip "Chat ID не указан. Укажите позже в .env (TELEGRAM_ALLOWED_USERS)."
        fi

        break
    done
else
    TELEGRAM_ENABLED=false
    print_skip "Telegram-бот пропущен."
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 5: API Tokens
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 5: API-токены (опционально)"

echo -e "  API-токены улучшают сбор данных, но не обязательны."
echo -e "  Без них сбор будет работать с ограничениями."
echo ""

# HuggingFace
echo -e "  ${BOLD}HuggingFace:${NC}"
echo -e "  Для доступа к расширенной статистике моделей."
echo -e "  Получить: https://huggingface.co/settings/tokens"
echo ""
echo -en "  ${YELLOW}Введите HuggingFace токен (hf_...) или Enter для пропуска: ${NC}"
read -r hf_token

if [[ -n "$hf_token" ]]; then
    if [[ "$hf_token" == hf_* ]]; then
        HUGGINGFACE_TOKEN="$hf_token"
        print_ok "HuggingFace токен сохранён."
    else
        print_warn "Токен не начинается с hf_. Возможно, неверный формат."
        if confirm "Использовать этот токен?"; then
            HUGGINGFACE_TOKEN="$hf_token"
        else
            print_skip "HuggingFace токен пропущен."
        fi
    fi
else
    print_skip "HuggingFace токен пропущен."
fi

echo ""

# GitHub
echo -e "  ${BOLD}GitHub:${NC}"
echo -e "  Для сбора данных о AI-репозиториях (повышает лимит API)."
echo -e "  Получить: https://github.com/settings/tokens"
echo ""
echo -en "  ${YELLOW}Введите GitHub токен или Enter для пропуска: ${NC}"
read -r gh_token

if [[ -n "$gh_token" ]]; then
    GITHUB_TOKEN="$gh_token"
    print_ok "GitHub токен сохранён."
else
    print_skip "GitHub токен пропущен."
fi

# ══════════════════════════════════════════════════════════════════════════════
# Step 6: Collection schedule
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 6: Расписание сбора данных"

echo -e "  Как часто собирать новые данные о трендах?"
echo ""
echo -e "    ${CYAN}1)${NC} Каждые 4 часа  (чаще всего обновлений)"
echo -e "    ${CYAN}2)${NC} Каждые 6 часов (по умолчанию, рекомендуется)"
echo -e "    ${CYAN}3)${NC} Каждые 12 часов (экономия ресурсов)"
echo -e "    ${CYAN}4)${NC} Каждые 24 часа  (один раз в сутки)"
echo ""
echo -en "  ${YELLOW}Выбор [1-4, по умолчанию 2]: ${NC}"
read -r schedule_choice
schedule_choice="${schedule_choice:-2}"

case "$schedule_choice" in
    1) COLLECTION_SCHEDULE_HOURS=4  ;;
    2) COLLECTION_SCHEDULE_HOURS=6  ;;
    3) COLLECTION_SCHEDULE_HOURS=12 ;;
    4) COLLECTION_SCHEDULE_HOURS=24 ;;
    *)
        COLLECTION_SCHEDULE_HOURS=6
        print_warn "Неверный выбор. Используем 6 часов."
        ;;
esac

print_ok "Расписание: каждые ${COLLECTION_SCHEDULE_HOURS} часов."

# ══════════════════════════════════════════════════════════════════════════════
# Step 7: Generate .env file
# ══════════════════════════════════════════════════════════════════════════════
print_header "Шаг 7: Генерация .env файла"

# Generate passwords
print_info "Генерация безопасных паролей..."
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
APP_API_KEY=$(openssl rand -hex 24)

print_ok "Пароли сгенерированы."

# Backup existing .env
ENV_FILE=".env"
if [[ -f "$ENV_FILE" ]]; then
    BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$ENV_FILE" "$BACKUP_FILE"
    print_warn "Существующий .env сохранён как ${BACKUP_FILE}"
fi

# Determine Ollama values for .env
if [[ "$OLLAMA_ENABLED" == true ]]; then
    ENV_OLLAMA_ENABLED="true"
else
    ENV_OLLAMA_ENABLED="false"
fi

# Determine Telegram values for .env
if [[ "$TELEGRAM_ENABLED" == true ]]; then
    ENV_TELEGRAM_ENABLED="true"
else
    ENV_TELEGRAM_ENABLED="false"
fi

# Build TELEGRAM_ALLOWED_USERS
TELEGRAM_ALLOWED_USERS=""
if [[ -n "$TELEGRAM_CHAT_ID" ]]; then
    TELEGRAM_ALLOWED_USERS="$TELEGRAM_CHAT_ID"
fi

# Write .env
cat > "$ENV_FILE" << ENVFILE
# ============================================================================
# AI Trend Monitor - Environment Configuration
# ============================================================================
# Generated by setup.sh on $(date '+%Y-%m-%d %H:%M:%S')
#
# SECURITY: Never commit this file to version control.
# ============================================================================

# ── Database (PostgreSQL) ──────────────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ai_trends
POSTGRES_USER=monitor
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── FastAPI ────────────────────────────────────────────────────────────────
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=INFO
APP_API_KEY=${APP_API_KEY}
APP_CORS_ORIGINS=["http://localhost:8501"]
APP_WORKERS=1

# ── Celery ─────────────────────────────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# ── HuggingFace ────────────────────────────────────────────────────────────
HUGGINGFACE_TOKEN=${HUGGINGFACE_TOKEN}
HF_MODELS_LIMIT=200
HF_REQUEST_TIMEOUT=30

# ── GitHub ─────────────────────────────────────────────────────────────────
GITHUB_TOKEN=${GITHUB_TOKEN}
GITHUB_MIN_STARS=50
GITHUB_RESULTS_PER_PAGE=100
GITHUB_MAX_PAGES=5
GITHUB_REQUEST_TIMEOUT=30

# ── arXiv ──────────────────────────────────────────────────────────────────
ARXIV_MAX_RESULTS=500
ARXIV_REQUEST_DELAY=3.0
ARXIV_REQUEST_TIMEOUT=60
ARXIV_CATEGORIES=["cs.AI","cs.LG","cs.CL","cs.CV","cs.NE"]

# ── Ollama (LLM inference) ────────────────────────────────────────────────
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
OLLAMA_MODEL=${OLLAMA_MODEL}
OLLAMA_ENABLED=${ENV_OLLAMA_ENABLED}
OLLAMA_TIMEOUT=120
OLLAMA_TEMPERATURE=0.3

# ── Telegram Bot ───────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
TELEGRAM_ADMIN_USERS=${TELEGRAM_ALLOWED_USERS}
TELEGRAM_ENABLED=${ENV_TELEGRAM_ENABLED}

# ── Scheduler ──────────────────────────────────────────────────────────────
COLLECTION_SCHEDULE_HOURS=${COLLECTION_SCHEDULE_HOURS}
ANALYTICS_SCHEDULE_HOURS=12

# ── General ────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
ENVIRONMENT=production
SECRET_KEY=${SECRET_KEY}

# ── Reports ────────────────────────────────────────────────────────────────
REPORTS_OUTPUT_DIR=/app/reports
REPORTS_MAX_AGE_DAYS=90

# ── Docker Compose port overrides ──────────────────────────────────────────
# DASHBOARD_PORT=8501
# POSTGRES_EXTERNAL_PORT=5432
# REDIS_EXTERNAL_PORT=6379
ENVFILE

print_ok "Файл .env создан."

# ══════════════════════════════════════════════════════════════════════════════
# Final summary
# ══════════════════════════════════════════════════════════════════════════════
print_header "Итоговый отчёт"

echo -e "  ${BOLD}Компонент              Статус${NC}"
echo -e "  ─────────────────────────────────────────"

# Docker
if [[ "$DOCKER_OK" == true ]]; then
    echo -e "  Docker                ${GREEN}Установлен${NC}"
else
    echo -e "  Docker                ${RED}Не установлен${NC}"
fi

# Docker Compose
if [[ "$DOCKER_COMPOSE_OK" == true ]]; then
    echo -e "  Docker Compose        ${GREEN}Установлен${NC}"
else
    echo -e "  Docker Compose        ${RED}Не установлен${NC}"
fi

# Git
if [[ "$GIT_OK" == true ]]; then
    echo -e "  Git                   ${GREEN}Установлен${NC}"
else
    echo -e "  Git                   ${RED}Не установлен${NC}"
fi

# Ollama
if [[ "$OLLAMA_ENABLED" == true ]]; then
    echo -e "  Ollama                ${GREEN}Включён (${OLLAMA_MODE}, ${OLLAMA_MODEL})${NC}"
else
    echo -e "  Ollama                ${YELLOW}Отключён${NC}"
fi

# Telegram
if [[ "$TELEGRAM_ENABLED" == true ]]; then
    echo -e "  Telegram-бот          ${GREEN}Настроен${NC}"
else
    echo -e "  Telegram-бот          ${YELLOW}Не настроен${NC}"
fi

# HuggingFace
if [[ -n "$HUGGINGFACE_TOKEN" ]]; then
    echo -e "  HuggingFace токен     ${GREEN}Указан${NC}"
else
    echo -e "  HuggingFace токен     ${YELLOW}Не указан${NC}"
fi

# GitHub
if [[ -n "$GITHUB_TOKEN" ]]; then
    echo -e "  GitHub токен          ${GREEN}Указан${NC}"
else
    echo -e "  GitHub токен          ${YELLOW}Не указан${NC}"
fi

# Schedule
echo -e "  Сбор данных           ${CYAN}Каждые ${COLLECTION_SCHEDULE_HOURS}ч${NC}"

# .env
echo -e "  .env файл             ${GREEN}Создан${NC}"

echo ""
echo -e "  ─────────────────────────────────────────"
echo ""

# Show warnings
if [[ "$DOCKER_OK" == false ]] || [[ "$DOCKER_COMPOSE_OK" == false ]]; then
    print_warn "Docker/Docker Compose не установлены. Установите перед запуском."
fi

if [[ "$OLLAMA_ENABLED" == true ]] && [[ "$OLLAMA_MODE" == "local" ]]; then
    print_info "Не забудьте запустить Ollama: ollama serve"
fi

echo ""
echo -e "  ${BOLD}${GREEN}Настройка завершена!${NC}"
echo ""
echo -e "  Следующий шаг -- запуск проекта:"
echo ""
echo -e "    ${CYAN}make up${NC}        -- запустить все сервисы"
echo -e "    ${CYAN}make logs${NC}      -- посмотреть логи"
echo -e "    ${CYAN}make status${NC}    -- статус сервисов"
echo -e "    ${CYAN}make help${NC}      -- все доступные команды"
echo ""
echo -e "  Дашборд будет доступен: ${CYAN}http://localhost:8501${NC}"
echo -e "  API будет доступен:     ${CYAN}http://localhost:8000${NC}"
echo ""
