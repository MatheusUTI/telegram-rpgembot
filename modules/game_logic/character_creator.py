# modules/game_logic/character_creator.py
from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils # Importa o nosso novo módulo de utilidades

# ==============================================================================
# === FUNÇÕES AUXILIARES DE CRIAÇÃO (PRIVADAS A ESTE MÓDULO)                 ===
# ==============================================================================

def _apresentar_escolha_pericias(config, chat_id, message_id, classe_key, player_ref, ficha_em_criacao):
    """
    Apresenta as opções de perícias para o jogador.
    Se não houver escolhas, finaliza esta etapa e avança para o background.
    """
    classe_info = config.CLASSES_DATA.get(classe_key, {})
    nome_classe_exibido = classe_info.get('nome_exibido', 'Sua classe')
    num_escolhas_total = classe_info.get('pericias_escolha_num', 0)
    opcoes_pericias_classe = classe_info.get('pericias_opcoes', [])
    pericias_ja_proficientes = ficha_em_criacao.get('pericias_proficientes', [])
    opcoes_reais_para_escolha = [p for p in opcoes_pericias_classe if p not in pericias_ja_proficientes]

    if num_escolhas_total <= 0 or not opcoes_reais_para_escolha:
        player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
        equipamento = classe_info.get('equipamento_inicial', [])
        inventario_atual = ficha_em_criacao.get('inventario', [])
        for eq_item in equipamento:
            nome_item_novo = eq_item.get("nome") if isinstance(eq_item, dict) else eq_item
            if not any((item_inv.get("nome") if isinstance(item_inv, dict) else item_inv) == nome_item_novo for item_inv in inventario_atual):
                inventario_atual.append(eq_item)

        ca_final = utils.calcular_ca_final_com_equipamento(
            ficha_em_criacao.get('ca_base', 10), inventario_atual, ficha_em_criacao.get('modificadores', {}))
        
        player_ref.update({
            'ficha_em_criacao.inventario': inventario_atual,
            'ficha_em_criacao.ca_final': ca_final,
            'ficha_em_criacao.pericias_escolhas_restantes': firestore.DELETE_FIELD,
            'ficha_em_criacao.pericias_opcoes_atuais': firestore.DELETE_FIELD
        })
        msg_final_pericias = f"Todas as perícias de *{nome_classe_exibido}* foram definidas.\nEquipamento inicial adicionado. Sua Classe de Armadura (CA) final é *{ca_final}*."
        if message_id: telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, msg_final_pericias)
        else: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, msg_final_pericias)
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Interessante... Agora, vamos à sua história. O que você fazia antes de se tornar um aventureiro?")
        return

    player_ref.update({
        'ficha_em_criacao.pericias_escolhas_restantes': num_escolhas_total,
        'ficha_em_criacao.pericias_opcoes_atuais': opcoes_reais_para_escolha
    })
    
    # --- INÍCIO DA CORREÇÃO ---
    texto = f"Como *{nome_classe_exibido}*, você tem aptidão em diversas áreas. Escolha *{num_escolhas_total}* perícia(s) da lista abaixo para se especializar.\n\nEscolha sua primeira perícia:"
    
    # Criar uma lista simples de botões, cada um em sua própria linha.
    # Isso é mais seguro e evita erros de formatação com o Telegram.
    botoes_simples = []
    for pericia in opcoes_reais_para_escolha:
        botoes_simples.append(
            [{'text': pericia, 'callback_data': f'skill_choice:{pericia}'}]
        )

    reply_markup = {'inline_keyboard': botoes_simples}
    
    # A mensagem anterior (escolha de classe/habilidade) já foi editada para confirmar.
    # Esta sempre será uma NOVA mensagem com os botões de perícia.
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, reply_markup)
    # --- FIM DA CORREÇÃO ---


def _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, classe_escolhida, player_ref, ficha_em_criacao):
    habilidades_nivel_1 = [h for h in config.CLASSES_DATA[classe_escolhida].get('habilidades', []) if h['nivel'] == 1]
    nome_classe_exibido = config.CLASSES_DATA[classe_escolhida].get('nome_exibido', classe_escolhida)
    texto_base_escolha = f"Como um(a) *{nome_classe_exibido}*,"

    if classe_escolhida == 'clerigo':
        dominios = [h for h in habilidades_nivel_1 if "Domínio Divino:" in h['nome']]
        if dominios:
            texto = f"{texto_base_escolha} sua fé se manifesta através de um Domínio Divino. Qual você devotará?"
            botoes = [[{'text': f"Domínio: {d['nome'].split(': ')[-1].replace(' (Exemplo)','')}", 'callback_data': f"subchoice:dominio:{d['nome']}"}] for d in dominios]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return
    elif classe_escolhida == 'guerreiro':
        estilos = [h for h in habilidades_nivel_1 if "Estilo de Luta" in h['nome']]
        if estilos:
            texto = f"{texto_base_escolha} seu treinamento lhe concedeu maestria em uma técnica. Qual você aprimorou?"
            botoes = [[{'text': f"Estilo: {s['nome'].split(': ')[-1]}", 'callback_data': f"subchoice:estilo_luta:{s['nome']}"}] for s in estilos]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return
    
    habilidades_gerais_nv1 = [h for h in habilidades_nivel_1 if "Domínio Divino:" not in h['nome'] and ("Estilo de Luta" not in h['nome'] or classe_escolhida != 'guerreiro')]
    if habilidades_gerais_nv1 and len(habilidades_gerais_nv1) > 1 and classe_escolhida not in ['barbaro', 'bardo', 'mago', 'clerigo', 'guerreiro']:
        texto = f"{texto_base_escolha} você possui talentos únicos. Escolha UMA habilidade inicial para focar:"
        botoes = [[{'text': hab['nome'], 'callback_data': f"ability_choice:{hab['nome']}"}] for hab in habilidades_gerais_nv1[:4]]
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return

    habilidades_finais_nv1 = ficha_em_criacao.get('habilidades_aprendidas', [])
    for hab in habilidades_gerais_nv1:
        if hab['nome'] not in habilidades_finais_nv1: habilidades_finais_nv1.append(hab['nome'])
    
    oficio = config.CLASSES_DATA.get(classe_escolhida, {}).get('oficio', 'Nenhum'); mods = ficha_em_criacao.get('modificadores', {}); c_info = config.CLASSES_DATA.get(classe_escolhida, {})
    pv_max = ficha_em_criacao.get('pv_maximos', 0); ca_base = ficha_em_criacao.get('ca_base', 10 + mods.get('des',0))
    if pv_max == 0:
        if 'dado_vida' in c_info and 'con' in mods:
            try: v_dv = int(c_info['dado_vida'].replace('d','')); pv_max = v_dv + mods['con']
            except: pv_max = 8 + mods.get('con', 0)
        else: pv_max = 8 + mods.get('con', 0)
    
    player_ref.update({
        'ficha_em_criacao.habilidades_aprendidas': list(set(habilidades_finais_nv1)), 'ficha_em_criacao.oficio': oficio, 'ficha_em_criacao.pv_maximos': pv_max, 
        'ficha_em_criacao.pv_atuais': pv_max, 'ficha_em_criacao.ca_base': ca_base, 'ficha_em_criacao.bonus_proficiencia': 2, 'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'
    })
    ficha_att_doc = player_ref.get(); ficha_para_pericias = ficha_att_doc.to_dict().get('ficha_em_criacao',{})
    telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Talentos de *{nome_classe_exibido}* definidos!\nPV: {pv_max}, CA Base (sem armadura): {ca_base}.")
    _apresentar_escolha_pericias(config, chat_id, None, classe_escolhida, player_ref, ficha_para_pericias)

# ==============================================================================
# === HANDLERS DE CRIAÇÃO (FUNÇÕES PÚBLICAS DO MÓDULO)                      ===
# ==============================================================================

def handle_criar_personagem_command(config, user_id, chat_id, player_ref):
    """Inicia ou reinicia o fluxo de criação de personagem."""
    player_ref.set({
        'estado_criacao': 'AGUARDANDO_NOME',
        'ficha_em_criacao': {'pericias_proficientes': [], 'inventario': []},
        'historico': []
    }, merge=False)
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Vamos forjar seu destino... Por qual nome você é conhecido?")

def handle_creation_message(config, user_id, chat_id, user_text, player_ref, player_data):
    """Trata as mensagens de texto durante a criação do personagem."""
    estado_atual = player_data.get('estado_criacao')
    
    if estado_atual == 'AGUARDANDO_NOME':
        player_ref.update({'estado_criacao': 'AGUARDANDO_RACA', 'ficha_em_criacao.nome': user_text})
        texto_raca = f"Excelente nome, *{user_text}*!\n\nCada povo em Aethel tem suas lendas e talentos. Qual é a sua origem? Escolha sua Raça:"
        if config.RACAS_DATA:
            botoes_r = [[{'text': r_data['nome_exibido'], 'callback_data': f'race_choice:{r_key}'}] for r_key, r_data in config.RACAS_DATA.items()]
            botoes_r.sort(key=lambda r: r[0]['text'])
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_raca, {'inline_keyboard': botoes_r})
        else:
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "AVISO: Raças não carregadas. Pulando para atributos.")
            player_ref.update({'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'})
            primeiro_val = utils.ARRAY_PADRAO_ATRIBUTOS[0]
            txt_dist = "Vamos distribuir seus Atributos usando os valores: 15, 14, 13, 12, 10, 8.\n"
            txt_dist += f"Começando pelo valor mais alto, *{primeiro_val}*. Em qual atributo você deseja aplicá-lo?"
            b_dist_buttons = []
            for attr_k_upper in utils.ATRIBUTOS_LISTA:
                b_dist_buttons.append({'text': f'{utils.obter_nome_completo_atributo(attr_k_upper)} ({attr_k_upper})', 'callback_data': f'distribute_attr:{primeiro_val}:{attr_k_upper}'})
            reply_markup_dist_fallback = {'inline_keyboard': [b_dist_buttons[i:i + 2] for i in range(0, len(b_dist_buttons), 2)]}
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, txt_dist, reply_markup_dist_fallback)

    elif estado_atual == 'AGUARDANDO_BACKGROUND':
        player_ref.update({'estado_criacao': 'AGUARDANDO_MOTIVACAO', 'ficha_em_criacao.background': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Interessante... E toda jornada tem um começo. O que te jogou na estrada em busca de aventura?")
    
    elif estado_atual == 'AGUARDANDO_MOTIVACAO':
        player_ref.update({'estado_criacao': 'AGUARDANDO_FALHA', 'ficha_em_criacao.motivacao': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Até os maiores heróis têm uma fraqueza que os assombra. Qual é a sua?")
        
    elif estado_atual == 'AGUARDANDO_FALHA':
        ficha_final_doc = player_ref.get()
        ficha_final = ficha_final_doc.to_dict().get('ficha_em_criacao', {})
        ficha_final['falha'] = user_text
        ficha_final.update({'nivel': 1, 'marcos': 0})
        
        if 'ca_final' not in ficha_final:
            ficha_final['ca_final'] = utils.calcular_ca_final_com_equipamento(
                ficha_final.get('ca_base', 10), ficha_final.get('inventario', []), ficha_final.get('modificadores', {}))
        
        if 'bonus_proficiencia' not in ficha_final: ficha_final['bonus_proficiencia'] = 2
        if 'recursos' not in ficha_final: ficha_final['recursos'] = {} 
        if 'magias' not in ficha_final: ficha_final['magias'] = {'conhecidas': [], 'preparadas': [], 'slots_n1_atuais': 0, 'slots_n1_max':0}
        
        player_ref.set({'ficha': ficha_final, 'historico': player_data.get('historico', [])}, merge=True)
        player_ref.update({'estado_criacao': firestore.DELETE_FIELD, 'ficha_em_criacao': firestore.DELETE_FIELD})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Perfeito! Seu personagem está pronto!\n\nUse /start para iniciar sua jornada.")

def handle_creation_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    """Trata os cliques em botões durante a criação do personagem."""
    ficha_em_criacao = player_data.get('ficha_em_criacao', {})
    
    if callback_data.startswith('race_choice:'):
        raca_key = callback_data.split(':', 1)[1]
        if raca_key not in config.RACAS_DATA:
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Raça inválida."); return
        
        raca_info = config.RACAS_DATA[raca_key]
        ficha_em_criacao['raca'] = raca_key; ficha_em_criacao['nome_raca_exibido'] = raca_info['nome_exibido']
        ficha_em_criacao['tracos_raciais'] = raca_info.get('tracos_raciais', [])
        ficha_em_criacao['deslocamento'] = raca_info.get('deslocamento', 9)
        pericias_atuais = ficha_em_criacao.get('pericias_proficientes', [])
        if "Proficiência (Percepção)" in raca_info.get('tracos_raciais', []): pericias_atuais.append("Percepção")
        ficha_em_criacao['pericias_proficientes'] = list(set(pericias_atuais))
        player_ref.update({'ficha_em_criacao': ficha_em_criacao, 'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'})
        
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você escolheu ser um(a) *{raca_info['nome_exibido']}*.")
        
        primeiro_valor = utils.ARRAY_PADRAO_ATRIBUTOS[0]
        texto = f"Excelente escolha! Ser um(a) *{raca_info['nome_exibido']}* lhe confere certas aptidões.\n\nAgora, defina seus Atributos Fundamentais (15, 14, 13, 12, 10, 8).\n\nComeçando pelo valor mais alto, *{primeiro_valor}*. Em qual atributo você deseja aplicá-lo?"
        botoes = []
        for attr_k in utils.ATRIBUTOS_LISTA: botoes.append({'text': f'{utils.obter_nome_completo_atributo(attr_k)} ({attr_k})', 'callback_data': f'distribute_attr:{primeiro_valor}:{attr_k}'})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': [botoes[i:i + 2] for i in range(0, len(botoes), 2)]})

    elif callback_data.startswith('distribute_attr:'):
        _, v_str, attr_key_upper = callback_data.split(':', 2); v_int = int(v_str)
        a_base = ficha_em_criacao.get('atributos_base', {}); v_pend = ficha_em_criacao.get('valores_atributos_pendentes', list(utils.ARRAY_PADRAO_ATRIBUTOS))
        
        if attr_key_upper.lower() in a_base: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"Atributo {utils.obter_nome_completo_atributo(attr_key_upper)} já definido."); return
        if v_int not in v_pend: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"Valor {v_int} não disponível."); return
        
        a_base[attr_key_upper.lower()] = v_int; v_pend.remove(v_int)
        player_ref.update({'ficha_em_criacao.atributos_base': a_base, 'ficha_em_criacao.valores_atributos_pendentes': v_pend})
        
        if not v_pend:
            a_finais = dict(a_base); r_key = ficha_em_criacao.get('raca')
            if r_key and r_key in config.RACAS_DATA:
                ajustes = config.RACAS_DATA[r_key].get('ajustes_atributo', {});
                for attr_k, bonus in ajustes.items(): a_finais[attr_k] = a_finais.get(attr_k, 0) + bonus
            mods = {attr: utils.calcular_modificador(val) for attr, val in a_finais.items()}
            player_ref.update({'estado_criacao': 'AGUARDANDO_CLASSE', 'ficha_em_criacao.atributos': a_finais, 'ficha_em_criacao.modificadores': mods})
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você atribuiu {v_int} para {utils.obter_nome_completo_atributo(attr_key_upper)}.\nAtributos base definidos. Bônus raciais aplicados!")
            
            # --- INÍCIO DA CORREÇÃO ---
            texto_resumo_atributos = "Perfeito! Seus Atributos Finais são:\n"
            resumo_linhas = []
            for attr_k_l, attr_v in a_finais.items():
                mod = mods.get(attr_k_l, 0)
                sinal_mod = '+' if mod >= 0 else ''
                resumo_linhas.append(f"{utils.obter_nome_completo_atributo(attr_k_l.upper())}: {attr_v} (Mod: {sinal_mod}{mod})")
            
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_resumo_atributos + "\n".join(resumo_linhas))
            
            texto_escolha_classe = "\nAgora, escolha sua vocação, seu chamado para a aventura:"
            botoes_classes = [[{'text': c_d['nome_exibido'], 'callback_data': f'class_choice:{c_k}'}] for c_k, c_d in config.CLASSES_DATA.items()]
            botoes_classes.sort(key=lambda r: r[0]['text'])
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_escolha_classe, {'inline_keyboard': botoes_classes})
            # --- FIM DA CORREÇÃO ---
        else:
            prox_v = v_pend[0]; attrs_d = [a_k for a_k in utils.ATRIBUTOS_LISTA if a_k.lower() not in a_base]
            texto_n = f"Você atribuiu {v_int} para {utils.obter_nome_completo_atributo(attr_key_upper)}.\n\nPróximo valor a distribuir: *{prox_v}*. Em qual atributo restante você o aplicará?"
            b_prox = [];
            for a_d_k in attrs_d: b_prox.append({'text': f'{utils.obter_nome_completo_atributo(a_d_k)} ({a_d_k})', 'callback_data': f'distribute_attr:{prox_v}:{a_d_k}'})
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto_n, {'inline_keyboard': [b_prox[i:i + 2] for i in range(0, len(b_prox), 2)]})

    elif callback_data.startswith('class_choice:'):
        c_key = callback_data.split(':', 1)[1]; c_info = config.CLASSES_DATA.get(c_key, {})
        p_fixas = c_info.get('pericias_fixas', []); p_atuais = ficha_em_criacao.get('pericias_proficientes', [])
        for p_f in p_fixas:
            if p_f not in p_atuais: p_atuais.append(p_f)
        player_ref.update({'estado_criacao': 'AGUARDANDO_HABILIDADE_INICIAL', 'ficha_em_criacao.classe': c_key, 'ficha_em_criacao.pericias_proficientes': list(set(p_atuais))})
        f_att_doc = player_ref.get(); f_para_habs = f_att_doc.to_dict().get('ficha_em_criacao', {})
        _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, c_key, player_ref, f_para_habs)

    elif callback_data.startswith('subchoice:') or callback_data.startswith('ability_choice:'):
        parts = callback_data.split(':', 2)
        tipo_esc, subtipo_ou_hab, hab_final = parts[0], parts[1], parts[2] if tipo_esc == 'subchoice' else parts[1]
        classe_p = ficha_em_criacao.get('classe');
        if not classe_p: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Erro: Classe não definida. Reinicie."); return
        habs_atuais = ficha_em_criacao.get('habilidades_aprendidas', []);
        if hab_final not in habs_atuais: habs_atuais.append(hab_final)
        habs_nv1 = [h for h in config.CLASSES_DATA.get(classe_p, {}).get('habilidades', []) if h['nivel'] == 1]
        for hab_p in habs_nv1:
            is_sub = "Domínio Divino:" in hab_p['nome'] or "Estilo de Luta" in hab_p['nome']
            if hab_p['nome'] != hab_final and not is_sub and hab_p['nome'] not in habs_atuais: habs_atuais.append(hab_p['nome'])
        player_ref.update({'ficha_em_criacao.habilidades_aprendidas': list(set(habs_atuais)), 'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'})
        f_para_pericias_doc = player_ref.get(); f_para_pericias = f_para_pericias_doc.to_dict().get('ficha_em_criacao',{})
        _apresentar_escolha_pericias(config, chat_id, message_id, classe_p, player_ref, f_para_pericias)

    elif callback_data.startswith('skill_choice:'):
        p_esc = callback_data.split(':',1)[1]
        p_prof = ficha_em_criacao.get('pericias_proficientes', []); p_rest = ficha_em_criacao.get('pericias_escolhas_restantes', 0); p_opts = ficha_em_criacao.get('pericias_opcoes_atuais', [])
        
        if p_esc in p_prof: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Já proficiente. Escolha outra."); return
        if p_esc not in p_opts: telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Opção inválida."); return
        
        p_prof.append(p_esc); p_rest -= 1;
        if p_esc in p_opts: p_opts.remove(p_esc)
        
        player_ref.update({
            'ficha_em_criacao.pericias_proficientes': list(set(p_prof)),
            'ficha_em_criacao.pericias_escolhas_restantes': p_rest,
            'ficha_em_criacao.pericias_opcoes_atuais': p_opts
        })
        
        if p_rest <= 0 or not p_opts:
            c_key = ficha_em_criacao.get('classe'); c_info = config.CLASSES_DATA.get(c_key,{})
            equipamento = c_info.get('equipamento_inicial', []); inv = ficha_em_criacao.get('inventario', [])
            for item_novo in equipamento:
                n_novo = item_novo.get("nome") if isinstance(item_novo, dict) else item_novo
                if not any((i.get("nome") if isinstance(i, dict) else i) == n_novo for i in inv): inv.append(item_novo)
            ca_final = utils.calcular_ca_final_com_equipamento(
                ficha_em_criacao.get('ca_base', 10), inv, ficha_em_criacao.get('modificadores',{}))
            
            player_ref.update({
                'estado_criacao': 'AGUARDANDO_BACKGROUND', 'ficha_em_criacao.inventario': inv, 'ficha_em_criacao.ca_final': ca_final,
                'ficha_em_criacao.pericias_escolhas_restantes': firestore.DELETE_FIELD, 'ficha_em_criacao.pericias_opcoes_atuais': firestore.DELETE_FIELD
            })
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Perícia *{p_esc}* adicionada. Todas as perícias de classe foram escolhidas.")
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"Equipamento inicial adicionado. Sua CA Final é *{ca_final}*.\n\nAgora, vamos à sua história. O que você fazia?")
        else:
            texto = f"Perícia *{p_esc}* adicionada.\nEscolha mais {p_rest} perícia(s):"
            b_prox = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in p_opts]
            reply_markup = {'inline_keyboard': [b_prox[i:i + 3] for i in range(0, len(b_prox), 3)] if len(b_prox) > 3 else b_prox}
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, reply_markup)