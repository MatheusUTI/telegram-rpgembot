# modules/telegram_actions.py
# Versão atualizada para usar o parse_mode "HTML" de forma segura.

import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

def escape_html(text: str) -> str:
    """
    Escapa os caracteres especiais para o modo de parse HTML do Telegram.
    Conforme a documentação oficial, apenas <, > e & precisam ser escapados.
    """
    if not isinstance(text, str):
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def send_telegram_message(token, chat_id, text, keyboard=None):
    """Envia uma mensagem de texto para um chat do Telegram, usando o modo HTML."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # MUDANÇA PRINCIPAL: parse_mode agora é "HTML"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML"}
    
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.error(f"Telegram API Error (send): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de rede ao enviar mensagem para {chat_id}: {e}")
        return None

def edit_telegram_message(token, chat_id, message_id, text, keyboard=None):
    """Edita uma mensagem de texto existente no Telegram, usando o modo HTML."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    
    # MUDANÇA PRINCIPAL: parse_mode agora é "HTML"
    payload = {"chat_id": str(chat_id), "message_id": message_id, "text": text, "parse_mode": "HTML"}

    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.error(f"Telegram API Error (edit): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de rede ao editar mensagem {message_id}: {e}")
        return None

def answer_callback_query(token, callback_query_id):
    """Responde a uma callback query para remover o ícone de 'carregando' no cliente."""
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de rede ao responder callback {callback_query_id}: {e}")