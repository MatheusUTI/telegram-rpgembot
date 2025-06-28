# modules/game_logic/socketing_handler.py
# Módulo completo para gerir a mecânica de engaste de gemas.

import copy
from firebase_admin import firestore
from modules import telegram_actions

def handle_engastar_command(config, user_id, chat_id, player_ref, player_data):
    """
    Inicia o fluxo de engaste de gemas.
    """
    inventario = player_data.get('ficha', {}).get('inventario', [])
    
    # Filtra os itens que podem receber gemas (têm engastes vazios)
    itens_com_engaste_vazio = [
        item for item in inventario 
        if isinstance(item, dict) and 'engastes' in item and any(engaste.get('gema') is None for engaste in item['engastes'])
    ]

    if not itens_com_engaste_vazio:
        telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, "Você não possui itens com engastes vazios para aprimorar.")
        return

    # Define o estado inicial do processo de engaste no Firestore
    player_ref.update({'estado_engaste': {'passo': 'AGUARDANDO_ESCOLHA_ITEM'}})

    botoes = []
    for item in itens_com_engaste_vazio:
        botoes.append([{'text': item['nome_exibido'], 'callback_data': f"socket_item:{item['uuid']}"}])
    
    texto = "Selecione o item que você deseja aprimorar:"
    teclado = {'inline_keyboard': botoes}
    telegram_actions.send_telegram_message(config.TELEGRAM_TOKEN, chat_id, texto, teclado)


def handle_socketing_callback(config, user_id, chat_id, message_id, callback_data, player_ref, player_data):
    """
    Gerencia os callbacks do fluxo de engaste.
    """
    estado_engaste = player_data.get('estado_engaste', {})
    passo_atual = estado_engaste.get('passo')
    inventario = player_data.get('ficha', {}).get('inventario', [])

    # Passo 1: Jogador escolheu o item
    if passo_atual == 'AGUARDANDO_ESCOLHA_ITEM' and callback_data.startswith('socket_item:'):
        item_uuid = callback_data.split(':', 1)[1]
        
        item_selecionado = next((item for item in inventario if item.get('uuid') == item_uuid), None)
        if not item_selecionado:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Erro: Item não encontrado no seu inventário.")
            player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
            return
            
        gemas_disponiveis = [item for item in inventario if isinstance(item, dict) and item.get('tipo_item') == 'gema']

        if not gemas_disponiveis:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, f"Você selecionou: {item_selecionado['nome_exibido']}.\n\nNo entanto, você não possui nenhuma gema para engastar.")
            player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
            return
        
        player_ref.update({
            'estado_engaste.passo': 'AGUARDANDO_ESCOLHA_GEMA',
            'estado_engaste.item_uuid': item_uuid
        })

        botoes_gemas = [[{'text': gema['nome_exibido'], 'callback_data': f"socket_gem:{gema['uuid']}"}] for gema in gemas_disponiveis]
        
        texto = f"Item selecionado: <b>{item_selecionado['nome_exibido']}</b>.\n\nAgora, escolha a Essência que deseja infundir neste item:"
        teclado = {'inline_keyboard': botoes_gemas}
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, teclado)

    # Passo 2: Jogador escolheu a gema, agora pedimos confirmação
    elif passo_atual == 'AGUARDANDO_ESCOLHA_GEMA' and callback_data.startswith('socket_gem:'):
        gema_uuid = callback_data.split(':', 1)[1]
        item_uuid = estado_engaste.get('item_uuid')

        item_obj = next((item for item in inventario if item.get('uuid') == item_uuid), None)
        gema_obj = next((item for item in inventario if item.get('uuid') == gema_uuid), None)

        if not item_obj or not gema_obj:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Erro: Item ou gema não encontrado.")
            player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
            return

        player_ref.update({'estado_engaste.passo': 'AGUARDANDO_CONFIRMACAO'})

        texto = f"Você deseja engastar <b>{gema_obj['nome_exibido']}</b> em <b>{item_obj['nome_exibido']}</b>?\n\n<i>Esta ação é permanente e consumirá a gema.</i>"
        botoes = [
            [{'text': "✅ Sim, engastar", 'callback_data': f"socket_confirm:{item_uuid}:{gema_uuid}"}],
            [{'text': "❌ Não, cancelar", 'callback_data': "socket_cancel"}]
        ]
        teclado = {'inline_keyboard': botoes}
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto, teclado)

    # Passo 3: Confirmação final e execução
    elif passo_atual == 'AGUARDANDO_CONFIRMACAO' and callback_data.startswith('socket_confirm:'):
        _, item_uuid, gema_uuid = callback_data.split(':')
        
        novo_inventario = []
        item_atualizado = None
        gema_consumida = None

        for item in inventario:
            if item.get('uuid') == item_uuid:
                item_atualizado = copy.deepcopy(item) # Trabalha com uma cópia para evitar mutações
            elif item.get('uuid') == gema_uuid:
                gema_consumida = item
            else:
                novo_inventario.append(item)
        
        if not item_atualizado or not gema_consumida:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Erro na transação. Tente novamente.")
            player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
            return
            
        # Encontra o primeiro engaste vazio e coloca a gema
        engaste_preenchido = False
        for engaste in item_atualizado.get('engastes', []):
            if engaste.get('gema') is None:
                engaste['gema'] = gema_consumida
                engaste_preenchido = True
                break
        
        if not engaste_preenchido:
            telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Erro: O item selecionado não parece ter mais engastes vazios.")
            player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
            return

        # Adiciona o item modificado de volta ao inventário
        novo_inventario.append(item_atualizado)

        # Atualiza o inventário e limpa o estado de engaste
        player_ref.update({
            'ficha.inventario': novo_inventario,
            'estado_engaste': firestore.DELETE_FIELD
        })

        texto_final = f"Com um brilho súbito, a <b>{gema_consumida['nome_exibido']}</b> se fixa no seu <b>{item_atualizado['nome_exibido']}</b>, que agora pulsa com um novo poder."
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, texto_final)

    # Jogador cancelou a operação
    elif callback_data == "socket_cancel":
        player_ref.update({'estado_engaste': firestore.DELETE_FIELD})
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Ação cancelada. A gema e o item retornam à sua mochila.")

    else:
        # Limpa um estado inválido ou expirado
        telegram_actions.edit_telegram_message(config.TELEGRAM_TOKEN, chat_id, message_id, "Esta ação de engaste parece ter expirado. Use /engastar para começar de novo.")
        player_ref.update({'estado_engaste': firestore.DELETE_FIELD})