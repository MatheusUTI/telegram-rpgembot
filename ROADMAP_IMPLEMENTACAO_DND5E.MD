# Roadmap de Implementação: D&D 5e para o RPG de Telegram "As Terras de Aethel"

Este documento serve como um checklist e guia para a implementação incremental das mecânicas do Dungeons & Dragons 5ª Edição no bot.

## Fase 0: Preparação e Refinamento Inicial (Onde estamos)

*   [x] Estrutura básica do bot com `main.py` e `classes.json`.
*   [x] Integração com Gemini para narração e arbitragem.
*   [x] Fluxo básico de criação de personagem (Nome, Classe, Background, Motivação, Falha).
*   [x] Implementação inicial de 7 classes com habilidades de nível 1.
*   [x] Sistema de rolagem de d20 para ações.
*   [x] Ficha de personagem web básica (via `get_char_sheet`).
*   [x] Histórico de conversa para Gemini.

## Fase 1: Alicerce do Personagem D&D 5e (Foco Bot Telegram)

### 1.1. Atributos (Ability Scores)
*   [ ] **Bot:** Implementar sistema de Array Padrão Simplificado (ex: 15, 14, 13, 12, 10, 8) para o jogador distribuir.
    *   [ ] Perguntar ao jogador onde alocar cada valor.
    *   [ ] Salvar os 6 atributos na `ficha.atributos`.
*   [ ] **Bot:** Calcular e salvar modificadores de atributo automaticamente em `ficha.modificadores`.
*   [ ] **Web App (Ideia Futura):** Planejar como exibir e potencialmente permitir métodos alternativos de geração.

### 1.2. Raças (Versão Simplificada Inicial)
*   [ ] **Bot:** Definir 3-5 raças iniciais no `game_data/racas.json` (ou diretamente no código, se mais simples para começar).
    *   Cada raça deve ter: `nome_exibido`, `ajustes_atributo` (ex: `{"des": 2, "int": 1}`), `deslocamento`, `tracos_raciais_simples` (array de strings com nomes dos traços).
*   [ ] **Bot:** Integrar escolha de raça no fluxo de criação de personagem (após nome, antes de atributos ou classe).
    *   [ ] Apresentar botões para escolha de raça.
    *   [ ] Aplicar ajustes de atributo da raça aos atributos base do personagem.
    *   [ ] Salvar raça escolhida e traços na ficha (`ficha.raca`, `ficha.tracos_raciais`, `ficha.deslocamento`).
    *   [ ] Informar ao jogador os bônus e traços recebidos.
*   [ ] **Web App (Ideia Futura):** Exibir detalhes completos da raça e seus traços.

### 1.3. Bônus de Proficiência
*   [ ] **Bot:** Implementar uma função ou lógica para determinar o Bônus de Proficiência baseado no nível do personagem (Nível 1-4: +2).
*   [ ] **Bot:** Salvar o bônus de proficiência atual na `ficha.bonus_proficiencia`.
*   [ ] **Web App (Ideia Futura):** Exibir o bônus de proficiência.

### 1.4. Pontos de Vida (PV) Iniciais
*   [ ] **Bot:** Para cada classe em `classes.json`, adicionar um campo `dado_vida` (ex: "d6", "d8", "d10", "d12").
*   [ ] **Bot:** Calcular PV iniciais: (Valor máximo do `dado_vida` da classe + `modificador.con`).
*   [ ] **Bot:** Salvar em `ficha.pv_maximos` e `ficha.pv_atuais`.
*   [ ] **Web App (Ideia Futura):** Mostrar cálculo de PV.

### 1.5. Classe de Armadura (CA) Inicial Simplificada
*   [ ] **Bot:** Definir uma CA inicial base para cada classe ou um item de armadura inicial padrão.
    *   Opção A (Simples): CA base fixa por classe (ex: Guerreiro CA 16, Mago CA 12).
    *   Opção B (Levemente mais complexa): 10 + `modificador.des` + bônus de armadura de um item inicial (ex: Mago = 10 + ModDES; Ladino com "Couro" = 11 + ModDES).
*   [ ] **Bot:** Salvar em `ficha.ca`.
*   [ ] **Web App (Ideia Futura):** Permitir equipar armaduras e calcular CA dinamicamente.

### 1.6. Perícias (Proficiências Iniciais)
*   [ ] **Bot:** Para cada classe em `classes.json`, adicionar `proficiencias_pericias_escolha_num` (quantas pode escolher) e `proficiencias_pericias_opcoes` (lista de perícias da qual escolher). Algumas podem ser fixas.
*   [ ] **Bot:** No fluxo de criação, após escolher a classe, apresentar as opções de perícias para o jogador selecionar.
*   [ ] **Bot:** Salvar perícias proficientes em `ficha.pericias_proficientes` (array de strings).
*   [ ] **Web App (Ideia Futura):** Listar todas as perícias, destacar proficientes, mostrar bônus.

### 1.7. Equipamento Inicial Fixo
*   [ ] **Bot:** Para cada classe em `classes.json`, definir um `equipamento_inicial` (array de objetos, ex: `[{"nome": "Espada Longa", "tipo": "arma"}, {"nome": "Escudo", "tipo": "armadura"}]`).
*   [ ] **Bot:** Adicionar este equipamento à `ficha.inventario` no final da criação do personagem.
*   [ ] **Web App (Ideia Futura):** Inventário detalhado.

## Fase 2: Mecânicas de Jogo Essenciais (Foco Bot Telegram)

### 2.1. Combate Básico
*   [ ] **Bot:** Comando `/atacar [alvo opcional]`.
    *   [ ] Determinar qual arma está "equipada" (inicialmente, a primeira arma do inventário).
    *   [ ] Calcular bônus de ataque: Modificador de Atributo relevante (FOR ou DES para Acuidade) + Bônus de Proficiência (se proficiente com a arma).
    *   [ ] Pedir rolagem de d20 ao jogador.
    *   [ ] Enviar resultado da rolagem, bônus de ataque, e detalhes do alvo (se houver) para o Gemini/Mestre decidir o acerto (comparando com CA do alvo, a ser definida pelo Mestre).
*   [ ] **Bot:** Após acerto confirmado pelo Mestre, calcular dano: Dados da arma + Modificador de Atributo relevante.
    *   [ ] Pedir rolagem de dano ao jogador.
    *   [ ] Informar o dano ao Mestre.
*   [ ] **Web App (Ideia Futura):** Interface de combate, gerenciamento de "alvos".

### 2.2. Magia (Truques e Nível 1)
*   [ ] **Bot:** Para classes conjuradoras, definir `truques_iniciais` (lista de nomes) e `magias_n1_iniciais` (lista de nomes ou número de escolhas) em `classes.json`.
*   [ ] **Bot:** Adicionar `magias.conhecidas` e `magias.preparadas` (conforme a classe) à ficha.
*   [ ] **Bot:** Implementar `magias.slots_n1_max` e `magias.slots_n1_atuais` na ficha.
*   [ ] **Bot:** Comando `/lancar_magia <nome_magia> [alvo opcional]`.
    *   [ ] Verificar se a magia é conhecida/preparada.
    *   [ ] Se for magia de Nível 1, verificar e gastar slot.
    *   [ ] Se a magia requer ataque, seguir fluxo similar ao `/atacar`.
    *   [ ] Se a magia requer teste de resistência do alvo, informar ao Mestre a CD da magia (8 + Bônus Prof. + Mod Atributo de Conjuração).
*   [ ] **Web App (Ideia Futura):** Grimório interativo.

### 2.3. Habilidades de Classe (Nível 1 Ativas)
*   [ ] **Bot:** Comando `/usar_habilidade <nome_habilidade> [alvo opcional]`.
*   [ ] **Bot:** Implementar lógica para habilidades chave de Nível 1 (ex: Fúria do Bárbaro - registrar usos, aplicar bônus narrativamente; Retomar o Fôlego do Guerreiro - curar PV).
    *   [ ] Adicionar campos de recursos à ficha (ex: `ficha.recursos.furia_usos_max`, `..._atuais`).
*   [ ] **Web App (Ideia Futura):** Botões para ativar habilidades.

### 2.4. Descansos
*   [ ] **Bot:** Comando `/descansar_longo`.
    *   [ ] Recuperar PV totais.
    *   [ ] Recuperar slots de magia.
    *   [ ] Recarregar usos de habilidades de classe.
*   [ ] **Bot (Opcional Inicial):** Comando `/descansar_curto`.
    *   [ ] Implementar Dados de Vida (`ficha.dados_vida_max`, `..._atuais`, `ficha.tipo_dado_vida`).
    *   [ ] Permitir gastar Dados de Vida para curar.
*   [ ] **Web App (Ideia Futura):** Gerenciamento de descansos.

### 2.5. Progressão de Nível (Simplificada)
*   [ ] **Bot:** Mecanismo para o Mestre (ou o bot após X marcos) conceder níveis.
*   [ ] **Bot:** Comando `/subir_nivel`.
    *   [ ] Aumentar PV (rolar Dado de Vida + Mod CON).
    *   [ ] Atualizar Bônus de Proficiência nos níveis corretos.
    *   [ ] Conceder Aumento de Atributo (ASI) nos níveis 4, 8 etc. (escolha de +2 em um ou +1 em dois).
    *   [ ] Apresentar novas habilidades de classe/subclasse conforme o `classes.json` e o novo nível.
*   [ ] **Web App (Ideia Futura):** Visualizar árvore de progressão.

## Fase 3: Expansão de Conteúdo e Mecânicas (Bot e Web App)

*   [ ] **Mais Raças e Sub-raças:** Com todos os seus traços.
*   [ ] **Antecedentes (Backgrounds):** Com proficiências e características.
*   [ ] **Talentos (Feats):** Como alternativa ao ASI.
*   [ ] **Listas de Magia Completas:** Para todos os níveis.
*   [ ] **Sistema Completo de Equipamento:** Comprar, vender, propriedades de armas/armaduras.
*   [ ] **Itens Mágicos.**
*   [ ] **Condições:** Implementar os efeitos mecânicos.
*   [ ] **Inimigos/Monstros:** Definir estatísticas para o Mestre-Gemini usar.
*   [ ] **Diário de Missões (Quest Log):** Integrado à ficha.
*   [ ] **Mapa Interativo (Web App).**
*   [ ] **Sistema de Reputação.**

## Fase 4: Recursos Avançados e Multiplayer

*   [ ] **Ficha Web Interativa:** Clicar em habilidades/itens para ver detalhes, usar itens.
*   [ ] **Ciclo Dia/Noite e Passagem de Tempo.**
*   [ ] **Modo Multiplayer:**
    *   [ ] Gerenciamento de múltiplos jogadores no mesmo chat.
    *   [ ] Sistema de iniciativa para combate em grupo.
    *   [ ] Compartilhamento de informações/estado do grupo.
*   [ ] **IA do Mestre Mais Avançada:** Usar Gemini para gerar NPCs dinâmicos, missões, controlar monstros com mais autonomia.

---

**Como Usar:**

*   Copie este conteúdo para um arquivo `ROADMAP_IMPLEMENTACAO_DND5E.md` no seu projeto.
*   À medida que você conclui um item, marque-o com `[x]`.
*   Sinta-se à vontade para adicionar sub-tarefas ou reordenar prioridades conforme avança.

Este roadmap é um guia. O importante é manter o progresso e construir sobre uma base sólida. Vamos começar pela **Fase 1.1: Atributos**!

Você gostaria de começar a discutir como implementar a geração de atributos e o cálculo de modificadores no `main.py`?