# modules/telegram_actions.py
import requests
import json
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - [telegram_actions] - %(message)s')

def escape_markdown_v2(text: str) -> str:
    """
    Escapa TODOS os caracteres reservados do MarkdownV2, conforme a documentação oficial.
    Esta função é a nossa garantia de que nenhum texto irá quebrar a API.
    """
    if not isinstance(text, str):
        return ""
    # A lista completa de caracteres reservados que DEVEM ser escapados.
    escape_chars = r'\_*[]()~`>#+-.=|{}!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_telegram_message(token, chat_id, text, keyboard=None):
    """Envia uma mensagem de texto, garantindo que o texto já está escapado se necessário."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "MarkdownV2"}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            # Se ainda houver um erro, o log agora mostrará o texto exato que falhou.
            logging.error(f"Telegram API Error (send): {response.status_code} - {response.text} | Payload Text: {text}")
            response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de rede ao enviar mensagem para {chat_id}: {e}"); return None

def edit_telegram_message(token, chat_id, message_id, text, keyboard=None):
    """Edita uma mensagem de texto, garantindo que o texto já está escapado se necessário."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {"chat_id": str(chat_id), "message_id": message_id, "text": text, "parse_mode": "MarkdownV2"}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            logging.error(f"Telegram API Error (edit): {response.status_code} - {response.text} | Payload Text: {text}")
            response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de rede ao editar mensagem {message_id}: {e}"); return None

# A função answer_callback_query permanece igual
def answer_callback_query(token, callback_query_id):
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de rede ao responder callback {callback_query_id}: {e}")