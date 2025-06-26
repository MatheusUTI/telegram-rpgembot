# modules/game_logic/adventure_handler.py
import json
import random
import urllib.parse
from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils

# ==============================================================================
# === HANDLERS DE COMANDOS DO MODO AVENTURA                                  ===
# ==============================================================================

def handle_start_command(config, user_id, chat_id, player_doc):
    """Lida com o comando /start."""
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        nome_personagem = player_doc.to_dict().get('ficha', {}).get('nome', 'Aventureiro(a)')
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"Bem-vindo(a) de volta, {nome_personagem}! Sua aventura nas Terras de Aethel continua...")
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Sua lenda ainda não foi escrita. Use /criar_personagem para forjar seu destino.")

def handle_ficha_command(config, user_id, chat_id, player_doc):
    """Lida com o comando /ficha."""
    # Substitua pela sua URL do Firebase Hosting
    hosting_url = "https://meu-rpg-duna.web.app"
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        teclado = {'inline_keyboard': [[{'text': '📜 Abrir Ficha de Personagem', 'web_app': {'url': hosting_url}}]]}
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Aqui está sua ficha de aventureiro. Clique no botão abaixo para abri-la.", teclado)
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Você precisa criar um personagem primeiro! Use o comando /criar_personagem.")

# ==============================================================================
# === HANDLERS DE AÇÕES DO MODO AVENTURA (MENSAGENS E CALLBACKS)             ===
# ==============================================================================

def handle_adventure_message(config, user_id, chat_id, user_text, player_ref, player_data):
    """Trata as mensagens de texto no modo aventura."""
    ficha = player_data.get('ficha', {})
    historico = player_data.get('historico', [])

    # Lógica para o comando /atacar
    if user_text.lower().startswith('/atacar'):
        arma_equipada = None
        for item in ficha.get('inventario', []):
            if isinstance(item, dict) and item.get('tipo', '') == 'arma_equipavel':
                arma_equipada = item
                break
        
        if not arma_equipada:
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Nenhuma arma equipável encontrada!")
            return

        nome_arma = arma_equipada.get('nome', 'arma')
        propriedades_arma = arma_equipada.get('propriedades_arma', [])
        atributo_padrao_arma = arma_equipada.get('atributo_padrao', 'for')
        modificadores = ficha.get('modificadores', {})
        
        attr_ataque = atributo_padrao_arma
        if "acuidade" in propriedades_arma and modificadores.get('des', -5) > modificadores.get('for', -5):
            attr_ataque = 'des'
        
        bonus_attr = modificadores.get(attr_ataque, 0)
        bonus_prof = ficha.get('bonus_proficiencia', 2)
        bonus_total = bonus_attr
        
        proficiencias_armas = config.CLASSES_DATA.get(ficha.get('classe'), {}).get('proficiencia_armas', [])
        tipo_arma_prof = arma_equipada.get("tipo_arma_prof", "simples")
        is_proficiente = tipo_arma_prof in proficiencias_armas

        if is_proficiente:
            bonus_total += bonus_prof

        alvo = user_text.split(' ', 1)[1] if len(user_text.split(' ', 1)) > 1 else "um oponente"
        alvo_enc = urllib.parse.quote_plus(alvo)
        arma_enc = urllib.parse.quote_plus(nome_arma)
        
        texto_info = f"Você empunha sua *{nome_arma}* e mira em *{alvo}*!\nSeu bônus para acertar é *+{bonus_total}* (Base {attr_ataque.upper()}: {bonus_attr}, Prof: +{bonus_prof if is_proficiente else 0})."
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_info)
        
        teclado = {'inline_keyboard': [[{'text': f'⚔️ Tentar Acertar {alvo} (Rolar d20)', 'callback_data': f'ataque_rolar_d20:{alvo_enc}:{arma_enc}:{bonus_total}:{attr_ataque}'}]]}
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Faça sua rolagem de ataque!", teclado)
        return

    # Lógica para ações genéricas
    try:
        prompt_arbitro = config.PROMPTS['arbitro'].format(user_text)
        convo_arbitro = config.model.start_chat(history=[])
        response_arbitro_obj = convo_arbitro.send_message(prompt_arbitro)
        resposta_arbitro = response_arbitro_obj.text.strip().upper()
    except Exception as e_gemini_arb:
        print(f"ERROR: [adventure_handler] Erro ao chamar Gemini (Árbitro) para user_id {user_id}: {e_gemini_arb}")
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "O Oráculo do Destino (IA Árbitro) está momentaneamente confuso. Tente uma ação diferente.")
        return

    entrada_jogador_hist = {"role": "user", "parts": [user_text]}
    if resposta_arbitro == "SIM":
        texto_pergunta = "O destino é incerto. Teste sua sorte."
        teclado = {'inline_keyboard': [[{'text': '🎲 Rolar d20 (Ação Geral)', 'callback_data': 'roll_d20'}]]}
        sent_message = telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_pergunta, teclado)
        if sent_message and sent_message.get('ok'):
            player_ref.update({'acao_pendente': user_text, 'id_mensagem_dado': sent_message['result']['message_id']})
    else: # "NÃO"
        try:
            prompt_simples_fmt = config.PROMPTS['narrador_simples'].format(user_text, json.dumps(ficha, ensure_ascii=False, default=str))
            convo_simples = config.model.start_chat(history=[{"role": msg["role"], "parts": msg["parts"]} for msg in historico])
            response_simples = convo_simples.send_message(prompt_simples_fmt)
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, response_simples.text)
            entrada_modelo_hist = {"role": "model", "parts": [response_simples.text]}
            player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist, entrada_modelo_hist])})
        except Exception as e_gemini_narr:
            print(f"ERROR: [adventure_handler] Erro ao chamar Gemini (Narrador Simples) para user_id {user_id}: {e_gemini_narr}")
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "O Mestre dos Contos tropeçou em suas palavras. Tente novamente.")

def handle_adventure_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    """Trata os cliques em botões no modo aventura."""
    ficha = player_data.get('ficha', {})
    historico = player_data.get('historico', [])

    if callback_data == 'roll_d20':
        acao_pendente = player_data.get('acao_pendente')
        if acao_pendente:
            resultado_d20 = random.randint(1, 20)
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você lança seu destino aos ventos... o resultado do dado é *{resultado_d20}*!")
            entrada_user_hist = {"role": "user", "parts": [acao_pendente]}
            hist_para_gemini = historico + [entrada_user_hist]
            prompt = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(hist_para_gemini, ensure_ascii=False), acao_pendente, resultado_d20)
            convo = config.model.start_chat(history=[{"role": m["role"], "parts": m["parts"]} for m in historico])
            response = convo.send_message(prompt)
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, response.text)
            entrada_model_hist = {"role": "model", "parts": [response.text]}
            player_ref.update({'acao_pendente': firestore.DELETE_FIELD, 'id_mensagem_dado': firestore.DELETE_FIELD, 'historico': firestore.ArrayUnion([entrada_user_hist, entrada_model_hist])})
    
    elif callback_data.startswith('ataque_rolar_d20:'):
        parts = callback_data.split(':', 4)
        alvo_enc, arma_enc, bonus_str, attr_atk = parts[1], parts[2], parts[3], parts[4]
        alvo = urllib.parse.unquote_plus(alvo_enc); arma = urllib.parse.unquote_plus(arma_enc); bonus = int(bonus_str)
        d20_puro = random.randint(1, 20); total_atk = d20_puro + bonus
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Atacando {alvo} com {arma}...\nd20: *{d20_puro}* + Bônus (+{bonus}) = Total: *{total_atk}*")
        
        acao_atk = f"Ataca {alvo} com {arma} (rolagem d20:{d20_puro}, total ataque:{total_atk})."
        hist_user = {"role": "user", "parts": [acao_atk]}; hist_gemini = historico + [hist_user]
        prompt = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(hist_gemini, ensure_ascii=False), f"Atacar {alvo} com {arma}", d20_puro)
        
        convo = config.model.start_chat(history=[{"role": m["role"], "parts": m["parts"]} for m in historico])
        response = convo.send_message(prompt); nar_acerto = response.text
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, nar_acerto)
        hist_model = {"role": "model", "parts": [nar_acerto]}
        
        acerto_ok = any(p in nar_acerto.lower() for p in ["acerta", "atinge", "consegue ferir", "golpe certeiro", "impacta", "conecta"])
        if acerto_ok:
            arma_info = next((item for item in ficha.get('inventario', []) if isinstance(item, dict) and item.get('nome') == arma), None)
            if arma_info:
                dado_dano, tipo_dano = arma_info.get('dado_dano', '1d4'), arma_info.get('tipo_dano_arma', 'concussão')
                attr_dano = arma_info.get('atributo_padrao', attr_atk)
                if "acuidade" in arma_info.get('propriedades_arma', []) and ficha.get('modificadores',{}).get('des',-5) > ficha.get('modificadores',{}).get('for',-5): attr_dano = 'des'
                dado_dano_enc = urllib.parse.quote_plus(dado_dano)
                teclado = {'inline_keyboard': [[{'text': f'💥 Rolar Dano ({dado_dano}) com {arma}', 'callback_data': f'ataque_rolar_dano:{alvo_enc}:{arma_enc}:{attr_dano}:{dado_dano_enc}:{tipo_dano}'}]]}
                telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Seu golpe conectou! Determine o estrago:", teclado)
                player_ref.update({'historico': firestore.ArrayUnion([hist_user, hist_model])})
            else:
                telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"(Mestre: Não encontrei {arma} para dano.)")
                player_ref.update({'historico': firestore.ArrayUnion([hist_user, hist_model])})
        else:
            player_ref.update({'historico': firestore.ArrayUnion([hist_user, hist_model])})

    elif callback_data.startswith('ataque_rolar_dano:'):
        parts = callback_data.split(':', 5)
        alvo_enc, arma_enc, attr_dano, dado_dano_enc, tipo_dano = parts[1], parts[2], parts[3], parts[4], parts[5]
        alvo, arma, dado_dano_str = urllib.parse.unquote_plus(alvo_enc), urllib.parse.unquote_plus(arma_enc), urllib.parse.unquote_plus(dado_dano_enc)
        
        mods = ficha.get('modificadores', {}); mod_dano = mods.get(attr_dano, 0)
        dano_total, rol_str = utils.rolar_dados_dano(dado_dano_str, mod_dano)
        
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, 
            f"Dano com *{arma}* em *{alvo}*:\nDados: {dado_dano_str}\nRolagem: {rol_str}\nTotal: *{dano_total}* de dano *{tipo_dano}*!")
        
        acao_dano = f"Causa {dano_total} de dano {tipo_dano} em {alvo} com {arma}."
        hist_user_dano = {"role": "user", "parts": [acao_dano]}; hist_gemini_dano = historico + [hist_user_dano]
        prompt = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(hist_gemini_dano, ensure_ascii=False), acao_dano, 0)
        
        convo = config.model.start_chat(history=[{"role": m["role"], "parts": m["parts"]} for m in historico])
        response = convo.send_message(prompt)
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, response.text)
        hist_model_dano = {"role": "model", "parts": [response.text]}
        player_ref.update({'historico': firestore.ArrayUnion([hist_user_dano, hist_model_dano])})