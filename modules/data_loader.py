# modules/data_loader.py
# Versão final, dinâmica e à prova de futuro.

import json
import os
import logging

def carregar_dados_jogo():
    """
    Carrega todos os dados da pasta game_data de forma dinâmica,
    agregando conteúdo de subpastas.
    """
    dados = {}
    game_data_path = 'game_data'

    try:
        for item_name in os.listdir(game_data_path):
            caminho_completo = os.path.join(game_data_path, item_name)
            
            # Remove a extensão .json para usar como chave, se for um ficheiro
            chave_dado, extensao = os.path.splitext(item_name)

            # Se for um diretório, agrega todos os JSONs dentro dele
            if os.path.isdir(caminho_completo):
                dados[chave_dado] = {}
                for filename in os.listdir(caminho_completo):
                    if filename.endswith('.json'):
                        file_path = os.path.join(caminho_completo, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                dados[chave_dado].update(json.load(f))
                        except Exception as e:
                            logging.error(f"Erro ao carregar o ficheiro agregado '{file_path}': {e}")
            
            # Se for um ficheiro JSON no diretório principal
            elif extensao == '.json':
                try:
                    with open(caminho_completo, 'r', encoding='utf-8') as f:
                        dados[chave_dado] = json.load(f)
                except Exception as e:
                    logging.error(f"Erro ao carregar o ficheiro de dados '{caminho_completo}': {e}")
    
    except FileNotFoundError:
        logging.error(f"O diretório '{game_data_path}' não foi encontrado. Verifique a estrutura do projeto.")
        return {}
        
    return dados