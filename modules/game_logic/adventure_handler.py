# modules/game_logic/adventure_handler.py
# Versão final com lógica completa e formatação HTML corrigida.

import json
import random
import re
from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils

# --- A "FORJA MÁGICA" E O PROCESSADOR DE LOOT ---
def _gerar_item_magico(config, id_item_base, raridade_maxima):
    # (código completo da função)
    base_item = config.BASE_ITEMS_DATA.get(id_item_base)
    if not base_item: return None
    raridades, indice_max = ["Comum", "Incomum", "Raro", "Épico"], raridades.index(raridade_maxima) if raridade_maxima in raridades else 0
    roll = random.randint(1, 100)
    if roll <= 60 or indice_max == 0: indice_final = indice_max
    elif roll <= 90: indice_final = max(0, indice_max - 1)
    else: indice_final = max(0, indice_max - 2)
    raridade_final = raridades[indice_final]
    efeitos_a_adicionar = 0
    if raridade_final == "Incomum": efeitos_a_adicionar = random.choice([0, 1])
    elif raridade_final == "Raro": efeitos_a_adicionar = random.choice([1, 2])
    elif raridade_final == "Épico": efeitos_a_adicionar = 3 if random.randint(1, 10) > 1 else 4
    item_gerado = base_item.copy()
    if efeitos_a_adicionar == 0:
        item_gerado.update({'nome_exibido': base_item['nome_base'], 'raridade': 'Comum', 'efeitos': []}); return item_gerado
    efeitos_escolhidos, tags_usadas, tem_prefixo = [], set(), False
    pool_prefixos = [p for p in config.AFFIXES_DATA.get('prefixos', {}).get(base_item.get('tipo', 'geral'), []) if raridades.index(p['raridade_minima']) <= indice_final]
    pool_sufixos = [s for s in config.AFFIXES_DATA.get('sufixos', {}).get('geral', []) if raridades.index(s['raridade_minima']) <= indice_final]
    for _ in range(efeitos_a_adicionar):
        pool_prefixos_filtrado = [p for p in pool_prefixos if not any(tag in tags_usadas for tag in p.get('incompativel_com', []))]
        pool_sufixos_filtrado = [s for s in pool_sufixos if not any(tag in tags_usadas for tag in s.get('incompativel_com', []))]
        escolha_pool = []
        if pool_prefixos_filtrado and not tem_prefixo: escolha_pool.append('prefixo')
        if pool_sufixos_filtrado: escolha_pool.append('sufixo')
        if not escolha_pool: break
        tipo_sorteado = random.choice(escolha_pool)
        if tipo_sorteado == 'prefixo':
            afixo = random.choice(pool_prefixos_filtrado)
            efeitos_escolhidos.append(afixo); pool_prefixos.remove(afixo); tem_prefixo = True
        else:
            afixo = random.choice(pool_sufixos_filtrado)
            efeitos_escolhidos.append(afixo); pool_sufixos.remove(afixo)
        tags_usadas.update(afixo.get('tags', []))
    nome_final, lista_efeitos_desc = base_item['nome_base'], []
    for afixo in efeitos_escolhidos:
        if afixo in config.AFFIXES_DATA.get('prefixos', {}).get(base_item.get('tipo', 'geral'), []): nome_final = f"{afixo['nome']} {nome_final}"
        else: nome_final = f"{nome_final} {afixo['nome']}"
        lista_efeitos_desc.append(afixo['efeito'])
    item_gerado.update({'nome_exibido': nome_final, 'descricao_final': f"{base_item['descricao_base']}\n<b>Efeitos Mágicos:</b> {'; '.join(lista_efeitos_desc)}", 'efeitos': lista_efeitos_desc, 'raridade': raridade_final})
    return item_gerado

def _processar_tabela_de_loot(config, player_ref, tabela_id):
    tabela = config.LOOT_TABLES_DATA.get(tabela_id)
    if not tabela: return None
    loot_encontrado_texto, itens_para_adicionar = [], []
    if tabela.get('moedas', "0") != "0":
        try:
            num_dados, tipo_dado = map(int, tabela['moedas'].split('d'))
            moedas_ganhas = sum(random.randint(1, tipo_dado) for _ in range(num_dados))
            if moedas_ganhas > 0:
                loot_encontrado_texto.append(f"💰 {moedas_ganhas} Peças de Cobre")
                player_ref.update({'ficha.dinheiro': firestore.Increment(moedas_ganhas)})
        except: print(f"ERROR: Formato de moedas inválido na tabela {tabela_id}")
    for drop in tabela.get('drops', []):
        if random.randint(1, 100) <= drop.get('chance', 0):
            item_gerado = _gerar_item_magico(config, drop['id_item_base'], drop['raridade_maxima'])
            if item_gerado:
                nome_escapado = telegram_actions.escape_html(item_gerado['nome_exibido'])
                loot_encontrado_texto.append(f"✨ {nome_escapado} <code>({item_gerado['raridade']})</code>")
                itens_para_adicionar.append(item_gerado)
    if itens_para_adicionar: player_ref.update({'ficha.inventario': firestore.ArrayUnion(itens_para_adicionar)})
    return "Você encontra:\n" + "\n".join(loot_encontrado_texto) if loot_encontrado_texto else None

# ==============================================================================
# === HANDLERS DE COMANDOS                                                 ===
# ==============================================================================
def handle_start_command(config, user_id, chat_id, player_doc):
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        nome_personagem = player_doc.to_dict().get('ficha', {}).get('nome', 'Aventureiro(a)')
        nome_escapado = telegram_actions.escape_html(nome_personagem)
        texto = f"⚔️ Bem-vindo(a) de volta, <b>{nome_escapado}</b>! Sua aventura nas Terras de Aethel continua."
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto)
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Sua lenda ainda não foi escrita. Use /criar_personagem para forjar seu destino.")

def handle_ficha_command(config, user_id, chat_id, player_doc):
    hosting_url = "https://meu-rpg-duna.web.app"
    if player_doc.exists and 'ficha' in player_doc.to_dict():
        teclado = {'inline_keyboard': [[{'text': '📜 Abrir Ficha de Personagem', 'web_app': {'url': hosting_url}}]]}
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Aqui está sua ficha de aventureiro. Clique no botão abaixo para abri-la.", teclado)
    else:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Você precisa criar um personagem primeiro! Use o comando /criar_personagem.")

# ==============================================================================
# === HANDLERS DE AÇÕES (MENSAGENS E CALLBACKS)                              ===
# ==============================================================================
def handle_adventure_message(config, user_id, chat_id, user_text, player_ref, player_data):
    prompt_arbitro = config.PROMPTS['arbitro'].format(user_text)
    convo_arbitro = config.model.start_chat(history=[])
    resposta_arbitro = convo_arbitro.send_message(prompt_arbitro).text.strip().upper()
    if resposta_arbitro == "SIM":
        texto_pergunta = "🎲 O destino é incerto. Teste sua <b>sorte</b>!"
        teclado = {'inline_keyboard': [[{'text': 'Rolar o d20 (Ação Geral)', 'callback_data': 'roll_d20'}]]}
        player_ref.update({'acao_pendente': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_pergunta, teclado)
    else:
        ficha = player_data.get('ficha', {})
        historico = player_data.get('historico', [])
        prompt_simples = config.PROMPTS['narrador_simples'].format(user_text, json.dumps(ficha, ensure_ascii=False))
        convo_simples = config.model.start_chat(history=historico)
        resposta_narrador = convo_simples.send_message(prompt_simples).text
        texto_seguro = telegram_actions.escape_html(resposta_narrador)
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_seguro)
        player_ref.update({'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [user_text]}, {'role': 'model', 'parts': [texto_seguro]}])})

def handle_adventure_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    if callback_data == 'roll_d20':
        acao_pendente = player_data.get('acao_pendente')
        if acao_pendente:
            resultado_d20 = random.randint(1, 20)
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você lança seu destino aos ventos... o resultado do dado é <b>{resultado_d20}</b>!")
            ficha = player_data.get('ficha', {})
            historico = player_data.get('historico', [])
            prompt_final = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(historico, ensure_ascii=False), acao_pendente, resultado_d20)
            convo = config.model.start_chat(history=historico)
            resposta_narrador = convo.send_message(prompt_final).text
            texto_narracao_limpo = re.sub(r'\[LOOT_TABLE:\s*\w+\s*\]', '', resposta_narrador).strip()
            texto_seguro = telegram_actions.escape_html(texto_narracao_limpo)
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_seguro)
            loot_tag_match = re.search(r'\[LOOT_TABLE:(\w+)\]', resposta_narrador)
            if loot_tag_match:
                tabela_id = loot_tag_match.group(1)
                mensagem_loot = _processar_tabela_de_loot(config, player_ref, tabela_id)
                if mensagem_loot:
                    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, mensagem_loot)
            player_ref.update({
                'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [acao_pendente]}, {'role': 'model', 'parts': [texto_narracao_limpo]}]),
                'acao_pendente': firestore.DELETE_FIELD
            })
