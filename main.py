# main.py
# Versão final com enriquecimento de dados na API da ficha.

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

from modules import data_loader, telegram_actions
from modules.game_logic import character_creator, adventure_handler, socketing_handler
from modules.game_logic.utils import calcular_ficha_efetiva # Importa a função de cálculo
import prompts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [main] - %(message)s')

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
        
        self.TELEGRAM_TOKEN = "8185946655:AAGfyNTARWgaRU5ddoFG9hHR-7kPqMCjzo0" # Substitua por variável de ambiente em produção
        self.GEMINI_API_KEY = "AIzaSyDIzFVMGmNp7yg8ovN8o0KHML5DT86b7ho" # Substitua por variável de ambiente em produção

        if not self.TELEGRAM_TOKEN or not self.GEMINI_API_KEY:
            logging.error("ERRO CRÍTICO: Tokens de API não definidos!")
        
        genai.configure(api_key=self.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.PROMPTS = {
            "arbitro": prompts.PROMPT_ARBITRO,
            "mestre_narrador": prompts.PROMPT_MESTRE_NARRADOR,
            "narrador_simples": prompts.PROMPT_NARRADOR_SIMPLES,
            "cronista": prompts.PROMPT_CRONISTA
        }
        logging.info("GameConfig inicializado com sucesso.")

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()
config = GameConfig()

@functions_framework.http
def rpg_bot_webhook(request):
    """Webhook principal que recebe e roteia todas as interações do Telegram."""
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

@functions_framework.http
def get_char_sheet(request):
    """API segura para a ficha de personagem web, agora com enriquecimento de dados."""
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
            player_data = player_doc.to_dict()
            ficha_base = player_data.get('ficha', {})
            
            # 1. Enriquece a ficha base com informações completas de raça e classe
            raca_key = ficha_base.get('raca')
            classe_key = ficha_base.get('classe')
            if raca_key:
                ficha_base['raca_info'] = config.RACAS_DATA.get(raca_key, {})
            if classe_key:
                ficha_base['classe_info'] = config.CLASSES_DATA.get(classe_key, {})

            # 2. Calcula a ficha efetiva com todos os bônus
            ficha_efetiva = calcular_ficha_efetiva(ficha_base)
            
            # 3. Prepara a resposta final com a ficha efetiva e enriquecida
            response_data = player_data
            response_data['ficha'] = ficha_efetiva
            
            return (json.dumps(response_data, ensure_ascii=False), 200, headers)
        else:
            return ({'error': 'Ficha não encontrada.'}, 404, headers)
            
    except Exception as e_api:
        logging.error(f"API get_char_sheet Erro Geral: {e_api}", exc_info=True)
        return ({'error': 'Erro interno no servidor.'}, 500, headers)