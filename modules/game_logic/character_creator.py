# modules/game_logic/character_creator.py
# Versão com correção no cálculo de pontos de vida.

from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils 

def _finalizar_criacao(config, chat_id, player_ref):
    """
    Finaliza o processo, calculando todos os atributos derivados e 
    construindo o objeto 'ficha' completo antes de salvar no Firestore.
    """
    ficha_doc = player_ref.get()
    if not ficha_doc.exists: return

    player_data = ficha_doc.to_dict()
    ficha_em_criacao = player_data.get('ficha_em_criacao', {})
    
    # --- Início da Construção da Ficha Final ---
    
    raca_key = ficha_em_criacao.get('raca', 'humano')
    classe_key = ficha_em_criacao.get('classe', 'guerreiro')
    raca_info = config.RACAS_DATA.get(raca_key, {})
    classe_info = config.CLASSES_DATA.get(classe_key, {})
    
    nivel = ficha_em_criacao.get('nivel', 1)
    bonus_proficiencia = utils.calcular_bonus_proficiencia(nivel)
    
    # --- ALTERAÇÃO ARQUITETURAL: Correção do Cálculo de Vida ---
    mod_con = ficha_em_criacao.get('modificadores', {}).get('con', 0)
    dado_vida_str = classe_info.get('dado_vida', 'd6') # Ex: "d10"

    try:
        # Extrai o valor numérico do dado de vida (remove o 'd' e converte para int)
        valor_max_dado_vida = int(dado_vida_str.replace('d', ''))
    except (ValueError, IndexError):
        valor_max_dado_vida = 6 # Um valor padrão seguro em caso de erro no JSON.

    # Agora a soma é feita entre dois números inteiros.
    vida_maxima = valor_max_dado_vida + mod_con
    # --- FIM DA ALTERAÇÃO ---
    
    ficha_final = {
        'nome': ficha_em_criacao.get('nome', 'Aventureiro'),
        'raca': raca_key,
        'classe': classe_key,
        'nivel': nivel,
        'marcos': 0,
        'background': ficha_em_criacao.get('background', ''),
        'motivacao': ficha_em_criacao.get('motivacao', ''),
        'falha': ficha_em_criacao.get('falha', ''),
        'atributos': ficha_em_criacao.get('atributos', {}),
        'modificadores': ficha_em_criacao.get('modificadores', {}),
        'proficiencia_bonus': bonus_proficiencia,
        'pontos_vida': { 'atuais': vida_maxima, 'maximos': vida_maxima, 'temporarios': 0 },
        'ca_final': utils.calcular_ca_final_com_equipamento(
            10 + ficha_em_criacao.get('modificadores', {}).get('des', 0),
            ficha_em_criacao.get('inventario', []),
            ficha_em_criacao.get('modificadores', {})
        ),
        'iniciativa': ficha_em_criacao.get('modificadores', {}).get('des', 0),
        'deslocamento': raca_info.get('deslocamento', '9m'),
        'dados_vida': { 'total': f"1{dado_vida_str}", 'restantes': f"1{dado_vida_str}" },
        'testes_resistencia_proficientes': classe_info.get('testes_resistencia_proficientes', []),
        'pericias_proficientes': ficha_em_criacao.get('pericias_proficientes', []),
        'inventario': ficha_em_criacao.get('inventario', []),
        'currency': ficha_em_criacao.get('currency', {}),
        'habilidades_aprendidas': ficha_em_criacao.get('habilidades_aprendidas', []) + raca_info.get('habilidades_fixas', []),
        'proficiencias_armas': list(set(raca_info.get('proficiencias_armas', []) + classe_info.get('proficiencias_armas', []))),
        'proficiencias_armaduras': list(set(raca_info.get('proficiencias_armaduras', []) + classe_info.get('proficiencias_armaduras', []))),
        'proficiencias_ferramentas': list(set(raca_info.get('proficiencias_ferramentas', []) + classe_info.get('proficiencias_ferramentas', []))),
        'proficiencias_idiomas': list(set(raca_info.get('idiomas', []) + classe_info.get('idiomas_adicionais', [])))
    }
    
    player_ref.set({'ficha': ficha_final, 'historico': []}, merge=True)
    player_ref.update({'estado_criacao': firestore.DELETE_FIELD, 'ficha_em_criacao': firestore.DELETE_FIELD})
    
    nome = telegram_actions.escape_html(ficha_final.get('nome', 'Aventureiro'))
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"✅ Perfeito! O seu personagem, <b>{nome}</b>, está pronto para a aventura.\n\nUse /start para iniciar a sua jornada.")

# O restante do ficheiro permanece inalterado, pois a lógica de fluxo está correta.

def _apresentar_escolha_pericias(config, chat_id, message_id, classe_key, player_ref, ficha_em_criacao):
    """Apresenta as opções de perícias para o jogador."""
    classe_info = config.CLASSES_DATA.get(classe_key, {})
    nome_classe_exibido = telegram_actions.escape_html(classe_info.get('nome_exibido', 'Sua classe'))
    num_escolhas = classe_info.get('pericias_escolha_num', 0)
    opcoes_pericias = [p for p in classe_info.get('pericias_opcoes', []) if p not in ficha_em_criacao.get('pericias_proficientes', [])]

    if num_escolhas <= 0 or not opcoes_pericias:
        player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
        if message_id: telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Todas as perícias de <b>{nome_classe_exibido}</b> foram definidas.")
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "📜 Agora, vamos à sua história. O que você fazia antes de se tornar um aventureiro?")
        return

    player_ref.update({'ficha_em_criacao.pericias_escolhas_restantes': num_escolhas, 'ficha_em_criacao.pericias_opcoes_atuais': opcoes_pericias})
    
    texto = f"Como <b>{nome_classe_exibido}</b>, você tem aptidão em diversas áreas. Escolha <b>{num_escolhas}</b> perícia(s) da lista abaixo.\n\nEscolha a sua primeira perícia:"
    botoes = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in opcoes_pericias]
    
    if message_id: telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Habilidade selecionada com sucesso!")
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': botoes})

def _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, classe_escolhida, player_ref, ficha_em_criacao):
    """Apresenta as sub-escolhas de uma classe."""
    habilidades_nv1 = [h for h in config.CLASSES_DATA[classe_escolhida].get('habilidades', []) if h['nivel'] == 1]
    nome_classe_exibido = config.CLASSES_DATA[classe_escolhida].get('nome_exibido', classe_escolhida)
    texto_base = f"Como um(a) <b>{nome_classe_exibido}</b>,"
    
    if classe_escolhida == 'guerreiro':
        opcoes = [h for h in habilidades_nv1 if "Estilo de Luta" in h['nome']]
        texto = f"{texto_base} o seu treinamento concedeu-lhe mestria numa técnica. Qual você aprimorou?"
        botoes = [[{'text': s['nome'].split(': ')[-1], 'callback_data': f"ability_choice:{s['nome']}"}] for s in opcoes]
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return

    player_ref.update({'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'})
    ficha_atualizada = player_ref.get().to_dict().get('ficha_em_criacao', {})
    telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você escolheu a classe <b>{nome_classe_exibido}</b>. Seus talentos iniciais foram definidos.")
    _apresentar_escolha_pericias(config, chat_id, None, classe_escolhida, player_ref, ficha_atualizada)

def handle_criar_personagem_command(config, user_id, chat_id, player_ref):
    """Inicia o processo de criação de personagem, já com a estrutura de moeda."""
    ficha_inicial = {
        'currency': { 'dracmas_aco': 0, 'cravos_prata': 0, 'fragmentos_ferro': 0 },
        'inventory': []
    }
    player_ref.set({'estado_criacao': 'AGUARDANDO_NOME', 'ficha_em_criacao': ficha_inicial}, merge=False)
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "⚔️ Vamos forjar o seu destino... Por qual nome você é conhecido nestas terras?")

def handle_creation_message(config, user_id, chat_id, user_text, player_ref, player_data):
    """Lida com as mensagens de texto durante a criação do personagem."""
    estado_atual = player_data.get('estado_criacao')
    
    if estado_atual == 'AGUARDANDO_NOME':
        nome_escapado = telegram_actions.escape_html(user_text)
        player_ref.update({'estado_criacao': 'AGUARDANDO_RACA', 'ficha_em_criacao.nome': user_text})
        texto = f"<b>{nome_escapado}</b>... um nome que ecoará pelas Terras de Aethel.\n\nCada povo tem as suas lendas e talentos. Qual é a sua origem? 📜"
        botoes_races = [[{'text': r_data['nome_exibido'], 'callback_data': f'race_choice:{r_key}'}] for r_key, r_data in sorted(config.RACAS_DATA.items())]
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': botoes_races})

    elif estado_atual == 'AGUARDANDO_BACKGROUND':
        player_ref.update({'estado_criacao': 'AGUARDANDO_MOTIVACAO', 'ficha_em_criacao.background': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Todo o herói tem uma história para contar. E toda a jornada tem um começo. O que te jogou na estrada em busca de aventura?")
    
    elif estado_atual == 'AGUARDANDO_MOTIVACAO':
        player_ref.update({'estado_criacao': 'AGUARDANDO_FALHA', 'ficha_em_criacao.motivacao': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Interessante motivação. Mas até os maiores heróis têm uma fraqueza que os assombra, uma falha que molda o seu caráter. Qual é a sua?")
        
    elif estado_atual == 'AGUARDANDO_FALHA':
        player_ref.update({'ficha_em_criacao.falha': user_text})
        _finalizar_criacao(config, chat_id, player_ref)

def handle_creation_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    """Lida com os callbacks de botões durante a criação do personagem."""
    ficha_em_criacao = player_data.get('ficha_em_criacao', {})
    
    if callback_data.startswith('race_choice:'):
        raca_key = callback_data.split(':', 1)[1]
        raca_info = config.RACAS_DATA.get(raca_key, {})
        ficha_em_criacao['raca'] = raca_key
        if 'ajustes_atributo' in raca_info: ficha_em_criacao['ajustes_raciais'] = raca_info['ajustes_atributo']
        if 'pericias_fixas' in raca_info: ficha_em_criacao['pericias_proficientes'] = raca_info['pericias_fixas']
        
        player_ref.update({'ficha_em_criacao': ficha_em_criacao, 'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'})
        
        nome_raca_escapado = telegram_actions.escape_html(raca_info.get('nome_exibido', ''))
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você escolheu ser um(a) <b>{nome_raca_escapado}</b>.")
        
        valores = utils.ARRAY_PADRAO_ATRIBUTOS
        valores_formatados = f"({', '.join(map(str, valores))})"
        texto = f"Agora, defina seus Atributos Fundamentais usando os valores: <b>{valores_formatados}</b>.\n\nComeçando pelo valor mais alto, <b>{valores[0]}</b>. Onde você deseja aplicá-lo?"
        
        botoes_objetos = [{'text': f'{utils.obter_nome_completo_atributo(attr_k)} ({attr_k})', 'callback_data': f'distribute_attr:{valores[0]}:{attr_k}'} for attr_k in utils.ATRIBUTOS_LISTA]
        teclado_final = [botoes_objetos[i:i + 2] for i in range(0, len(botoes_objetos), 2)]
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': teclado_final})

    elif callback_data.startswith('distribute_attr:'):
        _, v_str, attr_key_upper = callback_data.split(':', 2)
        v_int = int(v_str)
        atributos_base = ficha_em_criacao.get('atributos_base', {})
        valores_pendentes = ficha_em_criacao.get('valores_atributos_pendentes', list(utils.ARRAY_PADRAO_ATRIBUTOS))
        
        if attr_key_upper.lower() in atributos_base: return
        
        atributos_base[attr_key_upper.lower()] = v_int
        if v_int in valores_pendentes: valores_pendentes.remove(v_int)
        player_ref.update({'ficha_em_criacao.atributos_base': atributos_base, 'ficha_em_criacao.valores_atributos_pendentes': valores_pendentes})
        
        nome_attr_escapado = telegram_actions.escape_html(utils.obter_nome_completo_atributo(attr_key_upper))
        if not valores_pendentes:
            atributos_finais = dict(atributos_base)
            ajustes_raciais = ficha_em_criacao.get('ajustes_raciais', {})
            for attr, bonus in ajustes_raciais.items(): atributos_finais[attr] = atributos_finais.get(attr, 0) + bonus
            modificadores = {attr: utils.calcular_modificador(val) for attr, val in atributos_finais.items()}
            
            player_ref.update({'estado_criacao': 'AGUARDANDO_CLASSE', 'ficha_em_criacao.atributos': atributos_finais, 'ficha_em_criacao.modificadores': modificadores})
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você atribuiu <b>{v_str}</b> para <b>{nome_attr_escapado}</b>.\n\n✅ Atributos definidos e bónus raciais aplicados!")
            
            texto_resumo = "Seus Atributos Finais são:\n"
            for attr, val in sorted(atributos_finais.items()):
                mod = modificadores.get(attr, 0)
                sinal = '+' if mod >= 0 else ''
                texto_resumo += f"<b>{utils.obter_nome_completo_atributo(attr.upper())}</b>: {val} <code>({sinal}{mod})</code>\n"
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_resumo)
            
            texto_classe = "\nAgora, escolha a sua vocação, o seu chamado para a aventura:"
            botoes_classes = [[{'text': c_data['nome_exibido'], 'callback_data': f'class_choice:{c_key}'}] for c_key, c_data in sorted(config.CLASSES_DATA.items())]
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_classe, {'inline_keyboard': botoes_classes})
        else:
            prox_valor = valores_pendentes[0]
            attrs_disponiveis = [key for key in utils.ATRIBUTOS_LISTA if key.lower() not in atributos_base]
            texto_proximo = f"Você atribuiu <b>{v_str}</b> para <b>{nome_attr_escapado}</b>.\n\nPróximo valor a distribuir: <b>{prox_valor}</b>. Onde o aplicará?"
            
            botoes_objetos = [{'text': f'{utils.obter_nome_completo_atributo(attr_k)} ({attr_k})', 'callback_data': f'distribute_attr:{prox_valor}:{attr_k}'} for attr_k in attrs_disponiveis]
            teclado_final = [botoes_objetos[i:i + 2] for i in range(0, len(botoes_objetos), 2)]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto_proximo, {'inline_keyboard': teclado_final})
            
    elif callback_data.startswith('class_choice:'):
        classe_key = callback_data.split(':', 1)[1]
        player_ref.update({'estado_criacao': 'AGUARDANDO_HABILIDADE', 'ficha_em_criacao.classe': classe_key})
        _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, classe_key, player_ref, ficha_em_criacao)
    
    elif callback_data.startswith('ability_choice:'):
        habilidade_escolhida = callback_data.split(':', 1)[1]
        habs_atuais = ficha_em_criacao.get('habilidades_aprendidas', [])
        if habilidade_escolhida not in habs_atuais:
            habs_atuais.append(habilidade_escolhida)
        
        player_ref.update({ 'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS', 'ficha_em_criacao.habilidades_aprendidas': habs_atuais })
        
        classe_key = ficha_em_criacao.get('classe')
        hab_escapada = telegram_actions.escape_html(habilidade_escolhida)
        texto_confirmacao = f"✨ Habilidade <b>{hab_escapada}</b> selecionada!"
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto_confirmacao)
        _apresentar_escolha_pericias(config, chat_id, None, classe_key, player_ref, ficha_em_criacao)
        
    elif callback_data.startswith('skill_choice:'):
        pericia_escolhida = callback_data.split(':',1)[1]
        pericias_proficientes = ficha_em_criacao.get('pericias_proficientes', [])
        escolhas_restantes = ficha_em_criacao.get('pericias_escolhas_restantes', 1)
        opcoes_atuais = ficha_em_criacao.get('pericias_opcoes_atuais', [])

        if pericia_escolhida not in pericias_proficientes:
            pericias_proficientes.append(pericia_escolhida)
        if pericia_escolhida in opcoes_atuais: opcoes_atuais.remove(pericia_escolhida)
        escolhas_restantes -= 1

        player_ref.update({
            'ficha_em_criacao.pericias_proficientes': pericias_proficientes,
            'ficha_em_criacao.pericias_escolhas_restantes': escolhas_restantes,
            'ficha_em_criacao.pericias_opcoes_atuais': opcoes_atuais
        })
        
        pericia_escapada = telegram_actions.escape_html(pericia_escolhida)
        if escolhas_restantes <= 0:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Perícia <b>{pericia_escapada}</b> adicionada. Todas as perícias de classe foram escolhidas.")
            player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "📜 Agora, vamos à sua história. O que você fazia antes de se tornar um aventureiro?")
        else:
            texto = f"Perícia <b>{pericia_escapada}</b> adicionada.\nEscolha mais <b>{escolhas_restantes}</b> perícia(s):"
            botoes_pericias = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in opcoes_atuais]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes_pericias})