# modules/data_loader.py
import json
import os

def carregar_dados_jogo():
    dados = {}
    for tipo_dado in ['classes', 'racas', 'base_items', 'affixes', 'loot_tables']:
        caminho = f'game_data/{tipo_dado}'
        if os.path.isdir(caminho): # Se for uma pasta
            dados[tipo_dado] = {}
            for filename in os.listdir(caminho):
                if filename.endswith('.json'):
                    with open(os.path.join(caminho, filename), 'r', encoding='utf-8') as f:
                        dados[tipo_dado].update(json.load(f))
        elif os.path.isfile(f'{caminho}.json'): # Se for um ficheiro
            with open(f'{caminho}.json', 'r', encoding='utf-8') as f:
                dados[tipo_dado] = json.load(f)
    return dados