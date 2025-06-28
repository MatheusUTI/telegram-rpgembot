# main.py
# O orquestrador principal que liga todos os nossos módulos e serviços.

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
import logging

# Importar nossos novos módulos e arquivos
from modules import data_loader, telegram_actions
from modules.game_logic import character_creator, adventure_handler, socketing_handler
from modules.game_logic.utils import calcular_ficha_efetiva # --- ALTERAÇÃO ARQUITETURAL ---
import prompts

# --- Configuração do Logging Profissional ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [main] - %(message)s')

# --- Classe de Configuração para passar dependências ---
class GameConfig:
    """Agrupa todas as configurações e dados carregados para passar para os handlers."""
    def __init__(self):
        logging.info("Inicializando GameConfig...")
        
        dados_jogo = data_loader.carregar_dados_jogo()
        self.CLASSES_DATA = dados_jogo.get('classes', {})
        self.RACAS_DATA = dados_jogo.get('racas', {})
        self.BASE_ITEMS_DATA = dados_jogo.get('base_items', {})
        self.AFFIXES_DATA = dados_jogo.get('affixes', {})
        self.LOOT_TABLES_DATA = dados_jogo.get('loot_tables', {})
        self.GEMAS_DATA = dados_jogo.get('gemas', {})
        
        self.TELEGRAM_TOKEN = "8185946655:AAGfyNTARWgaRU5ddoFG9hHR-7kPqMCjzo0"
        self.GEMINI_API_KEY = "AIzaSyDIzFVMGmNp7yg8ovN8o0KHML5DT86b7ho"

        if not self.TELEGRAM_TOKEN or not self.GEMINI_API_KEY:
            logging.error("ERRO CRÍTICO: Tokens de API não definidos na GameConfig!")
        
        genai.configure(api_key=self.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.PROMPTS = {
            "arbitro": prompts.PROMPT_ARBITRO,
            "mestre_narrador": prompts.PROMPT_MESTRE_NARRADOR,
            "narrador_simples": prompts.PROMPT_NARRADOR_SIMPLES,
            "cronista": prompts.PROMPT_CRONISTA
        }
        logging.info("GameConfig inicializado com sucesso.")

# --- INICIALIZAÇÃO GLOBAL ---
logging.info("Iniciando inicialização global do main.py...")
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()
config = GameConfig()
logging.info("Inicialização global do main.py concluída.")


# ==============================================================================
# === CLOUD FUNCTION 1: O WEBHOOK DO BOT DO TELEGRAM                          ===
# ==============================================================================
@functions_framework.http
def rpg_bot_webhook(request):
    update = request.get_json(silent=True)
    if not update: return "OK", 200

    chat_id, user_id = None, None
    try:
        if 'callback_query' in update:
            data = update['callback_query']
            user_id, chat_id = str(data['from']['id']), data['message']['chat']['id']
            player_ref = db.collection('jogadores').document(user_id)
            player_doc = player_ref.get()
            player_data = player_doc.to_dict() if player_doc.exists else {}
            
            estado_criacao = player_data.get('estado_criacao')
            estado_engaste = player_data.get('estado_engaste')
            
            telegram_actions.answer_callback_query(config.TELEGRAM_TOKEN, data['id'])

            if estado_criacao:
                character_creator.handle_creation_callback(config, user_id, chat_id, data['message']['message_id'], data['data'], player_ref, player_data)
            elif estado_engaste:
                socketing_handler.handle_socketing_callback(config, user_id, chat_id, data['message']['message_id'], data['data'], player_ref, player_data)
            else:
                adventure_handler.handle_adventure_callback(config, user_id, chat_id, data['message']['message_id'], data['data'], player_ref, player_data)

        elif 'message' in update and 'text' in update['message']:
            message = update['message']
            user_id, chat_id, user_text = str(message['from']['id']), message['chat']['id'], message['text']
            player_ref = db.collection('jogadores').document(user_id)
            player_doc = player_ref.get()
            player_data = player_doc.to_dict() if player_doc.exists else {}
            estado_criacao = player_data.get('estado_criacao')

            if user_text.lower() == '/start':
                adventure_handler.handle_start_command(config, user_id, chat_id, player_doc)
            elif user_text.lower() == '/criar_personagem':
                character_creator.handle_criar_personagem_command(config, user_id, chat_id, player_ref)
            elif user_text.lower() == '/ficha':
                adventure_handler.handle_ficha_command(config, user_id, chat_id, player_doc)
            elif user_text.lower() == '/engastar':
                socketing_handler.handle_engastar_command(config, user_id, chat_id, player_ref, player_data)
            
            elif estado_criacao:
                character_creator.handle_creation_message(config, user_id, chat_id, user_text, player_ref, player_data)
            else:
                adventure_handler.handle_adventure_message(config, user_id, chat_id, user_text, player_ref, player_data)
    
    except Exception as e:
        logging.error(f"Erro INESPERADO no roteador principal para user_id {user_id}: {e}", exc_info=True)
        if chat_id:
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Ocorreu um erro catastrófico nos planos astrais. Os Deuses Antigos foram alertados.")
    
    return "OK", 200

# ==============================================================================
# === CLOUD FUNCTION 2: A API SEGURA PARA A FICHA DE PERSONAGEM              ===
# ==============================================================================
@functions_framework.http
def get_char_sheet(request):
    headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'}
    if request.method == 'OPTIONS': return ('', 204, headers)
    
    request_json = request.get_json(silent=True)
    if not request_json or 'initData' not in request_json:
        return ({'error': 'initData não fornecido.'}, 400, headers)
    
    init_data = request_json['initData']
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        hash_recebido = parsed_data.pop('hash', None)
        if not hash_recebido: raise ValueError("Hash de validação não encontrado.")
        
        chaves_ordenadas = sorted(parsed_data.keys())
        data_check_string = "\n".join(f"{key}={parsed_data[key]}" for key in chaves_ordenadas)
        secret_key = hmac.new("WebAppData".encode('utf-8'), config.TELEGRAM_TOKEN.encode('utf-8'), hashlib.sha256).digest()
        hash_calculado = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(hash_calculado, hash_recebido):
            return ({'error': 'Falha na validação dos dados (hash inválido).'}, 403, headers)
        
        user_data = json.loads(parsed_data.get('user', '{}'))
        user_id = str(user_data.get('id'))
        if not user_id: raise ValueError('ID de usuário não encontrado nos dados validados.')
        
        player_ref = db.collection('jogadores').document(user_id)
        player_doc = player_ref.get()

        if player_doc.exists:
            # --- ALTERAÇÃO ARQUITETURAL ---
            # Pega a ficha 'crua' do banco de dados
            player_data = player_doc.to_dict()
            ficha_base = player_data.get('ficha', {})
            
            # Calcula a ficha efetiva com todos os bônus
            ficha_efetiva = calcular_ficha_efetiva(ficha_base)
            
            # Cria um novo dicionário de resposta com a ficha efetiva
            response_data = player_data
            response_data['ficha'] = ficha_efetiva
            
            return (json.dumps(response_data, ensure_ascii=False), 200, headers)
            # --- FIM DA ALTERAÇÃO ---
        else:
            return ({'error': 'Ficha não encontrada.'}, 404, headers)
            
    except Exception as e_api:
        logging.error(f"API get_char_sheet Erro Geral: {e_api}", exc_info=True)
        return ({'error': 'Erro interno no servidor.'}, 500, headers)