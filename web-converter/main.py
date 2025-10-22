"""
Веб-сервис для конвертации аудио файлов
Позволяет загружать большие файлы (до 2 ГБ) и конвертировать их в MP3
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional

# Добавляем родительскую директорию в PATH для импорта утилит бота
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, Depends, Cookie
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import uvicorn
import secrets
import hashlib
import time

from bot.utils.audio_converter import convert_to_mp3_auto, get_audio_duration, calculate_optimal_bitrate
from bot.utils.formatters import format_duration, format_file_size
from bot.utils.config import config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Converter API",
    description="Конвертация аудио файлов для Telegram бота",
    version="1.0.0"
)

# CORS для возможности обращения из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Обработчик 401 ошибки - редирект на страницу логина для браузера, JSON для API
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        # Для API запросов возвращаем JSON
        if request.url.path.startswith("/convert") or request.url.path.startswith("/download"):
            return Response(
                content='{"detail":"Требуется авторизация"}',
                status_code=401,
                media_type="application/json"
            )
        # Для обычных страниц делаем редирект на логин
        return RedirectResponse(url="/login")
    raise exc

# Директории для файлов
UPLOAD_DIR = Path("web-converter/uploads")
CONVERTED_DIR = Path("web-converter/converted")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CONVERTED_DIR.mkdir(parents=True, exist_ok=True)

# Максимальный размер файла (2 ГБ)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB

# Хранилище активных сессий (в продакшене лучше использовать Redis)
active_sessions = {}

def generate_session_token(username: str) -> str:
    """Генерация токена сессии"""
    timestamp = str(time.time())
    raw = f"{username}:{timestamp}:{secrets.token_urlsafe(32)}"
    return hashlib.sha256(raw.encode()).hexdigest()

def verify_session(session_token: Optional[str] = Cookie(None, alias="session_token")) -> str:
    """Проверка токена сессии"""
    if not session_token or session_token not in active_sessions:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    return active_sessions[session_token]


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Страница авторизации"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход - Аудио Конвертер</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }

            .login-container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                width: 100%;
                max-width: 400px;
                animation: slideIn 0.5s ease-out;
            }

            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }

            .login-header h1 {
                font-size: 28px;
                color: #333;
                margin-bottom: 10px;
            }

            .login-header .icon {
                font-size: 60px;
                margin-bottom: 15px;
            }

            .login-header p {
                color: #666;
                font-size: 14px;
            }

            .form-group {
                margin-bottom: 20px;
            }

            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
                font-size: 14px;
            }

            .form-group input {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                font-size: 16px;
                transition: all 0.3s;
                font-family: inherit;
            }

            .form-group input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            .form-group input::placeholder {
                color: #999;
            }

            .btn-login {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                margin-top: 10px;
            }

            .btn-login:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }

            .btn-login:active {
                transform: translateY(0);
            }

            .error-message {
                background: #fee;
                color: #c33;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 20px;
                font-size: 14px;
                display: none;
                animation: shake 0.5s;
            }

            @keyframes shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-10px); }
                75% { transform: translateX(10px); }
            }

            .error-message.show {
                display: block;
            }

            @media (max-width: 480px) {
                .login-container {
                    padding: 30px 20px;
                }

                .login-header h1 {
                    font-size: 24px;
                }
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <div class="icon">🎵</div>
                <h1>Вход в систему</h1>
                <p>Аудио конвертер для исламского бота</p>
            </div>

            <div class="error-message" id="errorMessage"></div>

            <form id="loginForm" method="POST" action="/login">
                <div class="form-group">
                    <label for="username">Логин</label>
                    <input type="text" id="username" name="username" placeholder="Введите логин" required autofocus>
                </div>

                <div class="form-group">
                    <label for="password">Пароль</label>
                    <input type="password" id="password" name="password" placeholder="Введите пароль" required>
                </div>

                <button type="submit" class="btn-login">Войти</button>
            </form>
        </div>

        <script>
            const form = document.getElementById('loginForm');
            const errorMessage = document.getElementById('errorMessage');

            form.addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = new FormData(form);

                try {
                    const response = await fetch('/login', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        window.location.href = '/';
                    } else {
                        const data = await response.json();
                        errorMessage.textContent = data.detail || 'Неверный логин или пароль';
                        errorMessage.classList.add('show');

                        setTimeout(() => {
                            errorMessage.classList.remove('show');
                        }, 3000);
                    }
                } catch (error) {
                    errorMessage.textContent = 'Ошибка подключения к серверу';
                    errorMessage.classList.add('show');
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Обработка авторизации"""
    if username == config.web_converter_login and password == config.web_converter_password:
        session_token = generate_session_token(username)
        active_sessions[session_token] = username

        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=86400 * 7,  # 7 дней
            samesite="lax"
        )
        return response
    else:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")


@app.get("/logout")
async def logout(session_token: Optional[str] = Cookie(None, alias="session_token")):
    """Выход из системы"""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]

    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response


@app.get("/manifest.json")
async def get_manifest(username: str = Depends(verify_session)):
    """PWA Manifest для установки на мобильный"""
    return {
        "name": "Аудио Конвертер - Исламский Бот",
        "short_name": "Аудио Конвертер",
        "description": "Конвертация аудио файлов для Telegram бота",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#667eea",
        "theme_color": "#667eea",
        "orientation": "portrait",
        "icons": [
            {
                "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%23667eea' width='100' height='100'/%3E%3Ctext y='75' font-size='70' fill='white' text-anchor='middle' x='50'%3E🎵%3C/text%3E%3C/svg%3E",
                "sizes": "192x192",
                "type": "image/svg+xml"
            },
            {
                "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%23667eea' width='100' height='100'/%3E%3Ctext y='75' font-size='70' fill='white' text-anchor='middle' x='50'%3E🎵%3C/text%3E%3C/svg%3E",
                "sizes": "512x512",
                "type": "image/svg+xml"
            }
        ]
    }


@app.get("/sw.js")
async def get_service_worker(username: str = Depends(verify_session)):
    """Service Worker для PWA"""
    return HTMLResponse(content="""
// Service Worker для кэширования
const CACHE_NAME = 'audio-converter-v1';
const urlsToCache = [
  '/',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
""", media_type="application/javascript")


@app.get("/", response_class=HTMLResponse)
async def read_root(username: str = Depends(verify_session)):
    """Главная страница с интерфейсом для загрузки файлов"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <meta name="theme-color" content="#667eea">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Аудио Конвертер">
        <meta name="description" content="Конвертация аудио файлов для Telegram бота">
        <link rel="manifest" href="/manifest.json">
        <link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%23667eea' width='100' height='100'/%3E%3Ctext y='75' font-size='70' fill='white' text-anchor='middle' x='50'%3E🎵%3C/text%3E%3C/svg%3E">
        <title>Конвертер аудио для исламского бота</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }

            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 600px;
                width: 100%;
            }

            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
                text-align: center;
            }

            .subtitle {
                color: #666;
                text-align: center;
                margin-bottom: 30px;
                font-size: 14px;
            }

            .upload-area {
                border: 3px dashed #667eea;
                border-radius: 15px;
                padding: 40px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
                margin-bottom: 20px;
                background: #f8f9ff;
            }

            .upload-area:hover {
                background: #eef1ff;
                border-color: #764ba2;
            }

            .upload-area.dragover {
                background: #e0e7ff;
                border-color: #764ba2;
                transform: scale(1.02);
            }

            .upload-icon {
                font-size: 50px;
                margin-bottom: 15px;
            }

            .upload-text {
                color: #667eea;
                font-weight: bold;
                margin-bottom: 5px;
            }

            .upload-hint {
                color: #999;
                font-size: 13px;
            }

            input[type="file"] {
                display: none;
            }

            .bitrate-selector {
                margin-bottom: 20px;
            }

            .bitrate-selector label {
                display: block;
                margin-bottom: 10px;
                color: #333;
                font-weight: bold;
            }

            .bitrate-options {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 10px;
            }

            .bitrate-option {
                padding: 15px;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.2s;
                text-align: center;
            }

            .bitrate-option:hover {
                border-color: #667eea;
                background: #f8f9ff;
            }

            .bitrate-option input {
                display: none;
            }

            .bitrate-option input:checked + label {
                color: #667eea;
                font-weight: bold;
            }

            .bitrate-option input:checked ~ .bitrate-parent {
                border-color: #667eea;
                background: #eef1ff;
            }

            .convert-btn {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }

            .convert-btn:hover {
                transform: translateY(-2px);
            }

            .convert-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }

            .progress-container {
                display: none;
                margin-top: 20px;
            }

            .progress-bar {
                width: 100%;
                height: 30px;
                background: #f0f0f0;
                border-radius: 15px;
                overflow: hidden;
                margin-bottom: 10px;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                transition: width 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
            }

            .file-info {
                background: #f8f9ff;
                border-radius: 10px;
                padding: 15px;
                margin-top: 20px;
                display: none;
            }

            .file-info-item {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e0e0e0;
            }

            .file-info-item:last-child {
                border-bottom: none;
            }

            .download-section {
                display: none;
                margin-top: 20px;
                text-align: center;
            }

            .download-btn {
                display: inline-block;
                padding: 15px 40px;
                background: #28a745;
                color: white;
                text-decoration: none;
                border-radius: 10px;
                font-weight: bold;
                transition: transform 0.2s;
            }

            .download-btn:hover {
                transform: translateY(-2px);
            }

            .error-message {
                background: #fee;
                border: 1px solid #fcc;
                color: #c00;
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                display: none;
            }

            /* Адаптация для мобильных устройств */
            @media (max-width: 768px) {
                body {
                    padding: 10px;
                }

                .container {
                    padding: 20px;
                    border-radius: 15px;
                }

                h1 {
                    font-size: 24px;
                }

                .subtitle {
                    font-size: 14px;
                }

                .upload-area {
                    padding: 30px 20px;
                }

                .upload-icon {
                    font-size: 48px;
                }

                .upload-text {
                    font-size: 16px;
                }

                .upload-hint {
                    font-size: 12px;
                }

                .bitrate-selector label {
                    font-size: 14px;
                }

                .bitrate-options {
                    gap: 8px;
                }

                .bitrate-btn {
                    padding: 10px 15px;
                    font-size: 14px;
                }

                .convert-btn {
                    padding: 12px;
                    font-size: 16px;
                }

                .file-info {
                    padding: 15px;
                }

                .download-section {
                    padding: 15px;
                }
            }

            /* Адаптация для очень маленьких экранов */
            @media (max-width: 400px) {
                .container {
                    padding: 15px;
                }

                h1 {
                    font-size: 20px;
                }

                .upload-area {
                    padding: 20px 15px;
                }

                .bitrate-options {
                    flex-direction: column;
                    gap: 10px;
                }

                .bitrate-btn {
                    width: 100%;
                }
            }

            /* Поддержка safe area для iPhone с вырезом */
            @supports (padding: max(0px)) {
                body {
                    padding-left: max(20px, env(safe-area-inset-left));
                    padding-right: max(20px, env(safe-area-inset-right));
                    padding-bottom: max(20px, env(safe-area-inset-bottom));
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Конвертер Аудио</h1>
            <p class="subtitle">Для исламского Telegram бота уроков</p>

            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📁</div>
                <div class="upload-text">Нажмите или перетащите файл сюда</div>
                <div class="upload-hint">Поддерживаются: MP3, WAV, OGG, FLAC, M4A, AAC и другие<br>Максимальный размер: 2 ГБ</div>
                <input type="file" id="fileInput" accept="audio/*">
            </div>

            <div class="bitrate-selector">
                <label>Выберите качество (битрейт):</label>
                <div class="bitrate-options">
                    <div class="bitrate-option bitrate-parent">
                        <input type="radio" name="bitrate" value="64" id="bitrate64" checked>
                        <label for="bitrate64">
                            <strong>64 kbps</strong><br>
                            <small>До 40 мин</small>
                        </label>
                    </div>
                    <div class="bitrate-option bitrate-parent">
                        <input type="radio" name="bitrate" value="48" id="bitrate48">
                        <label for="bitrate48">
                            <strong>48 kbps</strong><br>
                            <small>До 1 часа</small>
                        </label>
                    </div>
                    <div class="bitrate-option bitrate-parent">
                        <input type="radio" name="bitrate" value="32" id="bitrate32">
                        <label for="bitrate32">
                            <strong>32 kbps</strong><br>
                            <small>До 1.5 часов</small>
                        </label>
                    </div>
                    <div class="bitrate-option bitrate-parent">
                        <input type="radio" name="bitrate" value="auto" id="bitrateAuto">
                        <label for="bitrateAuto">
                            <strong>Авто</strong><br>
                            <small>Подобрать</small>
                        </label>
                    </div>
                </div>
            </div>

            <button class="convert-btn" id="convertBtn" disabled>Конвертировать</button>

            <div class="progress-container" id="progressContainer">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill">0%</div>
                </div>
                <div id="statusText" style="text-align: center; color: #666;"></div>
            </div>

            <div class="file-info" id="fileInfo"></div>

            <div class="download-section" id="downloadSection">
                <a href="#" class="download-btn" id="downloadBtn" download>📥 Скачать MP3</a>
            </div>

            <div class="error-message" id="errorMessage"></div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const convertBtn = document.getElementById('convertBtn');
            const progressContainer = document.getElementById('progressContainer');
            const progressFill = document.getElementById('progressFill');
            const statusText = document.getElementById('statusText');
            const fileInfo = document.getElementById('fileInfo');
            const downloadSection = document.getElementById('downloadSection');
            const downloadBtn = document.getElementById('downloadBtn');
            const errorMessage = document.getElementById('errorMessage');

            let selectedFile = null;

            // Drag & Drop
            uploadArea.addEventListener('click', () => fileInput.click());
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handleFileSelect(files[0]);
                }
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                }
            });

            function handleFileSelect(file) {
                selectedFile = file;
                convertBtn.disabled = false;
                uploadArea.querySelector('.upload-text').textContent = `Выбран: ${file.name}`;
                uploadArea.querySelector('.upload-hint').textContent = `Размер: ${formatFileSize(file.size)}`;
            }

            convertBtn.addEventListener('click', async () => {
                if (!selectedFile) return;

                const bitrate = document.querySelector('input[name="bitrate"]:checked').value;

                convertBtn.disabled = true;
                progressContainer.style.display = 'block';
                downloadSection.style.display = 'none';
                errorMessage.style.display = 'none';
                fileInfo.style.display = 'none';

                const formData = new FormData();
                formData.append('file', selectedFile);
                formData.append('bitrate', bitrate);

                let progressInterval; // Объявляем снаружи для доступа в catch

                try {
                    updateProgress(10, 'Загрузка файла на сервер...');

                    // Запускаем имитацию прогресса во время конвертации
                    let currentProgress = 10;
                    progressInterval = setInterval(() => {
                        if (currentProgress < 90) {
                            currentProgress += 5;
                            updateProgress(currentProgress, 'Конвертация в MP3...');
                        }
                    }, 500); // Обновление каждые 500мс

                    const response = await fetch('/convert', {
                        method: 'POST',
                        body: formData
                    });

                    clearInterval(progressInterval); // Останавливаем имитацию

                    if (!response.ok) {
                        // Если требуется авторизация - перенаправляем на логин
                        if (response.status === 401) {
                            window.location.href = '/login';
                            return;
                        }
                        const error = await response.json();
                        throw new Error(error.detail || 'Ошибка конвертации');
                    }

                    const result = await response.json();

                    updateProgress(100, 'Готово!');

                    // Показываем информацию о файле
                    showFileInfo(result);

                    // Показываем кнопку скачивания
                    downloadBtn.href = `/download/${result.filename}`;
                    downloadSection.style.display = 'block';

                } catch (error) {
                    if (progressInterval) clearInterval(progressInterval); // Останавливаем имитацию при ошибке
                    errorMessage.textContent = `Ошибка: ${error.message}`;
                    errorMessage.style.display = 'block';
                    progressContainer.style.display = 'none';
                } finally {
                    convertBtn.disabled = false;
                }
            });

            function updateProgress(percent, text) {
                progressFill.style.width = percent + '%';
                progressFill.textContent = percent + '%';
                statusText.textContent = text;
            }

            function showFileInfo(data) {
                fileInfo.innerHTML = `
                    <div class="file-info-item">
                        <span>Длительность:</span>
                        <strong>${data.duration}</strong>
                    </div>
                    <div class="file-info-item">
                        <span>Битрейт MP3:</span>
                        <strong>${data.bitrate} kbps</strong>
                    </div>
                    <div class="file-info-item">
                        <span>Размер MP3:</span>
                        <strong>${data.mp3_size}</strong>
                    </div>
                    <div class="file-info-item">
                        <span>Исходный размер:</span>
                        <strong>${data.original_size}</strong>
                    </div>
                `;
                fileInfo.style.display = 'block';
            }

            function formatFileSize(bytes) {
                if (bytes < 1024) return bytes + ' Б';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
                if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
                return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' ГБ';
            }

            // Регистрация Service Worker для PWA
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', () => {
                    navigator.serviceWorker.register('/sw.js')
                        .then(registration => console.log('PWA: Service Worker зарегистрирован'))
                        .catch(err => console.log('PWA: Ошибка регистрации Service Worker', err));
                });
            }

            // Обработка события установки PWA
            let deferredPrompt;
            window.addEventListener('beforeinstallprompt', (e) => {
                e.preventDefault();
                deferredPrompt = e;
                console.log('PWA: Готово к установке на устройство');
            });
        </script>
    </body>
    </html>
    """


@app.post("/convert")
async def convert_audio(
    file: UploadFile = File(...),
    bitrate: str = Form("64"),
    username: str = Depends(verify_session)
):
    """
    Конвертация аудио файла в MP3

    Args:
        file: Загруженный аудио файл
        bitrate: Битрейт (64, 48, 32 или auto)

    Returns:
        JSON с информацией о конвертированном файле
    """
    try:
        logger.info(f"Получен файл: {file.filename}, размер: {file.size if hasattr(file, 'size') else 'unknown'}")

        # Сохраняем загруженный файл
        file_ext = Path(file.filename).suffix
        temp_filename = f"temp_{os.urandom(8).hex()}{file_ext}"
        temp_path = UPLOAD_DIR / temp_filename

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        original_size = os.path.getsize(temp_path)
        logger.info(f"Файл сохранён: {temp_path}, размер: {original_size} байт")

        # Определяем битрейт
        if bitrate == "auto":
            duration = await get_audio_duration(str(temp_path))
            if duration:
                preferred_bitrate = await calculate_optimal_bitrate(duration)
            else:
                preferred_bitrate = 64
        else:
            preferred_bitrate = int(bitrate)

        # Конвертируем (используем оригинальное имя файла)
        original_name = Path(file.filename).stem  # имя без расширения
        # Добавляем timestamp для уникальности
        import time
        timestamp = int(time.time())
        output_filename = f"{original_name}_{timestamp}.mp3"
        output_path = CONVERTED_DIR / output_filename

        success, error, used_bitrate = await convert_to_mp3_auto(
            str(temp_path),
            str(output_path),
            preferred_bitrate=preferred_bitrate
        )

        # Удаляем временный файл
        os.remove(temp_path)

        if not success:
            raise HTTPException(status_code=400, detail=error)

        # Получаем информацию о файле
        duration_seconds = await get_audio_duration(str(output_path))
        mp3_size = os.path.getsize(output_path)

        result = {
            "filename": output_filename,
            "duration": format_duration(duration_seconds) if duration_seconds else "Неизвестно",
            "bitrate": used_bitrate or preferred_bitrate,
            "mp3_size": format_file_size(mp3_size),
            "original_size": format_file_size(original_size)
        }

        logger.info(f"Конвертация успешна: {result}")
        return result

    except Exception as e:
        logger.error(f"Ошибка конвертации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
async def download_file(filename: str, username: str = Depends(verify_session)):
    """Скачивание сконвертированного файла"""
    file_path = CONVERTED_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="audio/mpeg"
    )


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok", "service": "audio-converter"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=1992,
        reload=True,
        log_level="info"
    )
