# modules/telegram_actions.py
import requests
import json

# Funções de logging podem ser importadas de um módulo de logging central no futuro,
# mas por enquanto, uma simples função print é suficiente aqui.
def log_error(message):
    print(f"ERROR: [telegram_actions] {message}")

def send_telegram_message(token, chat_id, text, keyboard=None):
    """Envia uma mensagem de texto para um chat do Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    
    try:
        response = requests.post(url, json=payload, timeout=10) # Adicionado timeout
        response.raise_for_status()  # Levanta um erro para respostas 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error(f"Erro de rede ao enviar mensagem para {chat_id}: {e}")
        return None

def edit_telegram_message(token, chat_id, message_id, text, keyboard=None):
    """Edita uma mensagem de texto existente no Telegram."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error(f"Erro de rede ao editar mensagem {message_id} para {chat_id}: {e}")
        return None

def answer_callback_query(token, callback_query_id):
    """Responde a uma callback query para remover o ícone de 'carregando' no cliente."""
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.exceptions.RequestException as e:
        log_error(f"Erro de rede ao responder callback query {callback_query_id}: {e}")