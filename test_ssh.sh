#!/bin/bash

echo "🔍 Проверка SSH подключения к FastDL серверу"
echo "=============================================="

# Параметры из .env или по умолчанию
HOST=${FASTDL_SSH_HOST:-"185.130.249.201"}
PORT=${FASTDL_SSH_PORT:-"1337"}
USER=${FASTDL_SSH_USER:-"root"}
REMOTE_PATH=${FASTDL_REMOTE_PATH:-"/var/www/html/fastdl/sound/ui"}

echo "📋 Параметры:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   User: $USER"
echo "   Remote path: $REMOTE_PATH"
echo

# Проверка доступности хоста
echo "🌐 Проверка доступности хоста..."
if ping -c 1 -W 5 $HOST > /dev/null 2>&1; then
    echo "✅ Хост $HOST доступен"
else
    echo "❌ Хост $HOST недоступен"
    exit 1
fi

# Проверка порта
echo "🔌 Проверка порта $PORT..."
if timeout 5 bash -c "</dev/tcp/$HOST/$PORT" 2>/dev/null; then
    echo "✅ Порт $PORT открыт"
else
    echo "❌ Порт $PORT недоступен"
    echo "   Попробуйте: telnet $HOST $PORT"
    exit 1
fi

# Проверка SSH ключей
echo "🔑 Проверка SSH ключей..."
if [ -d ~/.ssh ]; then
    echo "✅ Папка ~/.ssh существует"
    
    key_found=false
    for key_type in rsa ed25519 ecdsa; do
        if [ -f ~/.ssh/id_$key_type ]; then
            echo "✅ Найден приватный ключ: ~/.ssh/id_$key_type"
            key_found=true
        fi
        if [ -f ~/.ssh/id_$key_type.pub ]; then
            echo "✅ Найден публичный ключ: ~/.ssh/id_$key_type.pub"
        fi
    done
    
    if [ "$key_found" = false ]; then
        echo "❌ SSH ключи не найдены"
        echo "   Создайте ключ: ssh-keygen -t ed25519"
    fi
else
    echo "❌ Папка ~/.ssh не существует"
    echo "   Создайте ключ: ssh-keygen -t ed25519"
fi

# Тест SSH подключения
echo "🔐 Тест SSH подключения..."
if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -p $PORT $USER@$HOST "echo 'SSH подключение работает'" 2>/dev/null; then
    echo "✅ SSH подключение успешно!"
    
    # Тест команд на сервере
    echo "🔧 Тест выполнения команд..."
    
    echo -n "   whoami: "
    ssh -o ConnectTimeout=10 -p $PORT $USER@$HOST "whoami" 2>/dev/null || echo "ошибка"
    
    echo -n "   pwd: "
    ssh -o ConnectTimeout=10 -p $PORT $USER@$HOST "pwd" 2>/dev/null || echo "ошибка"
    
    # Проверка папки
    echo "📁 Проверка папки $REMOTE_PATH..."
    if ssh -o ConnectTimeout=10 -p $PORT $USER@$HOST "mkdir -p $REMOTE_PATH && ls -la $REMOTE_PATH" 2>/dev/null; then
        echo "✅ Папка доступна для записи"
    else
        echo "❌ Проблемы с папкой $REMOTE_PATH"
    fi
    
    # Тест загрузки файла
    echo "📤 Тест загрузки файла..."
    test_content="Test file $(date)"
    echo "$test_content" > /tmp/ssh_test.txt
    
    if scp -o ConnectTimeout=10 -P $PORT /tmp/ssh_test.txt $USER@$HOST:$REMOTE_PATH/ssh_test.txt 2>/dev/null; then
        echo "✅ Файл успешно загружен"
        
        # Проверяем содержимое
        echo -n "   Содержимое файла: "
        ssh -o ConnectTimeout=10 -p $PORT $USER@$HOST "cat $REMOTE_PATH/ssh_test.txt" 2>/dev/null
        
        # Удаляем тестовый файл
        ssh -o ConnectTimeout=10 -p $PORT $USER@$HOST "rm $REMOTE_PATH/ssh_test.txt" 2>/dev/null
        echo "🗑️ Тестовый файл удален"
    else
        echo "❌ Ошибка загрузки файла"
    fi
    
    rm -f /tmp/ssh_test.txt
    
else
    echo "❌ SSH подключение не работает"
    echo
    echo "🔧 Попробуйте диагностику:"
    echo "1. Ручное подключение:"
    echo "   ssh -p $PORT $USER@$HOST"
    echo
    echo "2. Если нужна аутентификация по ключу:"
    echo "   ssh-copy-id -p $PORT $USER@$HOST"
    echo
    echo "3. Если используется пароль, добавьте -o PasswordAuthentication=yes"
    echo
    echo "4. Проверьте логи SSH на сервере:"
    echo "   sudo tail -f /var/log/auth.log"
    
    exit 1
fi

echo
echo "🎉 Все проверки пройдены! SSH готов для работы с ботом."