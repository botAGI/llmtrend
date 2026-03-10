# ============================================================================
# AI Trend Monitor -- Setup Wizard (Windows PowerShell)
# ============================================================================
# Interactive setup script that configures Docker, Git, Ollama, Telegram,
# API tokens, scheduling, and generates a .env file.
#
# Usage:
#   .\setup.ps1
#
# If scripts are blocked, run first:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# ============================================================================

$ErrorActionPreference = "Stop"

# ── Helper functions ─────────────────────────────────────────────────────────

function Print-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host ("=" * 62) -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host ("=" * 62) -ForegroundColor Blue
    Write-Host ""
}

function Print-Ok {
    param([string]$Message)
    Write-Host "  [OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Print-Warn {
    param([string]$Message)
    Write-Host "  [!!] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Print-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Print-Skip {
    param([string]$Message)
    Write-Host "  [SKIP] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Print-Info {
    param([string]$Message)
    Write-Host "  [i] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Confirm-Prompt {
    param(
        [string]$Prompt = "Продолжить?",
        [string]$Default = "y"
    )
    if ($Default -eq "y") {
        $suffix = "[Y/n]"
    } else {
        $suffix = "[y/N]"
    }
    Write-Host "  $Prompt $suffix : " -ForegroundColor Yellow -NoNewline
    $answer = Read-Host
    if ([string]::IsNullOrWhiteSpace($answer)) {
        $answer = $Default
    }
    return ($answer -match "^[YyДд]")
}

# ── State variables ──────────────────────────────────────────────────────────
$DockerOk = $false
$DockerComposeOk = $false
$GitOk = $false
$OllamaEnabled = $false
$OllamaModel = "llama3.1:8b"
$OllamaBaseUrl = "http://ollama:11434"
$OllamaMode = ""
$TelegramBotToken = ""
$TelegramChatId = ""
$TelegramEnabled = $false
$HuggingFaceToken = ""
$GitHubToken = ""
$CollectionScheduleHours = 6

# ── ASCII header ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host @"
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
"@ -ForegroundColor Cyan

Write-Host ""
Write-Host "  AI Trend Monitor -- Setup Wizard (Windows)" -ForegroundColor White
Write-Host "  Интерактивная настройка проекта"
Write-Host ""
Write-Host "  Этот скрипт поможет настроить все компоненты:"
Write-Host "  - Docker Desktop"
Write-Host "  - Git"
Write-Host "  - Ollama (Docker-режим)"
Write-Host "  - Telegram-бот"
Write-Host "  - API-токены (HuggingFace, GitHub)"
Write-Host "  - Расписание сбора данных"
Write-Host "  - Генерация файла .env"
Write-Host ""

if (-not (Confirm-Prompt "Начать настройку?")) {
    Write-Host ""
    Write-Host "  Настройка отменена."
    exit 0
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 0: System info
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 0: Определение системы"

$Arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "x86" }
$WinVer = [System.Environment]::OSVersion.VersionString
Print-Ok "ОС: Windows ($WinVer)"
Print-Ok "Архитектура: $Arch"

# Check NVIDIA GPU
$hasGpu = $false
try {
    $gpuInfo = (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }).Name
    if ($gpuInfo) {
        $hasGpu = $true
        Print-Ok "NVIDIA GPU обнаружена: $gpuInfo"
    } else {
        Print-Info "NVIDIA GPU не обнаружена. Ollama будет работать на CPU."
    }
} catch {
    Print-Info "Не удалось определить GPU."
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 1: Check Docker
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 1: Docker Desktop"

try {
    $dockerVer = & docker --version 2>$null
    if ($dockerVer) {
        Print-Ok "Docker установлен: $dockerVer"
        $DockerOk = $true

        # Check daemon
        try {
            $null = & docker info 2>$null
            Print-Ok "Docker daemon запущен."
        } catch {
            Print-Fail "Docker daemon не запущен. Запустите Docker Desktop."
        }
    }
} catch {
    Print-Fail "Docker не установлен."
    Print-Info "Скачайте Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
    Print-Info "Убедитесь, что WSL 2 включён."
}

# Check Docker Compose
try {
    $composeVer = & docker compose version 2>$null
    if ($composeVer) {
        Print-Ok "Docker Compose: $composeVer"
        $DockerComposeOk = $true
    }
} catch {
    Print-Fail "Docker Compose не найден."
    Print-Info "Docker Compose V2 входит в Docker Desktop."
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 2: Check Git
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 2: Git"

try {
    $gitVer = & git --version 2>$null
    if ($gitVer) {
        Print-Ok "Git установлен: $gitVer"
        $GitOk = $true
    }
} catch {
    Print-Fail "Git не установлен."
    Print-Info "Скачайте Git: https://git-scm.com/download/win"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        if (Confirm-Prompt "Установить Git через winget?") {
            try {
                & winget install --id Git.Git -e --source winget
                Print-Ok "Git установлен. Перезапустите терминал для применения PATH."
                $GitOk = $true
            } catch {
                Print-Fail "Ошибка установки Git."
            }
        }
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 3: Ollama setup
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 3: Ollama (локальный LLM)"

Write-Host "  Ollama позволяет запускать LLM локально для анализа трендов."
Write-Host "  Это опционально -- проект работает и без AI-анализа."
Write-Host ""

if (Confirm-Prompt "Включить Ollama для AI-анализа?") {
    $OllamaEnabled = $true

    # Model selection
    Write-Host ""
    Write-Host "  Выберите модель:" -ForegroundColor White
    Write-Host "    1) llama3.1:8b   (по умолчанию, ~4.7 GB)" -ForegroundColor Cyan
    Write-Host "    2) llama3.2:3b   (~2 GB, быстрая)" -ForegroundColor Cyan
    Write-Host "    3) mistral:7b    (~4.1 GB)" -ForegroundColor Cyan
    Write-Host "    4) gemma2:9b     (~5.4 GB)" -ForegroundColor Cyan
    Write-Host "    5) qwen2.5:7b    (~4.4 GB)" -ForegroundColor Cyan
    Write-Host "    6) Другая (ввести вручную)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Выбор [1-6, по умолчанию 1]: " -ForegroundColor Yellow -NoNewline
    $modelChoice = Read-Host
    if ([string]::IsNullOrWhiteSpace($modelChoice)) { $modelChoice = "1" }

    switch ($modelChoice) {
        "1" { $OllamaModel = "llama3.1:8b" }
        "2" { $OllamaModel = "llama3.2:3b" }
        "3" { $OllamaModel = "mistral:7b" }
        "4" { $OllamaModel = "gemma2:9b" }
        "5" { $OllamaModel = "qwen2.5:7b" }
        "6" {
            Write-Host "  Введите название модели: " -ForegroundColor Yellow -NoNewline
            $customModel = Read-Host
            if (-not [string]::IsNullOrWhiteSpace($customModel)) {
                $OllamaModel = $customModel
            } else {
                $OllamaModel = "llama3.1:8b"
                Print-Warn "Пустой ввод. Используем llama3.1:8b."
            }
        }
        default {
            $OllamaModel = "llama3.1:8b"
            Print-Warn "Неверный выбор. Используем llama3.1:8b."
        }
    }

    Print-Ok "Выбрана модель: $OllamaModel"

    # Mode selection -- on Windows we primarily support Docker or remote
    Write-Host ""
    Write-Host "  Режим работы Ollama:" -ForegroundColor White
    Write-Host "    1) Docker контейнер (по умолчанию, из docker-compose)" -ForegroundColor Cyan
    Write-Host "    2) Локальная установка (уже установлен)" -ForegroundColor Cyan
    Write-Host "    3) Удалённый сервер (ввести URL)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Выбор [1-3, по умолчанию 1]: " -ForegroundColor Yellow -NoNewline
    $ollamaChoice = Read-Host
    if ([string]::IsNullOrWhiteSpace($ollamaChoice)) { $ollamaChoice = "1" }

    switch ($ollamaChoice) {
        "1" {
            $OllamaMode = "docker"
            $OllamaBaseUrl = "http://ollama:11434"
            Print-Ok "Ollama будет запущен в Docker контейнере."
            if ($hasGpu) {
                Print-Info "NVIDIA GPU обнаружена."
                Print-Info "Для GPU в Docker раскомментируйте deploy секцию в docker-compose.yml."
            }
        }
        "2" {
            $OllamaMode = "local"
            $OllamaBaseUrl = "http://host.docker.internal:11434"
            try {
                $ollamaVer = & ollama --version 2>$null
                if ($ollamaVer) {
                    Print-Ok "Ollama найден: $ollamaVer"
                } else {
                    Print-Warn "Ollama не найден. Скачайте: https://ollama.com/download/windows"
                    $OllamaMode = "docker"
                    $OllamaBaseUrl = "http://ollama:11434"
                }
            } catch {
                Print-Warn "Ollama не найден. Переключаемся на Docker-режим."
                $OllamaMode = "docker"
                $OllamaBaseUrl = "http://ollama:11434"
            }
        }
        "3" {
            $OllamaMode = "remote"
            Write-Host "  Введите URL Ollama (напр. http://192.168.1.100:11434): " -ForegroundColor Yellow -NoNewline
            $remoteUrl = Read-Host
            if (-not [string]::IsNullOrWhiteSpace($remoteUrl)) {
                $OllamaBaseUrl = $remoteUrl
                Print-Info "Проверка подключения к $OllamaBaseUrl..."
                try {
                    $resp = Invoke-WebRequest -Uri "$OllamaBaseUrl/api/tags" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
                    Print-Ok "Подключение к Ollama успешно."
                } catch {
                    Print-Warn "Не удалось подключиться к $OllamaBaseUrl."
                }
            } else {
                Print-Warn "Пустой URL. Используем Docker-режим."
                $OllamaMode = "docker"
                $OllamaBaseUrl = "http://ollama:11434"
            }
        }
        default {
            $OllamaMode = "docker"
            $OllamaBaseUrl = "http://ollama:11434"
            Print-Warn "Неверный выбор. Используем Docker-режим."
        }
    }
} else {
    $OllamaEnabled = $false
    Print-Skip "Ollama отключён. AI-анализ не будет доступен."
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 4: Telegram Bot
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 4: Telegram-бот"

Write-Host "  Telegram-бот позволяет получать уведомления о трендах"
Write-Host "  и управлять сбором данных прямо из мессенджера."
Write-Host ""
Write-Host "  Для создания бота:"
Write-Host "    1. Откройте @BotFather в Telegram"
Write-Host "    2. Отправьте /newbot"
Write-Host "    3. Следуйте инструкциям и скопируйте токен"
Write-Host ""

if (Confirm-Prompt "Настроить Telegram-бот?") {
    $tokenValid = $false
    while (-not $tokenValid) {
        Write-Host "  Введите токен бота (формат 123456:ABC-DEF...): " -ForegroundColor Yellow -NoNewline
        $botToken = Read-Host

        if ([string]::IsNullOrWhiteSpace($botToken)) {
            Print-Warn "Токен не введён."
            if (Confirm-Prompt "Пропустить настройку Telegram?" "n") {
                Print-Skip "Telegram-бот пропущен."
                $tokenValid = $true
                continue
            }
            continue
        }

        # Validate format
        if ($botToken -notmatch '^\d+:.+$') {
            Print-Fail "Неверный формат токена. Ожидается: 123456:ABC-DEF..."
            continue
        }

        # Test via API
        Print-Info "Проверка токена через Telegram API..."
        try {
            $response = Invoke-RestMethod -Uri "https://api.telegram.org/bot$botToken/getMe" -UseBasicParsing -TimeoutSec 10
            if ($response.ok) {
                $botName = $response.result.username
                Print-Ok "Бот найден: @$botName"
                $TelegramBotToken = $botToken
                $TelegramEnabled = $true
            }
        } catch {
            Print-Warn "Не удалось проверить токен."
            if (Confirm-Prompt "Использовать этот токен всё равно?") {
                $TelegramBotToken = $botToken
                $TelegramEnabled = $true
            } else {
                continue
            }
        }

        # Chat ID
        Write-Host ""
        Write-Host "  Идентификатор чата (Chat ID):" -ForegroundColor White
        Write-Host "  Чтобы узнать свой Chat ID:"
        Write-Host "    1. Напишите боту /start в Telegram"
        Write-Host "    2. Откройте: https://api.telegram.org/bot<TOKEN>/getUpdates"
        Write-Host "    3. Найдите значение chat.id"
        Write-Host ""
        Write-Host "  Введите Chat ID (или Enter для пропуска): " -ForegroundColor Yellow -NoNewline
        $chatId = Read-Host
        if (-not [string]::IsNullOrWhiteSpace($chatId)) {
            $TelegramChatId = $chatId
            Print-Ok "Chat ID сохранён: $chatId"
        } else {
            Print-Skip "Chat ID не указан. Укажите позже в .env (TELEGRAM_ALLOWED_USERS)."
        }

        $tokenValid = $true
    }
} else {
    $TelegramEnabled = $false
    Print-Skip "Telegram-бот пропущен."
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 5: API Tokens
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 5: API-токены (опционально)"

Write-Host "  API-токены улучшают сбор данных, но не обязательны."
Write-Host ""

# HuggingFace
Write-Host "  HuggingFace:" -ForegroundColor White
Write-Host "  Получить: https://huggingface.co/settings/tokens"
Write-Host ""
Write-Host "  Введите HuggingFace токен (hf_...) или Enter для пропуска: " -ForegroundColor Yellow -NoNewline
$hfToken = Read-Host
if (-not [string]::IsNullOrWhiteSpace($hfToken)) {
    if ($hfToken -match '^hf_') {
        $HuggingFaceToken = $hfToken
        Print-Ok "HuggingFace токен сохранён."
    } else {
        Print-Warn "Токен не начинается с hf_."
        if (Confirm-Prompt "Использовать этот токен?") {
            $HuggingFaceToken = $hfToken
        } else {
            Print-Skip "HuggingFace токен пропущен."
        }
    }
} else {
    Print-Skip "HuggingFace токен пропущен."
}

Write-Host ""

# GitHub
Write-Host "  GitHub:" -ForegroundColor White
Write-Host "  Получить: https://github.com/settings/tokens"
Write-Host ""
Write-Host "  Введите GitHub токен или Enter для пропуска: " -ForegroundColor Yellow -NoNewline
$ghToken = Read-Host
if (-not [string]::IsNullOrWhiteSpace($ghToken)) {
    $GitHubToken = $ghToken
    Print-Ok "GitHub токен сохранён."
} else {
    Print-Skip "GitHub токен пропущен."
}

# ══════════════════════════════════════════════════════════════════════════════
# Step 6: Collection schedule
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 6: Расписание сбора данных"

Write-Host "  Как часто собирать новые данные о трендах?"
Write-Host ""
Write-Host "    1) Каждые 4 часа" -ForegroundColor Cyan
Write-Host "    2) Каждые 6 часов (по умолчанию)" -ForegroundColor Cyan
Write-Host "    3) Каждые 12 часов" -ForegroundColor Cyan
Write-Host "    4) Каждые 24 часа" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Выбор [1-4, по умолчанию 2]: " -ForegroundColor Yellow -NoNewline
$schedChoice = Read-Host
if ([string]::IsNullOrWhiteSpace($schedChoice)) { $schedChoice = "2" }

switch ($schedChoice) {
    "1" { $CollectionScheduleHours = 4 }
    "2" { $CollectionScheduleHours = 6 }
    "3" { $CollectionScheduleHours = 12 }
    "4" { $CollectionScheduleHours = 24 }
    default {
        $CollectionScheduleHours = 6
        Print-Warn "Неверный выбор. Используем 6 часов."
    }
}

Print-Ok "Расписание: каждые $CollectionScheduleHours часов."

# ══════════════════════════════════════════════════════════════════════════════
# Step 7: Generate .env file
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Шаг 7: Генерация .env файла"

# Generate passwords using .NET RNG
Print-Info "Генерация безопасных паролей..."

function New-RandomHex {
    param([int]$Bytes = 16)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] $Bytes
    $rng.GetBytes($buf)
    return ($buf | ForEach-Object { $_.ToString("x2") }) -join ""
}

$PostgresPassword = New-RandomHex -Bytes 16
$SecretKey = New-RandomHex -Bytes 32
$AppApiKey = New-RandomHex -Bytes 24

Print-Ok "Пароли сгенерированы."

# Backup existing .env
$envFile = ".env"
if (Test-Path $envFile) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = ".env.backup.$timestamp"
    Copy-Item $envFile $backupFile
    Print-Warn "Существующий .env сохранён как $backupFile"
}

# Build values
$envOllamaEnabled = if ($OllamaEnabled) { "true" } else { "false" }
$envTelegramEnabled = if ($TelegramEnabled) { "true" } else { "false" }
$telegramAllowed = $TelegramChatId

# Write .env
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$envContent = @"
# ============================================================================
# AI Trend Monitor - Environment Configuration
# ============================================================================
# Generated by setup.ps1 on $timestamp
#
# SECURITY: Never commit this file to version control.
# ============================================================================

# -- Database (PostgreSQL) --------------------------------------------------
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ai_trends
POSTGRES_USER=monitor
POSTGRES_PASSWORD=$PostgresPassword

# -- Redis -------------------------------------------------------------------
REDIS_URL=redis://redis:6379/0

# -- FastAPI -----------------------------------------------------------------
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=INFO
APP_API_KEY=$AppApiKey
APP_CORS_ORIGINS=["http://localhost:8501"]
APP_WORKERS=1

# -- Celery ------------------------------------------------------------------
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# -- HuggingFace -------------------------------------------------------------
HUGGINGFACE_TOKEN=$HuggingFaceToken
HF_MODELS_LIMIT=200
HF_REQUEST_TIMEOUT=30

# -- GitHub ------------------------------------------------------------------
GITHUB_TOKEN=$GitHubToken
GITHUB_MIN_STARS=50
GITHUB_RESULTS_PER_PAGE=100
GITHUB_MAX_PAGES=5
GITHUB_REQUEST_TIMEOUT=30

# -- arXiv -------------------------------------------------------------------
ARXIV_MAX_RESULTS=500
ARXIV_REQUEST_DELAY=3.0
ARXIV_REQUEST_TIMEOUT=60
ARXIV_CATEGORIES=["cs.AI","cs.LG","cs.CL","cs.CV","cs.NE"]

# -- Ollama (LLM inference) -------------------------------------------------
OLLAMA_BASE_URL=$OllamaBaseUrl
OLLAMA_MODEL=$OllamaModel
OLLAMA_ENABLED=$envOllamaEnabled
OLLAMA_TIMEOUT=120
OLLAMA_TEMPERATURE=0.3

# -- Telegram Bot ------------------------------------------------------------
TELEGRAM_BOT_TOKEN=$TelegramBotToken
TELEGRAM_ALLOWED_USERS=$telegramAllowed
TELEGRAM_ADMIN_USERS=$telegramAllowed
TELEGRAM_ENABLED=$envTelegramEnabled

# -- Scheduler ---------------------------------------------------------------
COLLECTION_SCHEDULE_HOURS=$CollectionScheduleHours
ANALYTICS_SCHEDULE_HOURS=12

# -- General -----------------------------------------------------------------
LOG_LEVEL=INFO
ENVIRONMENT=production
SECRET_KEY=$SecretKey

# -- Reports -----------------------------------------------------------------
REPORTS_OUTPUT_DIR=/app/reports
REPORTS_MAX_AGE_DAYS=90

# -- Docker Compose port overrides -------------------------------------------
# DASHBOARD_PORT=8501
# POSTGRES_EXTERNAL_PORT=5432
# REDIS_EXTERNAL_PORT=6379
"@

$envContent | Out-File -FilePath $envFile -Encoding UTF8 -Force
Print-Ok "Файл .env создан."

# ══════════════════════════════════════════════════════════════════════════════
# Final summary
# ══════════════════════════════════════════════════════════════════════════════
Print-Header "Итоговый отчёт"

Write-Host "  Компонент              Статус" -ForegroundColor White
Write-Host "  -----------------------------------------"

if ($DockerOk) {
    Write-Host "  Docker                " -NoNewline; Write-Host "Установлен" -ForegroundColor Green
} else {
    Write-Host "  Docker                " -NoNewline; Write-Host "Не установлен" -ForegroundColor Red
}

if ($DockerComposeOk) {
    Write-Host "  Docker Compose        " -NoNewline; Write-Host "Установлен" -ForegroundColor Green
} else {
    Write-Host "  Docker Compose        " -NoNewline; Write-Host "Не установлен" -ForegroundColor Red
}

if ($GitOk) {
    Write-Host "  Git                   " -NoNewline; Write-Host "Установлен" -ForegroundColor Green
} else {
    Write-Host "  Git                   " -NoNewline; Write-Host "Не установлен" -ForegroundColor Red
}

if ($OllamaEnabled) {
    Write-Host "  Ollama                " -NoNewline; Write-Host "Включён ($OllamaMode, $OllamaModel)" -ForegroundColor Green
} else {
    Write-Host "  Ollama                " -NoNewline; Write-Host "Отключён" -ForegroundColor Yellow
}

if ($TelegramEnabled) {
    Write-Host "  Telegram-бот          " -NoNewline; Write-Host "Настроен" -ForegroundColor Green
} else {
    Write-Host "  Telegram-бот          " -NoNewline; Write-Host "Не настроен" -ForegroundColor Yellow
}

if (-not [string]::IsNullOrWhiteSpace($HuggingFaceToken)) {
    Write-Host "  HuggingFace токен     " -NoNewline; Write-Host "Указан" -ForegroundColor Green
} else {
    Write-Host "  HuggingFace токен     " -NoNewline; Write-Host "Не указан" -ForegroundColor Yellow
}

if (-not [string]::IsNullOrWhiteSpace($GitHubToken)) {
    Write-Host "  GitHub токен          " -NoNewline; Write-Host "Указан" -ForegroundColor Green
} else {
    Write-Host "  GitHub токен          " -NoNewline; Write-Host "Не указан" -ForegroundColor Yellow
}

Write-Host "  Сбор данных           " -NoNewline; Write-Host "Каждые ${CollectionScheduleHours}ч" -ForegroundColor Cyan
Write-Host "  .env файл             " -NoNewline; Write-Host "Создан" -ForegroundColor Green

Write-Host ""
Write-Host "  -----------------------------------------"
Write-Host ""

if (-not $DockerOk -or -not $DockerComposeOk) {
    Print-Warn "Docker/Docker Compose не установлены. Установите перед запуском."
}

Write-Host ""
Write-Host "  Настройка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "  Следующий шаг -- запуск проекта:"
Write-Host ""
Write-Host "    docker compose up -d    -- запустить все сервисы" -ForegroundColor Cyan
Write-Host "    docker compose logs -f  -- посмотреть логи" -ForegroundColor Cyan
Write-Host "    docker compose ps       -- статус сервисов" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Дашборд будет доступен: http://localhost:8501" -ForegroundColor Cyan
Write-Host "  API будет доступен:     http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
