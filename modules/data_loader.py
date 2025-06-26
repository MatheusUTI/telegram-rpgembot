# modules/data_loader.py
import json

def log_info(message):
    """Função de log simples para informações."""
    print(f"INFO: [data_loader] {message}")

def log_error(message):
    """Função de log simples para erros."""
    print(f"ERROR: [data_loader] {message}")

def carregar_dados_jogo():
    """
    Carrega os arquivos de dados principais do jogo (classes e raças).
    Levanta um erro se o arquivo crítico de classes não puder ser carregado.
    Retorna os dados como dois dicionários.
    """
    classes_data = {}
    racas_data = {}

    # Carregar classes.json (crítico para a execução)
    try:
        log_info("Carregando game_data/classes.json...")
        with open('game_data/classes.json', 'r', encoding='utf-8') as f:
            classes_data = json.load(f)
        log_info(f"{len(classes_data)} classes carregadas com sucesso.")
        if not isinstance(classes_data, dict) or not classes_data:
            log_error("O arquivo classes.json não é um dicionário válido ou está vazio.")
            raise ValueError("classes.json inválido")
    except FileNotFoundError:
        log_error("O arquivo 'game_data/classes.json' não foi encontrado. A aplicação não pode continuar.")
        raise
    except json.JSONDecodeError as e:
        log_error(f"Falha ao decodificar 'game_data/classes.json'. Verifique a sintaxe. Erro: {e}")
        raise
    except Exception as e:
        log_error(f"Erro inesperado ao carregar 'game_data/classes.json': {e}")
        raise

    # Carregar racas.json (opcional, o jogo pode continuar sem ele)
    try:
        log_info("Carregando game_data/racas.json...")
        with open('game_data/racas.json', 'r', encoding='utf-8') as f:
            racas_data = json.load(f)
        log_info(f"{len(racas_data)} raças carregadas com sucesso.")
        if not isinstance(racas_data, dict):
            log_info("O arquivo racas.json não é um dicionário válido. Será tratado como vazio.")
            racas_data = {}
    except FileNotFoundError:
        log_info("AVISO: O arquivo 'game_data/racas.json' não foi encontrado. A escolha de raça não estará disponível.")
        racas_data = {}
    except json.JSONDecodeError as e:
        log_info(f"AVISO: Falha ao decodificar 'game_data/racas.json'. Erro: {e}")
        racas_data = {}
    except Exception as e:
        log_info(f"AVISO: Erro inesperado ao carregar 'game_data/racas.json': {e}")
        racas_data = {}

    return classes_data, racas_data