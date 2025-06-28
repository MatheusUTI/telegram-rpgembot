# modules/game_logic/utils.py
# Versão final, com cálculo de ficha efetiva.

import random
import copy

# --- Constantes de Personagem ---
ATRIBUTOS_LISTA = ["FOR", "DES", "CON", "INT", "SAB", "CAR"]
ARRAY_PADRAO_ATRIBUTOS = sorted([15, 14, 13, 12, 10, 8], reverse=True)
ATRIBUTOS_MAP = {
    'FOR': 'Força', 'DES': 'Destreza', 'CON': 'Constituição',
    'INT': 'Inteligência', 'SAB': 'Sabedoria', 'CAR': 'Carisma'
}
PERICIAS_MAP = {
    'Acrobacia': 'des', 'Arcanismo': 'int', 'Atletismo': 'for', 'Atuação': 'car', 'Enganação': 'car', 
    'Furtividade': 'des', 'História': 'int', 'Intimidação': 'car', 'Intuição': 'sab', 'Investigação': 'int', 
    'Lidar com Animais': 'sab', 'Medicina': 'sab', 'Natureza': 'int', 'Percepção': 'sab', 'Persuasão': 'car', 
    'Prestidigitação': 'des', 'Religião': 'int', 'Sobrevivência': 'sab'
}

# --- NOVA FUNÇÃO PRINCIPAL ---
def calcular_ficha_efetiva(ficha_base):
    """
    Recebe uma ficha do Firestore e retorna uma ficha com todos os bônus de itens e gemas aplicados.
    """
    if not ficha_base: return {}
    
    # Começa com uma cópia da ficha base para não modificar a original
    ficha_efetiva = copy.deepcopy(ficha_base)
    
    inventario = ficha_efetiva.get('inventario', [])
    atributos_efetivos = ficha_efetiva.get('atributos', {})

    # Itera sobre o inventário para encontrar bônus de gemas
    for item in inventario:
        if isinstance(item, dict) and 'engastes' in item:
            for engaste in item.get('engastes', []):
                gema = engaste.get('gema')
                if gema:
                    efeitos = gema.get('dados_brutos', {}).get('efeitos', {})
                    
                    # Assume-se que um item equipado é ou arma ou armadura para aplicar o bônus correto
                    # TODO: Futuramente, ter um sistema de "slots de equipamento" tornaria isso mais robusto
                    efeito_aplicavel = efeitos.get('armadura') if "armadura" in item.get('tipo', '') else efeitos.get('arma')
                    
                    if efeito_aplicavel:
                        tipo_bonus = efeito_aplicavel.get('tipo_bonus', '')
                        valor_base = efeito_aplicavel.get('valor_base', 0)
                        multiplicador = gema.get('dados_brutos', {}).get('tamanho', {}).get('multiplicador_valor', 1)
                        valor_final = valor_base * multiplicador

                        # Aplica bônus de atributo
                        if tipo_bonus.startswith('atributo_'):
                            attr_key = tipo_bonus.split('_')[1]
                            if attr_key in atributos_efetivos:
                                atributos_efetivos[attr_key] += valor_final
                        
                        # Aplica bônus de vida máxima
                        elif tipo_bonus == 'vida_maxima':
                             if 'pontos_vida' in ficha_efetiva:
                                ficha_efetiva['pontos_vida']['maximos'] += valor_final
                                # Cura o jogador pelo valor aumentado (opcional, mas bom para a jogabilidade)
                                ficha_efetiva['pontos_vida']['atuais'] += valor_final


    # Recalcula modificadores e outros stats baseados nos novos atributos
    ficha_efetiva['atributos'] = atributos_efetivos
    ficha_efetiva['modificadores'] = {attr: calcular_modificador(val) for attr, val in atributos_efetivos.items()}
    
    # Recalcula CA (pode ser influenciado por novos modificadores de DES)
    ficha_efetiva['ca_final'] = calcular_ca_final_com_equipamento(
        10 + ficha_efetiva['modificadores'].get('des', 0),
        inventario,
        ficha_efetiva['modificadores']
    )

    return ficha_efetiva


# --- Funções de Cálculo de Personagem (Existentes) ---
def obter_nome_completo_atributo(attr_key_upper):
    return ATRIBUTOS_MAP.get(attr_key_upper, attr_key_upper)

def calcular_modificador(valor_atributo):
    return (valor_atributo - 10) // 2

def calcular_bonus_proficiencia(nivel):
    return (nivel - 1) // 4 + 2

def calcular_ca_final_com_equipamento(ca_base_personagem, inventario, modificadores):
    # (Lógica inalterada)
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
        elif isinstance(item, str) and "escudo" in item.lower():
            tem_escudo = True
    if armadura_principal_ca_valor == 0:
        ca_final = ca_base_personagem
    if tem_escudo:
        ca_final += 2
    return ca_final

# --- Funções de Cálculo de Combate (Existentes) ---
def parse_dado_str(dado_str):
    if not isinstance(dado_str, str) or 'd' not in dado_str: return 0, 0
    parts = dado_str.lower().split('d')
    try:
        num_dados = int(parts[0]) if parts[0] else 1
        tipo_dado = int(parts[1])
        return num_dados, tipo_dado
    except (ValueError, IndexError):
        return 0, 0

def rolar_dados_dano(dado_str, modificador_dano):
    num_dados, tipo_dado = parse_dado_str(dado_str)
    if num_dados == 0: return 0, "Erro na formatação do dado"
    rolagens = [random.randint(1, tipo_dado) for _ in range(num_dados)]
    soma_rolagens = sum(rolagens)
    total_dano = soma_rolagens + modificador_dano
    rolagem_str_fmt = f"{soma_rolagens} ({'+'.join(map(str, rolagens))})"
    if modificador_dano != 0:
        rolagem_str_fmt += f" {'+' if modificador_dano >= 0 else ''}{modificador_dano} [Mod]"
    return total_dano, rolagem_str_fmt