import os
import json
import traceback
import random
import hmac
import hashlib
import urllib.parse
import google.generativeai as genai
import firebase_admin
from firebase_admin import firestore
import functions_framework
import requests

# --- INICIALIZAÇÃO E CARREGAMENTO DOS DADOS DO JOGO ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

CLASSES_DATA = {}
RACAS_DATA = {}

try:
    print("Tentando carregar game_data/classes.json...")
    with open('game_data/classes.json', 'r', encoding='utf-8') as f:
        CLASSES_DATA = json.load(f)
    print("game_data/classes.json carregado com sucesso.")
    if not isinstance(CLASSES_DATA, dict) or not CLASSES_DATA:
        print("ERRO CRÍTICO: classes.json não é um dicionário válido ou está vazio.")
        raise ValueError("classes.json inválido")
except FileNotFoundError:
    print("ERRO CRÍTICO: O ficheiro 'game_data/classes.json' não foi encontrado.")
    raise
except json.JSONDecodeError as e:
    print(f"ERRO CRÍTICO: Falha ao decodificar 'game_data/classes.json'. Erro: {e}")
    raise
except Exception as e:
    print(f"ERRO CRÍTICO INESPERADO ao carregar 'game_data/classes.json': {e}")
    raise

try:
    print("Tentando carregar game_data/racas.json...")
    with open('game_data/racas.json', 'r', encoding='utf-8') as f:
        RACAS_DATA = json.load(f)
    print("game_data/racas.json carregado com sucesso.")
    if not isinstance(RACAS_DATA, dict):
        print("AVISO: racas.json não é um dicionário válido ou está vazio após o carregamento, será tratado como {}")
        RACAS_DATA = {}
except FileNotFoundError:
    print("AVISO: O ficheiro 'game_data/racas.json' não foi encontrado. A escolha de raça pode não estar completa.")
    RACAS_DATA = {}
except json.JSONDecodeError as e:
    print(f"AVISO: Falha ao decodificar 'game_data/racas.json'. Erro: {e}")
    RACAS_DATA = {}
except Exception as e:
    print(f"AVISO INESPERADO ao carregar 'game_data/racas.json': {e}")
    RACAS_DATA = {}

# --- CONFIGURAÇÃO DAS CHAVES (COMO VOCÊ PEDIU PARA MANTER) ---
TELEGRAM_TOKEN = "8185946655:AAGfyNTARWgaRU5ddoFG9hHR-7kPqMCjzo0"
GEMINI_API_KEY = "AIzaSyDIzFVMGmNp7yg8ovN8o0KHML5DT86b7ho"

# --- CONFIGURAÇÃO DO MODELO GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- CONSTANTES DE JOGO ---
ATRIBUTOS_LISTA = ["FOR", "DES", "CON", "INT", "SAB", "CAR"]
ARRAY_PADRAO_ATRIBUTOS = sorted([15, 14, 13, 12, 10, 8], reverse=True)

# --- FUNÇÕES AUXILIARES ---
def calcular_modificador(valor_atributo):
    return (valor_atributo - 10) // 2

def obter_nome_completo_atributo(attr_key_upper):
    nomes_atributos = {
        "FOR": "Força", "DES": "Destreza", "CON": "Constituição",
        "INT": "Inteligência", "SAB": "Sabedoria", "CAR": "Carisma"
    }
    return nomes_atributos.get(attr_key_upper, attr_key_upper)

def parse_dado_str(dado_str):
    if not isinstance(dado_str, str) or 'd' not in dado_str: return 0, 0
    parts = dado_str.lower().split('d')
    try:
        num_dados = int(parts[0]) if parts[0] else 1
        tipo_dado = int(parts[1])
        return num_dados, tipo_dado
    except (ValueError, IndexError): return 0, 0

def rolar_dados_dano(dado_str, modificador_dano):
    num_dados, tipo_dado = parse_dado_str(dado_str)
    if num_dados == 0: return 0, "Erro na formatação do dado"
    rolagens, soma_rolagens = [], 0
    for _ in range(num_dados):
        roll = random.randint(1, tipo_dado)
        rolagens.append(roll)
        soma_rolagens += roll
    total_dano = soma_rolagens + modificador_dano
    rolagem_str_fmt = f"{soma_rolagens} ({'+'.join(map(str, rolagens))})"
    if modificador_dano != 0:
        rolagem_str_fmt += f" {'+' if modificador_dano >=0 else ''}{modificador_dano} [Mod]"
    return total_dano, rolagem_str_fmt

# --- PROMPTS DE SISTEMA ---
PROMPT_ARBITRO = """Analise a seguinte ação de um jogador em um RPG: "{}". A ação pode ser resolvida com uma simples narração (como olhar ao redor, falar, ou andar) ou ela possui um risco inerente de falha que exige um teste de perícia/sorte/força (como atacar, escalar, persuadir, se esconder)? Responda APENAS com a palavra `SIM` se um teste for necessário, ou `NÃO` se não for."""
PROMPT_MESTRE_NARRADOR = """Você é o Mestre de Jogo para um RPG de fantasia chamado 'As Terras de Aethel', um mundo onde a magia está desaparecendo e a tecnologia a vapor está surgindo. Use um tom levemente sombrio e misterioso. REGRAS DO SISTEMA 'LÓGICA & SORTE': 1. O sistema usa um dado de 20 lados (d20). O resultado bruto do dado rolado pelo jogador será informado a você. 2. Sua principal tarefa é ser o juiz lógico. Analise a Ficha do Personagem e a situação para aplicar modificadores lógicos (vantagens ou desvantagens) à rolagem. Você não precisa mostrar cálculos, apenas narre o resultado final de forma imersiva. 3. VANTAGEM LÓGICA: Se um personagem está bem preparado para uma ação (ex: um Ladino furtivo tentando se esconder nas sombras), o resultado do dado é efetivamente melhor. Um resultado baixo pode se tornar um sucesso simples. 4. DESVANTAGEM LÓGICA: Se um personagem está mal preparado (ex: um Guerreiro de armadura de metal tentando ser furtivo), o resultado do dado é efetivamente pior. Um resultado médio pode se tornar uma falha. 5. GRAUS DE SUCESSO: Use o resultado final (dado + modificadores) para determinar o grau de sucesso: Falha Crítica, Falha Simples, Sucesso com Custo, Sucesso Simples, ou Sucesso Excepcional. INFORMAÇÕES PARA A NARRAÇÃO: - Ficha do Personagem: {} - Histórico da Conversa: {} - Ação Tentada: "{}" - Resultado do Dado (d20): {} Sua tarefa é retornar APENAS a narração do que acontece a seguir, de forma criativa e imersiva."""
PROMPT_NARRADOR_SIMPLES = """Você é o Mestre de Jogo para um RPG de fantasia chamado 'As Terras de Aethel'. A seguinte ação do jogador não requer um teste de dados. Apenas narre o resultado da ação de forma simples e direta, preparando para a próxima ação. Ação do Jogador: "{}". Ficha do Personagem: {}."""

# --- FUNÇÕES AUXILIARES DO TELEGRAM ---
def send_telegram_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard: payload['reply_markup'] = json.dumps(keyboard)
    response = requests.post(url, json=payload)
    if not response.ok: print(f"Erro ao enviar msg: {response.status_code} - {response.text}")
    return response.json()

def edit_telegram_message(chat_id, message_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if keyboard: payload['reply_markup'] = json.dumps(keyboard)
    response = requests.post(url, json=payload)
    if not response.ok: print(f"Erro ao editar msg: {response.status_code} - {response.text}")
    return response.json()

def answer_callback_query(callback_query_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    requests.post(url, json=payload)

# --- FUNÇÃO AUXILIAR PARA CALCULAR CA COM EQUIPAMENTO (SIMPLIFICADO) ---
def calcular_ca_final_com_equipamento(ca_base_personagem, inventario, modificadores):
    ca_final = ca_base_personagem
    tem_escudo = False
    armadura_principal_ca_valor = 0
    if not isinstance(modificadores, dict): modificadores = {}
    if not isinstance(inventario, list): inventario = []

    for item in inventario:
        if isinstance(item, dict):
            nome_item_lower = item.get('nome', '').lower()
            tipo_item = item.get('tipo', '')
            item_ca_base = item.get('ca_base', 0)

            if tipo_item == "armadura_pesada_ref" and item_ca_base > 0:
                armadura_principal_ca_valor = max(armadura_principal_ca_valor, item_ca_base)
                ca_final = armadura_principal_ca_valor
            elif tipo_item == "armadura_media_ref" and item_ca_base > 0:
                bonus_des = min(modificadores.get('des', 0), 2)
                armadura_principal_ca_valor = max(armadura_principal_ca_valor, item_ca_base + bonus_des)
                ca_final = armadura_principal_ca_valor
            elif tipo_item == "armadura_leve_ref" and item_ca_base > 0:
                bonus_des = modificadores.get('des', 0)
                armadura_principal_ca_valor = max(armadura_principal_ca_valor, item_ca_base + bonus_des)
                ca_final = armadura_principal_ca_valor
            if "escudo" in nome_item_lower or (item.get('ca_bonus', 0) > 0 and tipo_item == "armadura_aux"):
                tem_escudo = True
        elif isinstance(item, str) and "escudo" in item.lower(): tem_escudo = True
            
    if armadura_principal_ca_valor == 0: ca_final = ca_base_personagem
    if tem_escudo: ca_final += 2
    return ca_final

# --- FUNÇÃO AUXILIAR PARA APRESENTAR ESCOLHAS DE PERÍCIAS ---
def apresentar_escolha_pericias(chat_id, message_id_para_editar_anterior, classe_key, player_ref, ficha_em_criacao): # Renomeado para clareza
    classe_info = CLASSES_DATA.get(classe_key, {})
    nome_classe_exibido = classe_info.get('nome_exibido', 'Sua classe')
    num_escolhas_total = classe_info.get('pericias_escolha_num', 0)
    opcoes_pericias_classe = classe_info.get('pericias_opcoes', [])
    pericias_ja_proficientes = ficha_em_criacao.get('pericias_proficientes', [])
    opcoes_reais_para_escolha = [p for p in opcoes_pericias_classe if p not in pericias_ja_proficientes]

    if num_escolhas_total == 0 or not opcoes_reais_para_escolha:
        player_ref.update({'estado_criacao': 'AGUARDANDO_BACKGROUND'})
        equipamento = classe_info.get('equipamento_inicial', [])
        inventario_com_equip = ficha_em_criacao.get('inventario', [])
        for eq_item in equipamento:
            nome_item_novo = eq_item.get("nome") if isinstance(eq_item, dict) else eq_item
            if not any((item_inv.get("nome") if isinstance(item_inv, dict) else item_inv) == nome_item_novo for item_inv in inventario_com_equip):
                inventario_com_equip.append(eq_item)
        ca_final = calcular_ca_final_com_equipamento(
            ficha_em_criacao.get('ca_base', 10), inventario_com_equip, ficha_em_criacao.get('modificadores', {}))
        player_ref.update({
            'ficha_em_criacao.inventario': inventario_com_equip,
            'ficha_em_criacao.ca_final': ca_final,
            'ficha_em_criacao.pericias_escolhas_restantes': firestore.DELETE_FIELD, # Limpa campos temporários
            'ficha_em_criacao.pericias_opcoes_atuais': firestore.DELETE_FIELD
        })
        msg_final_pericias = f"Todas as perícias de *{nome_classe_exibido}* foram definidas.\nEquipamento inicial adicionado. Sua Classe de Armadura (CA) final é *{ca_final}*."
        if message_id_para_editar_anterior: # Edita a mensagem da escolha de habilidade/classe
            edit_telegram_message(chat_id, message_id_para_editar_anterior, msg_final_pericias)
        else: # Envia nova se não havia uma para editar (ex: fluxo direto para perícias)
            send_telegram_message(chat_id, msg_final_pericias)
        send_telegram_message(chat_id, "Interessante... Agora, vamos à sua história. O que você fazia antes de se tornar um aventureiro?")
        return

    player_ref.update({
        'ficha_em_criacao.pericias_escolhas_restantes': num_escolhas_total,
        'ficha_em_criacao.pericias_opcoes_atuais': opcoes_reais_para_escolha
    })
    texto = f"Como *{nome_classe_exibido}*, você tem aptidão em diversas áreas. Escolha *{num_escolhas_total}* perícia(s) da lista abaixo para se especializar.\n\nEscolha sua primeira perícia:"
    botoes = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in opcoes_reais_para_escolha]
    reply_markup = {'inline_keyboard': [botoes[i:i + 3] for i in range(0, len(botoes), 3)] if len(botoes) > 3 else botoes}
    
    # A mensagem anterior (escolha de classe/habilidade) já foi editada. Enviamos uma nova para perícias.
    send_telegram_message(chat_id, texto, reply_markup)


# --- FUNÇÃO AUXILIAR PARA APRESENTAR HABILIDADES/SUB-ESCOLHAS INICIAIS ---
def apresentar_escolhas_iniciais_classe(chat_id, message_id_para_editar, classe_escolhida, player_ref, ficha_em_criacao):
    if not CLASSES_DATA.get(classe_escolhida):
        send_telegram_message(chat_id, "Erro: Classe não encontrada.")
        player_ref.update({'estado_criacao': 'AGUARDANDO_CLASSE'})
        return

    habilidades_nivel_1 = [h for h in CLASSES_DATA[classe_escolhida].get('habilidades', []) if h['nivel'] == 1]
    nome_classe_exibido = CLASSES_DATA[classe_escolhida].get('nome_exibido', classe_escolhida)
    texto_base_escolha = f"Como um(a) *{nome_classe_exibido}*,"

    if classe_escolhida == 'clerigo':
        dominios = [h for h in habilidades_nivel_1 if "Domínio Divino:" in h['nome']]
        if dominios:
            texto = f"{texto_base_escolha} sua fé se manifesta através de um Domínio Divino específico, que molda seus poderes e propósito.\n\nQual Domínio você devotará?"
            botoes = [[{'text': f"Domínio: {d['nome'].split(': ')[-1].replace(' (Exemplo)','')}", 'callback_data': f"subchoice:dominio:{d['nome']}"}] for d in dominios]
            edit_telegram_message(chat_id, message_id_para_editar, texto, {'inline_keyboard': botoes})
            return
    elif classe_escolhida == 'guerreiro':
        estilos = [h for h in habilidades_nivel_1 if "Estilo de Luta" in h['nome']]
        if estilos:
            texto = f"{texto_base_escolha} seu treinamento árduo lhe concedeu maestria em um Estilo de Luta particular.\n\nQual técnica você aprimorou?"
            botoes = [[{'text': f"Estilo: {s['nome'].split(': ')[-1]}", 'callback_data': f"subchoice:estilo_luta:{s['nome']}"}] for s in estilos]
            edit_telegram_message(chat_id, message_id_para_editar, texto, {'inline_keyboard': botoes})
            return

    habilidades_gerais_nv1_para_escolha = [h for h in habilidades_nivel_1 if "Domínio Divino:" not in h['nome'] and ("Estilo de Luta" not in h['nome'] or classe_escolhida != 'guerreiro')]
    if habilidades_gerais_nv1_para_escolha and len(habilidades_gerais_nv1_para_escolha) > 1 and classe_escolhida not in ['barbaro', 'bardo', 'mago', 'clerigo', 'guerreiro']:
        texto = f"{texto_base_escolha} você possui talentos únicos. Escolha UMA habilidade inicial para focar:"
        botoes = [[{'text': hab['nome'], 'callback_data': f"ability_choice:{hab['nome']}"}] for hab in habilidades_gerais_nv1_para_escolha[:4]]
        edit_telegram_message(chat_id, message_id_para_editar, texto, {'inline_keyboard': botoes})
        return

    habilidades_finais_nv1 = ficha_em_criacao.get('habilidades_aprendidas', [])
    for hab in habilidades_gerais_nv1_para_escolha:
        if hab['nome'] not in habilidades_finais_nv1: habilidades_finais_nv1.append(hab['nome'])
    
    oficio = CLASSES_DATA.get(classe_escolhida, {}).get('oficio', 'Nenhum')
    modificadores = ficha_em_criacao.get('modificadores', {})
    classe_info = CLASSES_DATA.get(classe_escolhida, {})
    pv_max = ficha_em_criacao.get('pv_maximos', 0)
    ca_base = ficha_em_criacao.get('ca_base', 10 + modificadores.get('des',0))
    if pv_max == 0:
        if 'dado_vida' in classe_info and 'con' in modificadores:
            try: valor_dado_vida = int(classe_info['dado_vida'].replace('d','')); pv_max = valor_dado_vida + modificadores['con']
            except ValueError: pv_max = 8 + modificadores.get('con', 0)
        else: pv_max = 8 + modificadores.get('con', 0)

    player_ref.update({
        'ficha_em_criacao.habilidades_aprendidas': list(set(habilidades_finais_nv1)),
        'ficha_em_criacao.oficio': oficio,
        'ficha_em_criacao.pv_maximos': pv_max,
        'ficha_em_criacao.pv_atuais': pv_max,
        'ficha_em_criacao.ca_base': ca_base,
        'ficha_em_criacao.bonus_proficiencia': 2,
        'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'
    })
    ficha_em_criacao_atualizada_doc = player_ref.get()
    ficha_em_criacao_para_pericias = ficha_em_criacao_atualizada_doc.to_dict().get('ficha_em_criacao',{})
    
    edit_telegram_message(chat_id, message_id_para_editar, f"Talentos de *{nome_classe_exibido}* definidos!\nPV: {pv_max}, CA Base (sem armadura): {ca_base}.")
    apresentar_escolha_pericias(chat_id, message_id_para_editar, classe_escolhida, player_ref, ficha_em_criacao_para_pericias) # Passa message_id para editar se for o caso


# ==============================================================================
# === CLOUD FUNCTION 1: O WEBHOOK DO BOT DO TELEGRAM                          ===
# ==============================================================================
@functions_framework.http
def rpg_bot_webhook(request):
    update = request.get_json(silent=True)
    if not update: return "OK", 200
    chat_id_para_erro = None
    try:
        if 'callback_query' in update:
            data = update['callback_query']
            user_id, chat_id, message_id, callback_data = str(data['from']['id']), data['message']['chat']['id'], data['message']['message_id'], data['data']
            player_ref = db.collection('jogadores').document(user_id)
            player_doc = player_ref.get()
            player_data = player_doc.to_dict() if player_doc.exists else {}
            ficha_em_criacao = player_data.get('ficha_em_criacao', {})
            answer_callback_query(data['id'])
            chat_id_para_erro = chat_id

            # --- CALLBACKS DE CRIAÇÃO DE PERSONAGEM ---
            if callback_data.startswith('race_choice:'):
                raca_escolhida_key = callback_data.split(':', 1)[1]
                if raca_escolhida_key not in RACAS_DATA:
                    send_telegram_message(chat_id, "Raça inválida. Tente novamente.")
                    return "OK", 200
                raca_info = RACAS_DATA[raca_escolhida_key]
                ficha_em_criacao['raca'] = raca_escolhida_key
                ficha_em_criacao['nome_raca_exibido'] = raca_info['nome_exibido']
                ficha_em_criacao['tracos_raciais'] = raca_info.get('tracos_raciais', [])
                ficha_em_criacao['deslocamento'] = raca_info.get('deslocamento', 9)
                pericias_prof_atuais = ficha_em_criacao.get('pericias_proficientes', [])
                if "Proficiência (Percepção)" in raca_info.get('tracos_raciais', []):
                    pericias_prof_atuais.append("Percepção")
                ficha_em_criacao['pericias_proficientes'] = list(set(pericias_prof_atuais))
                player_ref.update({
                    'ficha_em_criacao': ficha_em_criacao,
                    'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'
                })
                edit_telegram_message(chat_id, message_id, f"Você escolheu ser um(a) *{raca_info['nome_exibido']}*.")
                primeiro_valor = ARRAY_PADRAO_ATRIBUTOS[0]
                texto_dist = f"Excelente escolha! Ser um(a) *{raca_info['nome_exibido']}* lhe confere certas aptidões.\n\n"
                texto_dist += "Agora, defina seus Atributos Fundamentais usando os valores: 15, 14, 13, 12, 10, 8.\n"
                texto_dist += f"Começando pelo valor mais alto, *{primeiro_valor}*. Em qual atributo você deseja aplicá-lo?"
                botoes_dist = []
                for attr_key_upper in ATRIBUTOS_LISTA:
                    botoes_dist.append({'text': f'{obter_nome_completo_atributo(attr_key_upper)} ({attr_key_upper})', 'callback_data': f'distribute_attr:{primeiro_valor}:{attr_key_upper}'})
                reply_markup_dist = {'inline_keyboard': [botoes_dist[i:i + 2] for i in range(0, len(botoes_dist), 2)]}
                send_telegram_message(chat_id, texto_dist, reply_markup_dist)

            elif callback_data.startswith('distribute_attr:'):
                _, valor_str, atributo_escolhido_key = callback_data.split(':', 2)
                valor_int = int(valor_str)
                atributos_base = ficha_em_criacao.get('atributos_base', {})
                valores_pendentes = ficha_em_criacao.get('valores_atributos_pendentes', list(ARRAY_PADRAO_ATRIBUTOS))
                if atributo_escolhido_key.lower() in atributos_base:
                    send_telegram_message(chat_id, f"Atributo {obter_nome_completo_atributo(atributo_escolhido_key.upper())} já definido.")
                    return "OK", 200
                if valor_int not in valores_pendentes:
                    send_telegram_message(chat_id, f"Valor {valor_int} não disponível.")
                    return "OK", 200
                atributos_base[atributo_escolhido_key.lower()] = valor_int
                valores_pendentes.remove(valor_int)
                player_ref.update({
                    'ficha_em_criacao.atributos_base': atributos_base,
                    'ficha_em_criacao.valores_atributos_pendentes': valores_pendentes
                })
                if not valores_pendentes:
                    atributos_finais = dict(atributos_base)
                    raca_key = ficha_em_criacao.get('raca')
                    if raca_key and raca_key in RACAS_DATA:
                        ajustes = RACAS_DATA[raca_key].get('ajustes_atributo', {})
                        for attr_k, bonus in ajustes.items():
                            atributos_finais[attr_k] = atributos_finais.get(attr_k, 0) + bonus
                    modificadores = {attr: calcular_modificador(val) for attr, val in atributos_finais.items()}
                    player_ref.update({
                        'estado_criacao': 'AGUARDANDO_CLASSE',
                        'ficha_em_criacao.atributos': atributos_finais,
                        'ficha_em_criacao.modificadores': modificadores,
                    })
                    edit_telegram_message(chat_id, message_id, f"Você atribuiu {valor_int} para {obter_nome_completo_atributo(atributo_escolhido_key.upper())}.\nAtributos base definidos. Bônus raciais aplicados!")
                    texto_atributos_finais = "Perfeito! Seus Atributos Finais são:\n"
                    for attr_k_lower, attr_v in atributos_finais.items():
                        mod = modificadores.get(attr_k_lower,0)
                        texto_atributos_finais += f"*{obter_nome_completo_atributo(attr_k_lower.upper())} ({attr_k_lower.upper()})*: {attr_v} (Mod: {'+' if mod >=0 else ''}{mod})\n"
                    texto_atributos_finais += "\nAgora, escolha sua vocação, seu chamado para a aventura:"
                    botoes_classes = [[{'text': c_data['nome_exibido'], 'callback_data': f'class_choice:{c_key}'}] for c_key, c_data in CLASSES_DATA.items()]
                    botoes_classes.sort(key=lambda r: r[0]['text'])
                    send_telegram_message(chat_id, texto_atributos_finais, {'inline_keyboard': botoes_classes})
                else:
                    prox_valor = valores_pendentes[0]
                    attrs_disp_keys = [attr_key for attr_key in ATRIBUTOS_LISTA if attr_key.lower() not in atributos_base]
                    texto_novo = f"Você atribuiu {valor_int} para {obter_nome_completo_atributo(atributo_escolhido_key.upper())}.\n\n"
                    texto_novo += f"Próximo valor a distribuir: *{prox_valor}*. Em qual atributo restante você o aplicará?"
                    botoes_prox = []
                    for attr_disp_upper_key in attrs_disp_keys:
                        botoes_prox.append({'text': f'{obter_nome_completo_atributo(attr_disp_upper_key)} ({attr_disp_upper_key})', 
                                           'callback_data': f'distribute_attr:{prox_valor}:{attr_disp_upper_key}'})
                    reply_markup_prox = {'inline_keyboard': [botoes_prox[i:i + 2] for i in range(0, len(botoes_prox), 2)]}
                    edit_telegram_message(chat_id, message_id, texto_novo, reply_markup_prox)
            
            elif callback_data.startswith('class_choice:'):
                classe_escolhida_key = callback_data.split(':', 1)[1]
                classe_info = CLASSES_DATA.get(classe_escolhida_key, {})
                pericias_fixas = classe_info.get('pericias_fixas', [])
                pericias_atuais = ficha_em_criacao.get('pericias_proficientes', [])
                for p_fixa in pericias_fixas:
                    if p_fixa not in pericias_atuais: pericias_atuais.append(p_fixa)
                player_ref.update({
                    'estado_criacao': 'AGUARDANDO_HABILIDADE_INICIAL',
                    'ficha_em_criacao.classe': classe_escolhida_key,
                    'ficha_em_criacao.pericias_proficientes': list(set(pericias_atuais))
                })
                ficha_atualizada_doc = player_ref.get()
                ficha_para_habilidades = ficha_atualizada_doc.to_dict().get('ficha_em_criacao', {})
                apresentar_escolhas_iniciais_classe(chat_id, message_id, classe_escolhida_key, player_ref, ficha_para_habilidades)

            elif callback_data.startswith('subchoice:') or callback_data.startswith('ability_choice:'):
                parts = callback_data.split(':', 2)
                tipo_escolha_cb = parts[0]
                sub_tipo_ou_nome_habilidade = parts[1]
                habilidade_escolhida_final = parts[2] if tipo_escolha_cb == 'subchoice' else sub_tipo_ou_nome_habilidade
                classe_personagem_atual = ficha_em_criacao.get('classe')

                if not classe_personagem_atual:
                    send_telegram_message(chat_id, "Erro: Classe não definida. Reinicie.")
                    return "OK", 200

                habilidades_aprendidas_atuais = ficha_em_criacao.get('habilidades_aprendidas', [])
                if habilidade_escolhida_final not in habilidades_aprendidas_atuais:
                     habilidades_aprendidas_atuais.append(habilidade_escolhida_final)
                
                habilidades_nivel_1_classe = [h for h in CLASSES_DATA.get(classe_personagem_atual, {}).get('habilidades', []) if h['nivel'] == 1]
                for hab_passiva in habilidades_nivel_1_classe:
                    is_subchoice_type = "Domínio Divino:" in hab_passiva['nome'] or "Estilo de Luta" in hab_passiva['nome']
                    if hab_passiva['nome'] != habilidade_escolhida_final and not is_subchoice_type and hab_passiva['nome'] not in habilidades_aprendidas_atuais:
                        habilidades_aprendidas_atuais.append(hab_passiva['nome'])
                
                oficio_final = CLASSES_DATA.get(classe_personagem_atual, {}).get('oficio', 'Nenhum')
                modificadores_finais = ficha_em_criacao.get('modificadores', {})
                info_classe_final = CLASSES_DATA.get(classe_personagem_atual, {})
                pv_max_final = ficha_em_criacao.get('pv_maximos',0) 
                ca_base_final = ficha_em_criacao.get('ca_base', 10 + modificadores_finais.get('des',0))
                if pv_max_final == 0 :
                    if 'dado_vida' in info_classe_final and 'con' in modificadores_finais:
                        try: dv = int(info_classe_final['dado_vida'].replace('d','')); pv_max_final = dv + modificadores_finais['con']
                        except ValueError: pv_max_final = 8 + modificadores_finais.get('con', 0)
                    else: pv_max_final = 8 + modificadores_finais.get('con', 0)
                
                player_ref.update({
                    'ficha_em_criacao.habilidades_aprendidas': list(set(habilidades_aprendidas_atuais)),
                    'ficha_em_criacao.oficio': oficio_final,
                    'ficha_em_criacao.pv_maximos': pv_max_final,
                    'ficha_em_criacao.pv_atuais': pv_max_final,
                    'ficha_em_criacao.ca_base': ca_base_final,
                    'ficha_em_criacao.bonus_proficiencia': 2,
                    'estado_criacao': 'AGUARDANDO_ESCOLHA_PERICIAS'
                })
                
                ficha_em_criacao_para_pericias_doc = player_ref.get()
                ficha_em_criacao_para_pericias = ficha_em_criacao_para_pericias_doc.to_dict().get('ficha_em_criacao',{})
                
                nome_amigavel = habilidade_escolhida_final.split(': ')[-1].replace(" (Exemplo)","").replace(" (Patrulheiro)","")
                texto_confirmacao_habilidade = f"Habilidade *{nome_amigavel}* selecionada."
                if tipo_escolha_cb == 'subchoice':
                    texto_confirmacao_habilidade = f"{sub_tipo_ou_nome_habilidade.replace('_',' ').capitalize()} *{nome_amigavel}* selecionado(a)."
                
                edit_telegram_message(chat_id, message_id, f"{texto_confirmacao_habilidade}\nPV: {pv_max_final}, CA Base (sem armadura): {ca_base_final}.")
                apresentar_escolha_pericias(chat_id, message_id, classe_personagem_atual, player_ref, ficha_em_criacao_para_pericias) # Passa message_id

            elif callback_data.startswith('skill_choice:'):
                pericia_escolhida = callback_data.split(':',1)[1]
                pericias_prof = ficha_em_criacao.get('pericias_proficientes', [])
                pericias_escolhas_restantes = ficha_em_criacao.get('pericias_escolhas_restantes', 0)
                pericias_opcoes_atuais = ficha_em_criacao.get('pericias_opcoes_atuais', [])

                if pericia_escolhida in pericias_prof:
                    send_telegram_message(chat_id, "Já proficiente. Escolha outra.")
                    return "OK", 200
                if pericia_escolhida not in pericias_opcoes_atuais:
                    send_telegram_message(chat_id, "Opção inválida.")
                    return "OK", 200

                pericias_prof.append(pericia_escolhida)
                pericias_escolhas_restantes -= 1
                if pericia_escolhida in pericias_opcoes_atuais: pericias_opcoes_atuais.remove(pericia_escolhida)

                player_ref.update({
                    'ficha_em_criacao.pericias_proficientes': list(set(pericias_prof)),
                    'ficha_em_criacao.pericias_escolhas_restantes': pericias_escolhas_restantes,
                    'ficha_em_criacao.pericias_opcoes_atuais': pericias_opcoes_atuais
                })

                if pericias_escolhas_restantes <= 0 or not pericias_opcoes_atuais:
                    classe_key_final = ficha_em_criacao.get('classe')
                    classe_info_final = CLASSES_DATA.get(classe_key_final,{})
                    equipamento_inicial = classe_info_final.get('equipamento_inicial', [])
                    inventario_atual = ficha_em_criacao.get('inventario', [])
                    for eq_item in equipamento_inicial:
                        nome_eq_item = eq_item.get("nome") if isinstance(eq_item, dict) else eq_item
                        if not any( (item_inv.get("nome") if isinstance(item_inv, dict) else item_inv) == nome_eq_item for item_inv in inventario_atual):
                            inventario_atual.append(eq_item)
                    
                    ca_final_calculada = calcular_ca_final_com_equipamento(
                        ficha_em_criacao.get('ca_base', 10), inventario_atual, ficha_em_criacao.get('modificadores',{}))

                    player_ref.update({
                        'estado_criacao': 'AGUARDANDO_BACKGROUND',
                        'ficha_em_criacao.inventario': inventario_atual,
                        'ficha_em_criacao.ca_final': ca_final_calculada,
                        'ficha_em_criacao.pericias_escolhas_restantes': firestore.DELETE_FIELD,
                        'ficha_em_criacao.pericias_opcoes_atuais': firestore.DELETE_FIELD
                    })
                    edit_telegram_message(chat_id, message_id, f"Perícia *{pericia_escolhida}* adicionada. Todas as perícias de classe foram escolhidas.")
                    send_telegram_message(chat_id, f"Equipamento inicial adicionado. Sua Classe de Armadura (CA) final é *{ca_final_calculada}*.\n\nAgora, vamos à sua história. O que você fazia antes de se tornar um aventureiro?")
                else:
                    texto = f"Perícia *{pericia_escolhida}* adicionada.\n"
                    texto += f"Você ainda pode escolher *{pericias_escolhas_restantes}* perícia(s) da lista abaixo. Escolha a próxima:"
                    botoes_prox_pericia = [[{'text': p, 'callback_data': f'skill_choice:{p}'}] for p in pericias_opcoes_atuais]
                    reply_markup_prox = {'inline_keyboard': [botoes_prox_pericia[i:i + 3] for i in range(0, len(botoes_prox_pericia), 3)] if len(botoes_prox_pericia) > 3 else botoes_prox_pericia}
                    edit_telegram_message(chat_id, message_id, texto, reply_markup_prox)

            # --- CALLBACKS DE COMBATE ---
            elif callback_data.startswith('ataque_rolar_d20:'):
                parts = callback_data.split(':', 4)
                alvo_descrito_enc, nome_arma_enc, bonus_ataque_str, attr_ataque = parts[1], parts[2], parts[3], parts[4]
                alvo_descrito = urllib.parse.unquote_plus(alvo_descrito_enc)
                nome_arma = urllib.parse.unquote_plus(nome_arma_enc)
                bonus_ataque_final = int(bonus_ataque_str)
                resultado_d20_puro = random.randint(1, 20)
                resultado_ataque_total = resultado_d20_puro + bonus_ataque_final
                
                edit_telegram_message(chat_id, message_id, 
                    f"Atacando {alvo_descrito} com {nome_arma}...\n"
                    f"d20: *{resultado_d20_puro}* + Bônus de Ataque (+{bonus_ataque_final}) = Resultado Total: *{resultado_ataque_total}*")

                ficha_jogador = player_data.get('ficha', {})
                historico_atual = player_data.get('historico', [])
                acao_ataque_jogador = f"Ataca {alvo_descrito} com {nome_arma} (rolagem d20: {resultado_d20_puro}, bônus +{bonus_ataque_final}, total ataque: {resultado_ataque_total})."
                entrada_jogador_hist = {"role": "user", "parts": [acao_ataque_jogador]}
                historico_para_gemini = historico_atual + [entrada_jogador_hist]
                
                prompt_mestre_para_acerto = PROMPT_MESTRE_NARRADOR.format(
                    json.dumps(ficha_jogador, ensure_ascii=False),
                    json.dumps(historico_para_gemini, ensure_ascii=False),
                    f"Atacar {alvo_descrito} com {nome_arma}", resultado_d20_puro) # Passa d20 puro
                
                convo = model.start_chat(history=[{"role": msg["role"], "parts": msg["parts"]} for msg in historico_atual])
                response_acerto = convo.send_message(prompt_mestre_para_acerto)
                narração_acerto = response_acerto.text
                send_telegram_message(chat_id, narração_acerto)
                entrada_modelo_hist_acerto = {"role": "model", "parts": [narração_acerto]}
                
                acerto_detectado = any(palavra in narração_acerto.lower() for palavra in ["acerta", "atinge", "consegue ferir", "golpe certeiro", "impacta", "conecta"])

                if acerto_detectado:
                    arma_usada_info = None
                    for item_inv in ficha_jogador.get('inventario', []):
                        if isinstance(item_inv, dict) and item_inv.get('nome') == nome_arma:
                            arma_usada_info = item_inv; break
                    
                    if arma_usada_info:
                        dado_dano_arma = arma_usada_info.get('dado_dano', '1d4')
                        tipo_dano_arma = arma_usada_info.get('tipo_dano_arma', 'concussão')
                        attr_dano_arma = arma_usada_info.get('atributo_padrao', attr_ataque)
                        if "acuidade" in arma_usada_info.get('propriedades_arma', []) and ficha_jogador.get('modificadores',{}).get('des',-5) > ficha_jogador.get('modificadores',{}).get('for',-5):
                            attr_dano_arma = 'des'

                        dado_dano_arma_enc = urllib.parse.quote_plus(dado_dano_arma)
                        teclado_dano = {'inline_keyboard': [[{'text': f'💥 Rolar Dano ({dado_dano_arma}) com {nome_arma}', 
                                                              'callback_data': f'ataque_rolar_dano:{alvo_descrito_enc}:{nome_arma_enc}:{attr_dano_arma}:{dado_dano_arma_enc}:{tipo_dano_arma}'}]]}
                        send_telegram_message(chat_id, "Seu golpe conectou! Determine o estrago:", teclado_dano)
                        player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist, entrada_modelo_hist_acerto])})
                    else:
                        send_telegram_message(chat_id, f"(Mestre: Não encontrei os detalhes da arma {nome_arma} para o dano.)")
                        player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist, entrada_modelo_hist_acerto])})
                else:
                    player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist, entrada_modelo_hist_acerto])})

            elif callback_data.startswith('ataque_rolar_dano:'):
                parts = callback_data.split(':', 5)
                alvo_descrito_enc, nome_arma_enc, attr_dano, dado_dano_arma_enc, tipo_dano_arma = parts[1], parts[2], parts[3], parts[4], parts[5]
                alvo_descrito = urllib.parse.unquote_plus(alvo_descrito_enc)
                nome_arma = urllib.parse.unquote_plus(nome_arma_enc)
                dado_dano_arma_str = urllib.parse.unquote_plus(dado_dano_arma_enc)

                ficha_jogador = player_data.get('ficha', {})
                modificadores = ficha_jogador.get('modificadores', {})
                mod_dano = modificadores.get(attr_dano, 0)
                dano_total, rolagem_dano_str_fmt = rolar_dados_dano(dado_dano_arma_str, mod_dano)

                edit_telegram_message(chat_id, message_id, 
                    f"Dano com *{nome_arma}* em *{alvo_descrito}*:\n"
                    f"Dados da Arma: {dado_dano_arma_str}\n"
                    f"Rolagem dos Dados: {rolagem_dano_str_fmt}\n"
                    f"Dano Total Causado: *{dano_total}* de dano *{tipo_dano_arma}*!")

                historico_atual = player_data.get('historico', [])
                acao_dano_jogador = f"Causa {dano_total} de dano {tipo_dano_arma} em {alvo_descrito} com {nome_arma}."
                entrada_jogador_hist_dano = {"role": "user", "parts": [acao_dano_jogador]}
                historico_para_gemini_dano = historico_atual + [entrada_jogador_hist_dano]
                
                prompt_narrar_dano = PROMPT_MESTRE_NARRADOR.format(
                    json.dumps(ficha_jogador, ensure_ascii=False),
                    json.dumps(historico_para_gemini_dano, ensure_ascii=False),
                    acao_dano_jogador, 0 ) 

                convo = model.start_chat(history=[{"role": msg["role"], "parts": msg["parts"]} for msg in historico_atual])
                response_dano_narrado = convo.send_message(prompt_narrar_dano)
                send_telegram_message(chat_id, response_dano_narrado.text)
                entrada_modelo_hist_dano = {"role": "model", "parts": [response_dano_narrado.text]}
                player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist_dano, entrada_modelo_hist_dano])})


        elif 'message' in update:
            message = update['message']
            user_id, chat_id, user_text = str(message['from']['id']), message['chat']['id'], message['text']
            chat_id_para_erro = chat_id
            player_ref = db.collection('jogadores').document(user_id)
            player_doc = player_ref.get()
            player_data = player_doc.to_dict() if player_doc.exists else {}

            if user_text.lower() == '/start':
                player_data_dict = player_doc.to_dict() if player_doc.exists else {}
                if 'ficha' in player_data_dict: send_telegram_message(chat_id, f"Bem-vindo(a) de volta, {player_data_dict['ficha']['nome']}!")
                else: send_telegram_message(chat_id, "Use /criar_personagem para forjar seu destino.")
                return "OK", 200

            if user_text.lower() == '/criar_personagem':
                player_ref.set({'estado_criacao': 'AGUARDANDO_NOME', 
                                'ficha_em_criacao': {'pericias_proficientes': [], 'inventario': []}, 
                                'historico': []}, merge=False)
                send_telegram_message(chat_id, "Vamos forjar seu destino... Por qual nome você é conhecido?")
                return "OK", 200
            
            if user_text.lower() == '/ficha':
                hosting_url = "https://meu-rpg-duna.web.app"
                player_data_dict = player_doc.to_dict() if player_doc.exists else {}
                if 'ficha' in player_data_dict:
                    teclado = {'inline_keyboard': [[{'text': '📜 Abrir Ficha', 'web_app': {'url': hosting_url}}]]}
                    send_telegram_message(chat_id, "Sua ficha de aventureiro:", teclado)
                else: send_telegram_message(chat_id, "Crie um personagem com /criar_personagem.")
                return "OK", 200

            if user_text.lower().startswith('/atacar'):
                if 'ficha' not in player_data:
                    send_telegram_message(chat_id, "Crie um personagem primeiro com /criar_personagem.")
                    return "OK", 200

                ficha_jogador = player_data.get('ficha', {})
                inventario = ficha_jogador.get('inventario', [])
                modificadores = ficha_jogador.get('modificadores', {})
                bonus_proficiencia = ficha_jogador.get('bonus_proficiencia', 2)
                classe_jogador_key = ficha_jogador.get('classe')
                classe_info = CLASSES_DATA.get(classe_jogador_key, {})
                proficiencias_armas_classe = classe_info.get('proficiencia_armas', [])

                arma_equipada = None
                for item_inv in inventario:
                    if isinstance(item_inv, dict) and item_inv.get('tipo', '') == 'arma_equipavel':
                        arma_equipada = item_inv; break
                
                if not arma_equipada:
                    send_telegram_message(chat_id, "Nenhuma arma equipável encontrada para atacar!")
                    return "OK", 200

                nome_arma = arma_equipada.get('nome', 'arma')
                propriedades_arma = arma_equipada.get('propriedades_arma', [])
                atributo_padrao_arma = arma_equipada.get('atributo_padrao', 'for')
                
                attr_ataque = atributo_padrao_arma
                if "acuidade" in propriedades_arma and modificadores.get('des', -5) > modificadores.get('for', -5):
                    attr_ataque = 'des'
                
                bonus_attr_ataque = modificadores.get(attr_ataque, 0)
                bonus_ataque_final = bonus_attr_ataque
                tipo_arma_prof = arma_equipada.get("tipo_arma_prof", "simples")
                if tipo_arma_prof in proficiencias_armas_classe:
                    bonus_ataque_final += bonus_proficiencia

                partes_comando = user_text.split(' ', 1)
                alvo_descrito = partes_comando[1] if len(partes_comando) > 1 else "um oponente"
                alvo_descrito_enc = urllib.parse.quote_plus(alvo_descrito)
                nome_arma_enc = urllib.parse.quote_plus(nome_arma)

                texto_info_ataque = f"Você empunha sua *{nome_arma}* e mira em *{alvo_descrito}*!\n"
                texto_info_ataque += f"Seu bônus para acertar é *+{bonus_ataque_final}* (Baseado em {attr_ataque.upper()}: {bonus_attr_ataque}, Proficiência: +{bonus_proficiencia if tipo_arma_prof in proficiencias_armas_classe else 0})."
                send_telegram_message(chat_id, texto_info_ataque)
                teclado_rolar_ataque = {'inline_keyboard': [[{'text': f'⚔️ Tentar Acertar {alvo_descrito} (Rolar d20)', 
                                                               'callback_data': f'ataque_rolar_d20:{alvo_descrito_enc}:{nome_arma_enc}:{bonus_ataque_final}:{attr_ataque}'}]]}
                send_telegram_message(chat_id, "Faça sua rolagem de ataque!", teclado_rolar_ataque)
                return "OK", 200
            
            # CONTINUAÇÃO DO FLUXO DE CRIAÇÃO OU AVENTURA
            if not player_data and not user_text.lower().startswith('/'): # Redundante se já checou /atacar
                send_telegram_message(chat_id, "Use /criar_personagem para começar.")
                return "OK", 200

            estado_atual = player_data.get('estado_criacao')
            if estado_atual:
                if estado_atual == 'AGUARDANDO_NOME':
                    player_ref.update({
                        'estado_criacao': 'AGUARDANDO_RACA',
                        'ficha_em_criacao.nome': user_text,
                        'ficha_em_criacao.atributos_base': {}, 'ficha_em_criacao.atributos': {},
                        'ficha_em_criacao.modificadores': {},
                        'ficha_em_criacao.valores_atributos_pendentes': list(ARRAY_PADRAO_ATRIBUTOS),
                        'ficha_em_criacao.pericias_proficientes': [], 'ficha_em_criacao.inventario': []
                    })
                    texto_raca_msg = f"Excelente nome, *{user_text}*!\n\n"
                    if RACAS_DATA:
                        texto_raca_msg += "Cada povo em Aethel tem suas próprias lendas e talentos. Qual é a sua origem? Escolha sua Raça:"
                        botoes_r = [[{'text': r_data['nome_exibido'], 'callback_data': f'race_choice:{r_key}'}] for r_key, r_data in RACAS_DATA.items()]
                        botoes_r.sort(key=lambda r_row: r_row[0]['text'])
                        send_telegram_message(chat_id, texto_raca_msg, {'inline_keyboard': botoes_r})
                    else:
                        send_telegram_message(chat_id, texto_raca_msg + " (Raças não carregadas, pulando para atributos).")
                        player_ref.update({'estado_criacao': 'AGUARDANDO_DISTRIBUICAO_ATRIBUTOS'})
                        primeiro_val = ARRAY_PADRAO_ATRIBUTOS[0]
                        txt_dist = "Vamos distribuir seus Atributos Fundamentais usando os valores: 15, 14, 13, 12, 10, 8.\n"
                        txt_dist += f"Começando pelo valor mais alto, *{primeiro_val}*. Em qual atributo você deseja aplicá-lo?"
                        b_dist_buttons = []
                        for attr_k_upper in ATRIBUTOS_LISTA:
                            b_dist_buttons.append({'text': f'{obter_nome_completo_atributo(attr_k_upper)} ({attr_k_upper})', 
                                                   'callback_data': f'distribute_attr:{primeiro_val}:{attr_k_upper}'})
                        reply_markup_dist_fallback = {'inline_keyboard': [b_dist_buttons[i:i + 2] for i in range(0, len(b_dist_buttons), 2)]}
                        send_telegram_message(chat_id, txt_dist, reply_markup_dist_fallback)
                elif estado_atual == 'AGUARDANDO_BACKGROUND':
                    player_ref.update({'estado_criacao': 'AGUARDANDO_MOTIVACAO', 'ficha_em_criacao.background': user_text})
                    send_telegram_message(chat_id, "Interessante... E toda jornada tem um começo. O que te jogou na estrada em busca de aventura?")
                elif estado_atual == 'AGUARDANDO_MOTIVACAO':
                    player_ref.update({'estado_criacao': 'AGUARDANDO_FALHA', 'ficha_em_criacao.motivacao': user_text})
                    send_telegram_message(chat_id, "Até os maiores heróis têm uma fraqueza que os assombra. Qual é a sua?")
                elif estado_atual == 'AGUARDANDO_FALHA':
                    ficha_final_doc = player_ref.get()
                    ficha_completa_em_criacao = ficha_final_doc.to_dict().get('ficha_em_criacao', {})
                    ficha_completa_em_criacao['falha'] = user_text
                    ficha_completa_em_criacao.update({'nivel': 1, 'marcos': 0}) 
                    if 'ca_final' not in ficha_completa_em_criacao:
                        ficha_completa_em_criacao['ca_final'] = calcular_ca_final_com_equipamento(
                            ficha_completa_em_criacao.get('ca_base', 10),
                            ficha_completa_em_criacao.get('inventario', []),
                            ficha_completa_em_criacao.get('modificadores', {}))
                    if 'bonus_proficiencia' not in ficha_completa_em_criacao: ficha_completa_em_criacao['bonus_proficiencia'] = 2
                    if 'recursos' not in ficha_completa_em_criacao: ficha_completa_em_criacao['recursos'] = {} 
                    if 'magias' not in ficha_completa_em_criacao: ficha_completa_em_criacao['magias'] = {'conhecidas': [], 'preparadas': [], 'slots_n1_atuais': 0, 'slots_n1_max':0}
                    if 'inventario' not in ficha_completa_em_criacao: ficha_completa_em_criacao['inventario'] = []
                    player_ref.set({'ficha': ficha_completa_em_criacao, 'historico': player_data.get('historico', []) }, merge=True) 
                    player_ref.update({'estado_criacao': firestore.DELETE_FIELD, 'ficha_em_criacao': firestore.DELETE_FIELD})
                    send_telegram_message(chat_id, f"Perfeito! Seu personagem está pronto!\n\nUse /start para iniciar sua jornada.")
            else: # MODO DE AVENTURA (AÇÕES GENÉRICAS QUE NÃO SÃO /atacar)
                if not player_doc.exists or 'ficha' not in player_data:
                    send_telegram_message(chat_id, "Use /criar_personagem para começar.")
                    return "OK", 200
                prompt_arbitro = PROMPT_ARBITRO.format(user_text)
                convo_arbitro = model.start_chat(history=[])
                resposta_arbitro = convo_arbitro.send_message(prompt_arbitro).text.strip().upper()
                entrada_jogador_hist = {"role": "user", "parts": [user_text]}
                historico_atual = player_data.get('historico', [])
                if resposta_arbitro == "SIM":
                    texto_pergunta = "O destino é incerto. Teste sua sorte."
                    teclado = {'inline_keyboard': [[{'text': '🎲 Rolar d20', 'callback_data': 'roll_d20'}]]}
                    sent_message = send_telegram_message(chat_id, texto_pergunta, teclado)
                    if sent_message and sent_message.get('ok'):
                        message_id_dado = sent_message['result']['message_id']
                        player_ref.update({'acao_pendente': user_text, 'id_mensagem_dado': message_id_dado})
                else: 
                    ficha_aventura = player_data.get('ficha', {})
                    prompt_simples_fmt = PROMPT_NARRADOR_SIMPLES.format(user_text, json.dumps(ficha_aventura, ensure_ascii=False))
                    convo_simples = model.start_chat(history=[{"role": msg["role"], "parts": msg["parts"]} for msg in historico_atual])
                    response_simples = convo_simples.send_message(prompt_simples_fmt)
                    send_telegram_message(chat_id, response_simples.text)
                    entrada_modelo_hist = {"role": "model", "parts": [response_simples.text]}
                    player_ref.update({'historico': firestore.ArrayUnion([entrada_jogador_hist, entrada_modelo_hist])})
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERRO DETALHADO NA FUNÇÃO: {error_trace}")
        if chat_id_para_erro:
            send_telegram_message(chat_id_para_erro, f"Ocorreu um erro no multiverso. (Detalhe: {type(e).__name__})")
    return "OK", 200

# ==============================================================================
# === CLOUD FUNCTION 2: A API SEGURA PARA A FICHA DE PERSONAGEM              ===
# ==============================================================================
@functions_framework.http
def get_char_sheet(request):
    headers = {'Access-Control-Allow-Origin': '*','Access-Control-Allow-Methods': 'POST, OPTIONS','Access-Control-Allow-Headers': 'Content-Type, Authorization'}
    if request.method == 'OPTIONS': return ('', 204, headers)
    request_json = request.get_json(silent=True)
    if not request_json or 'initData' not in request_json: return ({'error': 'initData não fornecido.'}, 400, headers)
    init_data = request_json['initData']
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        hash_recebido = parsed_data.pop('hash', None)
        if not hash_recebido: raise ValueError("Hash de validação não encontrado.")
        chaves_ordenadas = sorted(parsed_data.keys())
        data_check_string = "\n".join(f"{key}={parsed_data[key]}" for key in chaves_ordenadas)
        secret_key = hmac.new("WebAppData".encode('utf-8'), TELEGRAM_TOKEN.encode('utf-8'), hashlib.sha256).digest()
        hash_calculado = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(hash_calculado, hash_recebido): return ({'error': 'Falha na validação dos dados (hash inválido).'}, 403, headers)
        user_data_str = parsed_data.get('user');
        if not user_data_str: return ({'error': 'Dados do usuário não encontrados.'}, 400, headers)
        user_data = json.loads(user_data_str); user_id = str(user_data.get('id'))
        if not user_id: return ({'error': 'ID de usuário não encontrado.'}, 400, headers)
        player_ref = db.collection('jogadores').document(user_id); player_doc = player_ref.get()
        if player_doc.exists:
            ficha_data = player_doc.to_dict().get('ficha', {})
            return (json.dumps(ficha_data, ensure_ascii=False), 200, headers)
        else: return ({'error': 'Ficha não encontrada.'}, 404, headers)
    except json.JSONDecodeError as e: print(f"ERRO API JSONDecodeError: {traceback.format_exc()}"); return ({'error': f'Erro ao decodificar dados: {str(e)}'}, 400, headers)
    except ValueError as e: print(f"ERRO API ValueError: {traceback.format_exc()}"); return ({'error': str(e)}, 400, headers)
    except Exception as e: print(f"ERRO GERAL API: {traceback.format_exc()}"); return ({'error': f'Erro interno: {str(e)}'}, 500, headers)