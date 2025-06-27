# modules/game_logic/character_creator.py
# Versão final com lógica completa e formatação MarkdownV2 segura.

from firebase_admin import firestore
from modules import telegram_actions
from modules.game_logic import utils 

# ==============================================================================
# === FUNÇÕES AUXILIARES DE CRIAÇÃO (PRIVADAS A ESTE MÓDULO)                 ===
# ==============================================================================

def _finalizar_criacao(config, chat_id, player_ref):
    """Finaliza o processo de criação, monta a ficha e limpa os estados temporários."""
    ficha_doc = player_ref.get()
    if not ficha_doc.exists: return

    player_data = ficha_doc.to_dict()
    ficha_em_criacao = player_data.get('ficha_em_criacao', {})
    
    # Adicionar dados finais por omissão
    ficha_em_criacao.setdefault('nivel', 1)
    ficha_em_criacao.setdefault('marcos', 0)
    
    if 'ca_final' not in ficha_em_criacao:
        ficha_em_criacao['ca_final'] = utils.calcular_ca_final_com_equipamento(
            ficha_em_criacao.get('ca_base', 10), ficha_em_criacao.get('inventario', []), ficha_em_criacao.get('modificadores', {})
        )
    
    # Atualiza o documento principal com a ficha finalizada
    player_ref.set({'ficha': ficha_em_criacao, 'historico': []}, merge=True)
    # Remove os campos temporários de criação
    player_ref.update({'estado_criacao': firestore.DELETE_FIELD, 'ficha_em_criacao': firestore.DELETE_FIELD})
    
    nome_escapado = telegram_actions.escape_markdown_v2(ficha_em_criacao.get('nome', 'Aventureiro'))
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, f"✅ Perfeito\\! O seu personagem, *{nome_escapado}*, está pronto para a aventura\\!\n\nUse /start para iniciar a sua jornada e descobrir o seu destino nas Terras de Aethel\\.")

def _apresentar_escolha_pericias(config, chat_id, message_id, classe_key, player_ref, ficha_em_criacao):
    """Apresenta as opções de perícias para o jogador."""
    classe_info = config.CLASSES_DATA.get(classe_key, {})
    nome_classe_exibido = telegram_actions.escape_markdown_v2(classe_info.get('nome_exibido', 'Sua classe'))
    num_escolhas = classe_info.get('pericias_escolha_num', 0)
    opcoes_pericias = [p for p in classe_info.get('pericias_opcoes', []) if p not in ficha_em_criacao.get('pericias_proficientes', [])]

    if num_escolhas <= 0 or not opcoes_pericias:
        player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
        if message_id: telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Todas as perícias de *{nome_classe_exibido}* foram definidas\\.")
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "📜 Agora, vamos à sua história\\. O que você fazia antes de se tornar um aventureiro\\?")
        return

    player_ref.update({'ficha_em_criacao.pericias_escolhas_restantes': num_escolhas, 'ficha_em_criacao.pericias_opcoes_atuais': opcoes_pericias})
    
    texto = f"Como *{nome_classe_exibido}*, você tem aptidão em diversas áreas\\. Escolha *{num_escolhas}* perícia\\(s\\) da lista abaixo para se especializar\\.\n\nEscolha a sua primeira perícia:"
    botoes = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in opcoes_pericias]
    
    if message_id: telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Habilidade selecionada com sucesso\\!")
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': botoes})

def _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, classe_escolhida, player_ref, ficha_em_criacao):
    """Apresenta as sub-escolhas de uma classe, como Estilo de Luta."""
    habilidades_nv1 = [h for h in config.CLASSES_DATA[classe_escolhida].get('habilidades', []) if h['nivel'] == 1]
    nome_classe_exibido = telegram_actions.escape_markdown_v2(config.CLASSES_DATA[classe_escolhida].get('nome_exibido', classe_escolhida))
    texto_base = f"Como um\\(a\\) *{nome_classe_exibido}*,"
    
    opcoes = []
    if classe_escolhida == 'guerreiro':
        opcoes = [h for h in habilidades_nv1 if "Estilo de Luta" in h['nome']]
        texto = f"{texto_base} o seu treinamento concedeu-lhe mestria numa técnica\\. Qual você aprimorou\\?"
        botoes = [[{'text': s['nome'].split(': ')[-1], 'callback_data': f"ability_choice:{s['nome']}"}] for s in opcoes]
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return
    elif classe_escolhida == 'clerigo':
        opcoes = [h for h in habilidades_nv1 if "Domínio Divino" in h['nome']]
        texto = f"{texto_base} a sua fé manifesta-se através de um Domínio Divino\\. A qual você se devota\\?"
        botoes = [[{'text': d['nome'].split(': ')[-1], 'callback_data': f"ability_choice:{d['nome']}"}] for d in opcoes]
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes}); return

    habs_atuais = ficha_em_criacao.get('habilidades_aprendidas', [])
    for hab in habilidades_nv1:
        if hab['nome'] not in habs_atuais: habs_atuais.append(hab['nome'])
    
    player_ref.update({'ficha_em_criacao.habilidades_aprendidas': habs_atuais, 'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'})
    ficha_atualizada = player_ref.get().to_dict().get('ficha_em_criacao', {})
    telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você escolheu a classe *{nome_classe_exibido}*\\. Seus talentos iniciais foram definidos\\.")
    _apresentar_escolha_pericias(config, chat_id, None, classe_escolhida, player_ref, ficha_atualizada)


# ==============================================================================
# === HANDLERS DE CRIAÇÃO (FUNÇÕES PÚBLICAS DO MÓDULO)                      ===
# ==============================================================================

def handle_criar_personagem_command(config, user_id, chat_id, player_ref):
    player_ref.set({'estado_criacao': 'AGUARDANDO_NOME', 'ficha_em_criacao': {}}, merge=False)
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "⚔️ Vamos forjar o seu destino\\.\\.\\. Por qual nome você é conhecido nestas terras\\?")

def handle_creation_message(config, user_id, chat_id, user_text, player_ref, player_data):
    estado_atual = player_data.get('estado_criacao')
    
    if estado_atual == 'AGUARDANDO_NOME':
        nome_escapado = telegram_actions.escape_markdown_v2(user_text)
        player_ref.update({'estado_criacao': 'AGUARDANDO_RACA', 'ficha_em_criacao.nome': user_text})
        texto = f"*{nome_escapado}*\\.\\.\\. um nome que ecoará pelas Terras de Aethel\\.\n\nCada povo tem as suas lendas e talentos\\. Qual é a sua origem\\? 📜"
        botoes_races = [[{'text': r_data['nome_exibido'], 'callback_data': f'race_choice:{r_key}'}] for r_key, r_data in sorted(config.RACAS_DATA.items())]
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': botoes_races})

    elif estado_atual == 'AGUARDANDO_BACKGROUND':
        player_ref.update({'estado_criacao': 'AGUARDANDO_MOTIVACAO', 'ficha_em_criacao.background': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Todo o herói tem uma história para contar\\. E toda a jornada tem um começo\\. O que te jogou na estrada em busca de aventura\\?")
    
    elif estado_atual == 'AGUARDANDO_MOTIVACAO':
        player_ref.update({'estado_criacao': 'AGUARDANDO_FALHA', 'ficha_em_criacao.motivacao': user_text})
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Interessante motivação\\. Mas até os maiores heróis têm uma fraqueza que os assombra, uma falha que molda o seu caráter\\. Qual é a sua\\?")
        
    elif estado_atual == 'AGUARDANDO_FALHA':
        player_ref.update({'ficha_em_criacao.falha': user_text})
        _finalizar_criacao(config, chat_id, player_ref)


def handle_creation_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    ficha_em_criacao = player_data.get('ficha_em_criacao', {})
    
    if callback_data.startswith('race_choice:'):
        raca_key = callback_data.split(':', 1)[1]
        raca_info = config.RACAS_DATA.get(raca_key, {})
        ficha_em_criacao['raca'] = raca_key
        if 'ajustes_atributo' in raca_info: ficha_em_criacao['ajustes_raciais'] = raca_info['ajustes_atributo']
        if 'pericias_fixas' in raca_info: ficha_em_criacao['pericias_proficientes'] = raca_info['pericias_fixas']
        
        player_ref.update({'ficha_em_criacao': ficha_em_criacao, 'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'})
        
        nome_raca_escapado = telegram_actions.escape_markdown_v2(raca_info.get('nome_exibido', ''))
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você escolheu ser um\\(a\\) *{nome_raca_escapado}*\\.")
        
        valores = utils.ARRAY_PADRAO_ATRIBUTOS
        valores_formatados = telegram_actions.escape_markdown_v2(f"({', '.join(map(str, valores))})")
        texto = f"Agora, defina seus Atributos Fundamentais usando os valores: *{valores_formatados}*\\.\n\nComeçando pelo valor mais alto, *{valores[0]}*\\. Onde você deseja aplicá-lo\\?"
        
        botoes = [[{'text': f'{utils.obter_nome_completo_atributo(attr_k)} ({attr_k})', 'callback_data': f'distribute_attr:{valores[0]}:{attr_k}'}] for attr_k in utils.ATRIBUTOS_LISTA]
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, {'inline_keyboard': [botoes[i:i + 2] for i in range(0, len(botoes), 2)]})

    elif callback_data.startswith('distribute_attr:'):
        _, v_str, attr_key_upper = callback_data.split(':', 2)
        v_int = int(v_str)
        atributos_base = ficha_em_criacao.get('atributos_base', {})
        valores_pendentes = ficha_em_criacao.get('valores_atributos_pendentes', list(utils.ARRAY_PADRAO_ATRIBUTOS))
        
        if attr_key_upper.lower() in atributos_base: return
        
        atributos_base[attr_key_upper.lower()] = v_int
        if v_int in valores_pendentes: valores_pendentes.remove(v_int)
        player_ref.update({'ficha_em_criacao.atributos_base': atributos_base, 'ficha_em_criacao.valores_atributos_pendentes': valores_pendentes})
        
        if not valores_pendentes:
            atributos_finais = dict(atributos_base)
            ajustes_raciais = ficha_em_criacao.get('ajustes_raciais', {})
            for attr, bonus in ajustes_raciais.items(): atributos_finais[attr] = atributos_finais.get(attr, 0) + bonus
            modificadores = {attr: utils.calcular_modificador(val) for attr, val in atributos_finais.items()}
            
            player_ref.update({'estado_criacao': 'AGUARDANDO_CLASSE', 'ficha_em_criacao.atributos': atributos_finais, 'ficha_em_criacao.modificadores': modificadores})
            
            nome_attr_escapado = telegram_actions.escape_markdown_v2(utils.obter_nome_completo_atributo(attr_key_upper))
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você atribuiu *{v_str}* para *{nome_attr_escapado}*\\.\n\n✅ Atributos definidos e bónus raciais aplicados\\!")
            
            texto_resumo = "Seus Atributos Finais são:\n"
            for attr, val in sorted(atributos_finais.items()):
                mod = modificadores.get(attr, 0)
                sinal = '+' if mod >= 0 else ''
                texto_resumo += f"*{telegram_actions.escape_markdown_v2(utils.obter_nome_completo_atributo(attr.upper()))}*: {val} `({sinal}{mod})`\n"
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_resumo)
            
            texto_classe = "\nAgora, escolha a sua vocação, o seu chamado para a aventura:"
            botoes_classes = [[{'text': c_data['nome_exibido'], 'callback_data': f'class_choice:{c_key}'}] for c_key, c_data in sorted(config.CLASSES_DATA.items())]
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto_classe, {'inline_keyboard': botoes_classes})
        else:
            prox_valor = valores_pendentes[0]
            attrs_disponiveis = [key for key in utils.ATRIBUTOS_LISTA if key.lower() not in atributos_base]
            nome_attr_escapado = telegram_actions.escape_markdown_v2(utils.obter_nome_completo_atributo(attr_key_upper))
            texto_proximo = f"Você atribuiu *{v_str}* para *{nome_attr_escapado}*\\.\n\nPróximo valor a distribuir: *{prox_valor}*\\. Onde o aplicará\\?"
            botoes_prox = [[{'text': f'{utils.obter_nome_completo_atributo(attr_k)} ({attr_k})', 'callback_data': f'distribute_attr:{prox_valor}:{attr_k}'}] for attr_k in attrs_disponiveis]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto_proximo, {'inline_keyboard': [botoes_prox[i:i + 2] for i in range(0, len(botoes_prox), 2)]})
            
    elif callback_data.startswith('class_choice:'):
        classe_key = callback_data.split(':', 1)[1]
        player_ref.update({'estado_criacao': 'AGUARDANDO_HABILIDADE', 'ficha_em_criacao.classe': classe_key})
        _apresentar_escolhas_iniciais_classe(config, chat_id, message_id, classe_key, player_ref, ficha_em_criacao)
    
    elif callback_data.startswith('ability_choice:'):
        habilidade_escolhida = callback_data.split(':', 1)[1]
        habs_atuais = ficha_em_criacao.get('habilidades_aprendidas', [])
        if habilidade_escolhida not in habs_atuais:
            habs_atuais.append(habilidade_escolhida)
        
        player_ref.update({
            'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS',
            'ficha_em_criacao.habilidades_aprendidas': habs_atuais
        })
        
        classe_key = ficha_em_criacao.get('classe')
        hab_escapada = telegram_actions.escape_markdown_v2(habilidade_escolhida)
        texto_confirmacao = f"✨ Habilidade *{hab_escapada}* selecionada\\!"
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
        
        pericia_escapada = telegram_actions.escape_markdown_v2(pericia_escolhida)
        if escolhas_restantes <= 0:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Perícia *{pericia_escapada}* adicionada\\. Todas as perícias de classe foram escolhidas\\.")
            player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
            telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "📜 Agora, vamos à sua história\\. O que você fazia antes de se tornar um aventureiro\\?")
        else:
            texto = f"Perícia *{pericia_escapada}* adicionada\\.\nEscolha mais *{escolhas_restantes}* perícia\\(s\\):"
            botoes_pericias = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in opcoes_atuais]
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, {'inline_keyboard': botoes_pericias})