# modules/game_logic/utils.py
import random

# Constantes do Jogo
ATRIBUTOS_LISTA = ["FOR", "DES", "CON", "INT", "SAB", "CAR"]
ARRAY_PADRAO_ATRIBUTOS = sorted([15, 14, 13, 12, 10, 8], reverse=True)

# Funções de Cálculo de Personagem
def calcular_modificador(valor_atributo):
    """Calcula o modificador de um atributo D&D 5e."""
    return (valor_atributo - 10) // 2

def obter_nome_completo_atributo(attr_key_upper):
    """Retorna o nome completo de um atributo a partir de sua abreviação."""
    nomes_atributos = {
        "FOR": "Força", "DES": "Destreza", "CON": "Constituição",
        "INT": "Inteligência", "SAB": "Sabedoria", "CAR": "Carisma"
    }
    return nomes_atributos.get(attr_key_upper, attr_key_upper)

def calcular_ca_final_com_equipamento(ca_base_personagem, inventario, modificadores):
    """Calcula a CA final baseada no inventário (lógica simplificada)."""
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
            
    if armadura_principal_ca_valor == 0:  # Nenhuma armadura corporal principal, usa CA base que já inclui ModDES
        ca_final = ca_base_personagem
    
    if tem_escudo:
        ca_final += 2
        
    return ca_final

# Funções de Cálculo de Combate
def parse_dado_str(dado_str):
    """Parseia uma string como '1d8' para (numero_dados, tipo_dado)."""
    if not isinstance(dado_str, str) or 'd' not in dado_str: return 0, 0
    parts = dado_str.lower().split('d')
    try:
        num_dados = int(parts[0]) if parts[0] else 1
        tipo_dado = int(parts[1])
        return num_dados, tipo_dado
    except (ValueError, IndexError):
        return 0, 0

def rolar_dados_dano(dado_str, modificador_dano):
    """Rola dados (ex: '1d8') e adiciona modificador, retorna total e string da rolagem."""
    num_dados, tipo_dado = parse_dado_str(dado_str)
    if num_dados == 0:
        return 0, "Erro na formatação do dado"
    
    rolagens = []
    soma_rolagens = 0
    for _ in range(num_dados):
        roll = random.randint(1, tipo_dado)
        rolagens.append(roll)
        soma_rolagens += roll
    
    total_dano = soma_rolagens + modificador_dano
    rolagem_str_fmt = f"{soma_rolagens} ({'+'.join(map(str, rolagens))})"
    if modificador_dano != 0:
        rolagem_str_fmt += f" {'+' if modificador_dano >=0 else ''}{modificador_dano} [Mod]"
    return total_dano, rolagem_str_fmt