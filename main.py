# main.py
import os
import json
import traceback
import hmac
import hashlib
import urllib.parse
import functions_framework
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai

# Importar nossos novos módulos e arquivos
from modules import data_loader, telegram_actions
from modules.game_logic import character_creator, adventure_handler
import prompts

# --- Funções de Logging ---
def log_info(message): print(f"INFO: [main] {message}")
def log_error(message, exc_info=False):
    print(f"ERROR: [main] {message}")
    if exc_info: traceback.print_exc()

# --- Classe de Configuração para passar dependências ---
class GameConfig:
    """Agrupa todas as configurações e dados carregados para passar para os handlers."""
    def __init__(self):
        log_info("Inicializando GameConfig...")
        # Carregar dados do jogo
        self.CLASSES_DATA, self.RACAS_DATA = data_loader.carregar_dados_jogo()
        
        # Configurar Tokens
        self.TELEGRAM_TOKEN = "8185946655:AAGfyNTARWgaRU5ddoFG9hHR-7kPqMCjzo0" # Mantenha como está, conforme solicitado
        self.GEMINI_API_KEY = "AIzaSyDIzFVMGmNp7yg8ovN8o0KHML5DT86b7ho" # Mantenha como está

        # Configurar Gemini
        genai.configure(api_key=self.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Carregar Prompts
        self.PROMPTS = {
            "arbitro": prompts.PROMPT_ARBITRO,
            "mestre_narrador": prompts.PROMPT_MESTRE_NARRADOR,
            "narrador_simples": prompts.PROMPT_NARRADOR_SIMPLES
        }
        log_info("GameConfig inicializado com sucesso.")

# --- INICIALIZAÇÃO GLOBAL ---
log_info("Iniciando inicialização global do main.py...")
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()
config = GameConfig() # Cria uma instância única da configuração
log_info("Inicialização global do main.py concluída.")


# ==============================================================================
# === CLOUD FUNCTION 1: O WEBHOOK DO BOT DO TELEGRAM                          ===
# ==============================================================================
@functions_framework.http
def rpg_bot_webhook(request):
    log_info("Webhook recebido.")
    update = request.get_json(silent=True)
    if not update:
        log_info("Request sem JSON payload. Retornando OK.")
        return "OK", 200

    chat_id_para_erro, user_id = None, None

    try:
        # Extrair dados comuns do update
        if 'callback_query' in update:
            is_callback = True
            data = update['callback_query']
            user_id = str(data['from']['id'])
            chat_id = data['message']['chat']['id']
            message_id = data['message']['message_id']
            callback_data = data['data']
            user_text = None # Não há texto de mensagem em um callback
            telegram_actions.answer_callback_query(config.TELEGRAM_TOKEN, data['id'])
        elif 'message' in update and 'text' in update['message']:
            is_callback = False
            message = update['message']
            user_id = str(message['from']['id'])
            chat_id = message['chat']['id']
            user_text = message['text']
            message_id = None # Não há um message_id para editar diretamente
            callback_data = None
        else:
            log_info("Update sem conteúdo relevante (callback ou mensagem de texto). Ignorando.")
            return "OK", 200

        chat_id_para_erro = chat_id
        
        player_ref = db.collection('jogadores').document(user_id)
        player_doc = player_ref.get()
        player_data = player_doc.to_dict() if player_doc.exists else {}
        estado_atual = player_data.get('estado_criacao')

        # Comandos de sistema que podem ser executados em qualquer estado
        if not is_callback:
            if user_text.lower() == '/start':
                 adventure_handler.handle_start_command(config, user_id, chat_id, player_doc)
                 return "OK", 200
            if user_text.lower() == '/criar_personagem':
                character_creator.handle_criar_personagem_command(config, user_id, chat_id, player_ref)
                return "OK", 200
            if user_text.lower() == '/ficha':
                adventure_handler.handle_ficha_command(config, user_id, chat_id, player_doc)
                return "OK", 200

        # --- ROTEAMENTO DA LÓGICA ---
        if estado_atual:
            log_info(f"Roteando para Character Creator para user_id {user_id}. Estado: {estado_atual}")
            if is_callback:
                character_creator.handle_creation_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data)
            else:
                character_creator.handle_creation_message(config, user_id, chat_id, user_text, player_ref, player_data)
        else:
            log_info(f"Roteando para Adventure Handler para user_id {user_id}.")
            if is_callback:
                adventure_handler.handle_adventure_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data)
            else:
                adventure_handler.handle_adventure_message(config, user_id, chat_id, user_text, player_ref, player_data)

    except Exception as e:
        log_error(f"Erro INESPERADO no roteador principal para user_id {user_id}: {e}", exc_info=True)
        if chat_id_para_erro:
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id_para_erro, f"Ocorreu um erro catastrófico. Os Deuses Antigos foram alertados. (Detalhe: {type(e).__name__})")
    
    log_info("Finalizando processamento do webhook.")
    return "OK", 200


# ==============================================================================
# === CLOUD FUNCTION 2: A API SEGURA PARA A FICHA DE PERSONAGEM              ===
# ==============================================================================
@functions_framework.http
def get_char_sheet(request):
    log_info("API get_char_sheet chamada.")
    headers = {'Access-Control-Allow-Origin': '*','Access-Control-Allow-Methods': 'POST, OPTIONS','Access-Control-Allow-Headers': 'Content-Type'}
    if request.method == 'OPTIONS': return ('', 204, headers)
    request_json = request.get_json(silent=True)
    if not request_json or 'initData' not in request_json:
        log_error("API get_char_sheet: initData não fornecido.")
        return ({'error': 'initData não fornecido.'}, 400, headers)
    init_data = request_json['initData']
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        hash_recebido = parsed_data.pop('hash', None)
        if not hash_recebido:
            log_error("API get_char_sheet: Hash de validação não encontrado.")
            raise ValueError("Hash de validação não encontrado.")
        
        chaves_ordenadas = sorted(parsed_data.keys())
        data_check_string = "\n".join(f"{key}={parsed_data[key]}" for key in chaves_ordenadas)
        secret_key = hmac.new("WebAppData".encode('utf-8'), config.TELEGRAM_TOKEN.encode('utf-8'), hashlib.sha256).digest()
        hash_calculado = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(hash_calculado, hash_recebido):
            log_error(f"API get_char_sheet: Falha na validação de hash.")
            return ({'error': 'Falha na validação dos dados (hash inválido).'}, 403, headers)
        
        user_data_str = parsed_data.get('user')
        if not user_data_str: log_error("API get_char_sheet: Dados do usuário não encontrados."); return ({'error': 'Dados do usuário não encontrados.'}, 400, headers)
        
        user_data = json.loads(user_data_str)
        user_id = str(user_data.get('id'))
        if not user_id: log_error("API get_char_sheet: ID de usuário não encontrado."); return ({'error': 'ID de usuário não encontrado.'}, 400, headers)
        
        log_info(f"API get_char_sheet: Solicitação validada para user_id: {user_id}")
        player_ref = db.collection('jogadores').document(user_id)
        player_doc = player_ref.get()

        if player_doc.exists:
            ficha_data = player_doc.to_dict().get('ficha', {})
            log_info(f"API get_char_sheet: Ficha encontrada para user_id: {user_id}")
            return (json.dumps(ficha_data, ensure_ascii=False), 200, headers)
        else:
            log_info(f"API get_char_sheet: Ficha NÃO encontrada para user_id: {user_id}")
            return ({'error': 'Ficha não encontrada.'}, 404, headers)
            
    except Exception as e_api:
        log_error(f"API get_char_sheet Erro Geral: {e_api}", exc_info=True)
        return ({'error': f'Erro interno: {str(e_api)}'}, 500, headers)