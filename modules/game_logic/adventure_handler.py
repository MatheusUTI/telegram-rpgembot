# modules/game_logic/adventure_handler.py
import json
import random
import re
from firebase_admin import firestore
from modules import telegram_actions

# Esta função deveria estar num módulo de utilidades, mas por simplicidade, deixamo-la aqui por agora.
def _gerar_item_magico(config, id_item_base, raridade_maxima):
    # Lógica da Forja Mágica...
    # (O código que já tínhamos)
    return {} # Placeholder

def _processar_tabela_de_loot(config, player_ref, tabela_id):
    # Lógica de processar loot...
    # (O código que já tínhamos)
    return "Loot encontrado!" # Placeholder

# --- FUNÇÃO QUE ESTAVA EM FALTA ---
def handle_start_command(config, user_id, chat_id, player_doc):
    """Lida com o comando /start."""
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        nome_personagem = player_doc.to_dict().get('ficha', {}).get('nome', 'Aventureiro(a)')
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"Bem-vindo(a) de volta, {nome_personagem}! Sua aventura nas Terras de Aethel continua...")
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Sua lenda ainda não foi escrita. Use /criar_personagem para forjar seu destino.")

def handle_ficha_command(config, user_id, chat_id, player_doc):
    """Lida com o comando /ficha."""
    hosting_url = "https://meu-rpg-duna.web.app"
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        teclado = {'inline_keyboard': [[{'text': '📜 Abrir Ficha de Personagem', 'web_app': {'url': hosting_url}}]]}
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Aqui está sua ficha de aventureiro. Clique no botão abaixo para abri-la.", teclado)
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Você precisa criar um personagem primeiro! Use o comando /criar_personagem.")

def handle_adventure_message(config, user_id, chat_id, user_text, player_ref, player_data):
    """Trata as mensagens de texto no modo aventura."""
    prompt_arbitro = config.PROMPTS['arbitro'].format(user_text)
    convo_arbitro = config.model.start_chat(history=[])
    resposta_arbitro = convo_arbitro.send_message(prompt_arbitro).text.strip().upper()

    if resposta_arbitro == "SIM":
        texto_pergunta = "O destino é incerto. Teste sua sorte."
        teclado = {'inline_keyboard': [[{'text': '🎲 Rolar d20 (Ação Geral)', 'callback_data': 'roll_d20'}]]}
        sent_message = telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_pergunta, teclado)
        if sent_message and sent_message.get('ok'):
            player_ref.update({'acao_pendente': user_text})
    else:
        ficha = player_data.get('ficha', {})
        prompt_simples = config.PROMPTS['narrador_simples'].format(user_text, json.dumps(ficha, ensure_ascii=False))
        # (Lógica para continuar conversa e salvar histórico aqui)
        convo_simples = config.model.start_chat(history=player_data.get('historico', []))
        response = convo_simples.send_message(prompt_simples)
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, response.text)
        player_ref.update({'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [user_text]}, {'role': 'model', 'parts': [response.text]}])})


def handle_adventure_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    """Trata os cliques em botões no modo aventura."""
    if callback_data == 'roll_d20':
        acao_pendente = player_data.get('acao_pendente')
        if acao_pendente:
            resultado_d20 = random.randint(1, 20)
            edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você lança seu destino aos ventos... o resultado do dado é *{resultado_d20}*!")
            
            ficha = player_data.get('ficha', {})
            historico = player_data.get('historico', [])
            prompt_final = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(historico, ensure_ascii=False), acao_pendente, resultado_d20)
            
            convo = config.model.start_chat(history=historico)
            resposta_narrador = convo.send_message(prompt_final).text

            # Lógica de processar loot
            # ...

            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, resposta_narrador)
            player_ref.update({
                'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [acao_pendente]}, {'role': 'model', 'parts': [resposta_narrador]}]),
                'acao_pendente': firestore.DELETE_FIELD
            })