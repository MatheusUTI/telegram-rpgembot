# modules/game_logic/adventure_handler.py
# Versão COMPLETA E CORRETA com UUIDs para cada item.

import json
import random
import re
import uuid # Importa a biblioteca para gerar UUIDs
from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils

def _registrar_memoria(config, player_ref, ficha, acao_jogador, narracao_mestre):
    """Usa o 'Cronista' para extrair um fato da interação e o armazena na memória do jogador."""
    try:
        prompt = config.PROMPTS['cronista'].format(json.dumps(ficha, ensure_ascii=False), acao_jogador, narracao_mestre)
        convo_cronista = config.model.start_chat(history=[])
        fato_gerado = convo_cronista.send_message(prompt).text.strip()
        if fato_gerado:
            player_ref.update({'ficha.memoria': firestore.ArrayUnion([fato_gerado])})
            print(f"Memória registrada: {fato_gerado}")
    except Exception as e:
        print(f"ERRO ao registrar memória: {e}")

def _gerar_gema(config):
    """Constrói um objeto de gema dinamicamente com base nas regras de gemas.json."""
    gemas_data = config.GEMAS_DATA
    if not gemas_data: return None
    tamanhos = gemas_data.get('tamanhos', {})
    roll_tamanho = random.randint(1, 100)
    tamanho_escolhido_key = "pequena"
    chance_acumulada = 0
    for key, data in sorted(tamanhos.items(), key=lambda item: item[1]['chance_drop']):
        chance_acumulada += data['chance_drop']
        if roll_tamanho <= chance_acumulada:
            tamanho_escolhido_key = key
            break
    tamanho_info = tamanhos.get(tamanho_escolhido_key, {})
    essencias = gemas_data.get('essencias', {})
    essencia_escolhida_key = random.choice(list(essencias.keys()))
    essencia_info = essencias.get(essencia_escolhida_key, {})
    multiplicador = tamanho_info.get('multiplicador_valor', 1)
    def construir_texto_efeito(efeito_info):
        valor_final = efeito_info.get('valor_base', 1) * multiplicador
        return efeito_info.get('texto_exibicao', "").format(valor_final)
    gema_final = {
        "uuid": str(uuid.uuid4()), # Adiciona um UUID único
        "nome_exibido": f"{tamanho_info.get('nome_prefixo', '')} {essencia_info.get('nome_base', '')}",
        "tipo_item": "gema",
        "origem_racial": essencia_info.get('origem_racial', ''),
        "descricao": essencia_info.get('descricao', ''),
        "efeito_arma_desc": construir_texto_efeito(essencia_info.get('efeitos', {}).get('arma', {})),
        "efeito_armadura_desc": construir_texto_efeito(essencia_info.get('efeitos', {}).get('armadura', {})),
        "dados_brutos": { "essencia": essencia_escolhida_key, "tamanho": tamanho_escolhido_key, "efeitos": essencia_info.get('efeitos', {}) }
    }
    return gema_final

def _gerar_item_magico(config, id_item_base, raridade_maxima):
    """Gera um item (comum ou mágico) com base num item base, com UUID e engastes potenciais."""
    base_item = config.BASE_ITEMS_DATA.get(id_item_base)
    if not base_item: return None
    
    item_gerado = base_item.copy()
    item_gerado["uuid"] = str(uuid.uuid4()) # Adiciona um UUID único a todo item gerado

    raridades = ["Comum", "Incomum", "Raro", "Épico"]
    indice_max = raridades.index(raridade_maxima) if raridade_maxima in raridades else 0
    
    roll = random.randint(1, 100)
    if roll <= 60 or indice_max == 0: indice_final = 0
    elif roll <= 85: indice_final = 1
    elif roll <= 98: indice_final = 2
    else: indice_final = 3
    
    indice_final = min(indice_final, indice_max)
    raridade_final = raridades[indice_final]

    item_gerado['raridade'] = raridade_final
    item_gerado['efeitos'] = []

    if raridade_final == "Comum":
        item_gerado['nome_exibido'] = base_item['nome_base']
    else:
        efeitos_a_adicionar = 0
        if raridade_final == "Incomum": efeitos_a_adicionar = 1
        elif raridade_final == "Raro": efeitos_a_adicionar = random.choice([1, 2])
        elif raridade_final == "Épico": efeitos_a_adicionar = random.choice([2, 3])
            
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

        nome_para_magia = base_item.get('nome_singular', base_item['nome_base'])
        lista_efeitos_desc = []
        prefixo_nome, sufixo_nome = "", ""
        for afixo in efeitos_escolhidos:
            if afixo['posicao'] == 'prefixo': prefixo_nome = f"{afixo['nome']} "
            else: sufixo_nome = f" {afixo['nome']}"
            lista_efeitos_desc.append(afixo['efeito'])
        
        nome_final = f"{prefixo_nome}{nome_para_magia}{sufixo_nome}"
        item_gerado['nome_exibido'] = nome_final.strip()
        item_gerado['descricao_final'] = f"{base_item['descricao_base']}\n<b>Efeitos Mágicos:</b> {'; '.join(lista_efeitos_desc)}"
        item_gerado['efeitos'] = lista_efeitos_desc

    max_engastes = base_item.get('engastes_max', 0)
    num_engastes = 0
    if max_engastes > 0:
        chance_base = 10 + (indice_final * 15)
        if random.randint(1, 100) <= chance_base:
            if random.randint(1, 100) <= (25 * indice_final):
                num_engastes = max_engastes
            else:
                num_engastes = random.randint(1, max_engastes)

    if num_engastes > 0:
        item_gerado['engastes'] = [{'gema': None} for _ in range(num_engastes)]

    return item_gerado

def _processar_tabela_de_loot(config, player_ref, tabela_id):
    tabela = config.LOOT_TABLES_DATA.get(tabela_id)
    if not tabela: return None
    loot_encontrado_texto, itens_para_adicionar = [], []
    moedas_str = tabela.get('moedas', "0")
    if moedas_str != "0":
        try:
            num_dados, tipo_dado = utils.parse_dado_str(moedas_str)
            if tipo_dado > 0:
                moedas_ganhas = sum(random.randint(1, tipo_dado) for _ in range(num_dados))
                if moedas_ganhas > 0:
                    loot_encontrado_texto.append(f"💰 {moedas_ganhas} Fragmentos de Ferro")
                    player_ref.update({'ficha.currency.fragmentos_ferro': firestore.Increment(moedas_ganhas)})
        except Exception as e: print(f"ERROR ao processar moedas na tabela {tabela_id}: {e}")
    for drop in tabela.get('drops', []):
        if random.randint(1, 100) <= drop.get('chance', 0):
            item_gerado = _gerar_item_magico(config, drop['id_item_base'], drop['raridade_maxima'])
            if item_gerado:
                nome_escapado = telegram_actions.escape_html(item_gerado['nome_exibido'])
                loot_encontrado_texto.append(f"✨ {nome_escapado} <code>({item_gerado['raridade']})</code>")
                itens_para_adicionar.append(item_gerado)
    gem_data = tabela.get('gems')
    if gem_data and random.randint(1, 100) <= gem_data.get('chance', 0):
        gema_gerada = _gerar_gema(config)
        if gema_gerada:
            nome_escapado = telegram_actions.escape_html(gema_gerada['nome_exibido'])
            loot_encontrado_texto.append(f"💎 {nome_escapado}")
            itens_para_adicionar.append(gema_gerada)
    if itens_para_adicionar: player_ref.update({'ficha.inventario': firestore.ArrayUnion(itens_para_adicionar)})
    return "Você encontra:\n" + "\n".join(loot_encontrado_texto) if loot_encontrado_texto else None

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
        memorias = ficha.get('memoria', [])
        memorias_recentes = memorias[-3:]
        memorias_formatadas = "\n- ".join(memorias_recentes) if memorias_recentes else "Nenhuma."
        prompt_simples = config.PROMPTS['narrador_simples'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(historico, ensure_ascii=False), memorias_formatadas, user_text)
        convo_simples = config.model.start_chat(history=historico)
        resposta_narrador = convo_simples.send_message(prompt_simples).text
        texto_seguro = telegram_actions.escape_html(resposta_narrador)
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_seguro)
        player_ref.update({'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [user_text]}, {'role': 'model', 'parts': [texto_seguro]}])})
        _registrar_memoria(config, player_ref, ficha, user_text, texto_seguro)

def handle_adventure_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    if callback_data == 'roll_d20':
        acao_pendente = player_data.get('acao_pendente')
        if acao_pendente:
            resultado_d20 = random.randint(1, 20)
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você lança seu destino aos ventos... o resultado do dado é <b>{resultado_d20}</b>!")
            ficha = player_data.get('ficha', {})
            historico = player_data.get('historico', [])
            memorias = ficha.get('memoria', [])
            memorias_recentes = memorias[-3:]
            memorias_formatadas = "\n- ".join(memorias_recentes) if memorias_recentes else "Nenhuma."
            prompt_final = config.PROMPTS['mestre_narrador'].format(json.dumps(ficha, ensure_ascii=False), json.dumps(historico, ensure_ascii=False), memorias_formatadas, acao_pendente, resultado_d20)
            convo = config.model.start_chat(history=historico)
            resposta_narrador = convo.send_message(prompt_final).text
            texto_narracao_limpo = re.sub(r'\[LOOT_TABLE:\s*\w+\s*\]', '', resposta_narrador).strip()
            texto_seguro = telegram_actions.escape_html(texto_narracao_limpo)
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_seguro)
            _registrar_memoria(config, player_ref, ficha, acao_pendente, texto_narracao_limpo)
            loot_tag_match = re.search(r'\[LOOT_TABLE:(\w+)\]', resposta_narrador)
            if loot_tag_match:
                tabela_id = loot_tag_match.group(1)
                mensagem_loot = _processar_tabela_de_loot(config, player_ref, tabela_id)
                if mensagem_loot:
                    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, mensagem_loot)
                    _registrar_memoria(config, player_ref, ficha, "Encontrou um tesouro", mensagem_loot)
            player_ref.update({'historico': firestore.ArrayUnion([{'role': 'user', 'parts': [acao_pendente]}, {'role': 'model', 'parts': [texto_narracao_limpo]}]), 'acao_pendente': firestore.DELETE_FIELD})