# Resumo Detalhado do Projeto: As Terras de Aethel

**Tipo de Projeto:** Bot de RPG para Telegram

**Descrição:** Este projeto consiste em um bot para a plataforma Telegram que tem como objetivo proporcionar uma experiência de jogo de RPG de fantasia. Ele se baseia nas regras da 5ª Edição de Dungeons & Dragons e integra um modelo de IA, o Gemini, para conduzir a narrativa, atuando como Mestre de Jogo. O cenário de Aethel é marcado por um conflito crescente entre a magia tradicional e o advento da tecnologia a vapor.

**Principais Características e Funcionalidades Detalhadas:**

*   **Interface do Bot no Telegram:** A interação principal dos jogadores com o jogo ocorre através de comandos enviados no chat do Telegram. Comandos como `/start` para iniciar, `/criar_personagem` para começar o processo de criação de um novo herói e `/ficha` para acessar a ficha do seu aventureiro são os pontos de entrada.
*   **Criação de Personagem:** O bot guia o jogador por um fluxo passo a passo para criar seu personagem. Isso inclui a escolha de:
    *   **Nome:** A identidade do seu herói.
    *   **Raça:** Define características inatas e bônus (baseado no arquivo `game_data/racas.json`, que inclui raças como Humano, Elfo, Anão e Halfling, com seus ajustes de atributo e traços raciais).
    *   **Classe:** Determina as habilidades, proficiências e papel do personagem (baseado no arquivo `game_data/classes.json`, com classes como Guerreiro, Mago, Ladino, Clérigo, Bárbaro e Patrulheiro, detalhando dados de vida, perícias, proficiências com armas e equipamentos iniciais).
    *   **Atributos:** Distribuição dos seis atributos principais (Força, Destreza, Constituição, Inteligência, Sabedoria, Carisma) usando um array padrão (15, 14, 13, 12, 10, 8). O bot calcula automaticamente os modificadores de atributo e aplica os bônus raciais.
    *   **Perícias:** O jogador escolhe perícias para se especializar, ganhando bônus em testes relacionados. Algumas perícias podem ser fixas por classe/raça, enquanto outras são escolhidas de uma lista.
    *   **Equipamento Inicial:** O personagem recebe um conjunto de equipamentos básicos definido pela sua classe, que é adicionado ao seu inventário.
    *   **Antecedente (Background), Motivação e Falha:** Elementos narrativos que ajudam a definir a história e personalidade do personagem, embora a implementação completa do background com proficiências e características ainda esteja no roadmap.
*   **Ficha de Personagem (Web App):** Existe uma aplicação web separada (`public/index.html`, `public/style.css`, `public/script.js`) que serve como a ficha de personagem interativa.
    *   Os jogadores acessam esta ficha através de um botão no Telegram (`/ficha`), que abre a web app com dados seguros (`initData`).
    *   A web app exibe as informações do personagem (nome, classe, nível, background, motivação, falha, ofício).
    *   Futuramente, esta ficha permitirá interagir com habilidades e itens.
*   **Lógica do Jogo (Módulos Python):** A inteligência do jogo reside nos módulos dentro de `modules/game_logic`:
    *   `character_creator.py`: Orquestra o fluxo de criação, interagindo com o usuário via mensagens e botões (callback queries) e salvando o estado temporário da ficha em criação no Firestore.
    *   `adventure_handler.py`: Processa as ações dos jogadores durante a aventura. Atualmente, lida com:
        *   Comandos como `/start` e `/ficha`.
        *   O comando `/atacar`, calculando o bônus de ataque (considerando proficiência e atributo relevante, incluindo acuidade para armas leves ou com esta propriedade) e solicitando a rolagem de d20 ao jogador.
        *   Após a confirmação de acerto pelo Mestre (IA), solicita a rolagem de dano, calculando o dano total (dados da arma + modificador de atributo).
        *   Interage com o módulo `utils.py` para cálculos.
        *   Comunica-se com o Gemini para arbitragem (`PROMPT_ARBITRO`) e narração (`PROMPT_MESTRE_NARRADOR`, `PROMPT_NARRADOR_SIMPLES`).
    *   `utils.py`: Contém funções utilitárias essenciais, como calcular modificadores de atributo, determinar a Classe de Armadura (considerando armaduras e escudos) e realizar rolagens de dados genéricas e de dano.
*   **Integração com IA (Gemini):** O modelo Gemini é fundamental para a experiência narrativa.
    *   Ele atua como Mestre de Jogo, narrando os eventos e reagindo às ações dos jogadores de forma dinâmica.
    *   É usado para arbitrar a necessidade de testes de perícia para ações complexas.
    *   Interage com o histórico da conversa (`historico` no Firestore) para manter contexto.
*   **Gerenciamento de Dados (Firestore):** O estado de cada jogador (ficha completa após a criação, ficha em criação, histórico de conversa, estado atual no fluxo de criação) é persistido no banco de dados Firestore.
*   **Carregamento de Dados:** O módulo `modules/data_loader.py` é responsável por ler os arquivos JSON (`classes.json`, `racas.json`) na inicialização da aplicação, disponibilizando os dados para a lógica do jogo.
*   **Ações no Telegram:** O módulo `modules/telegram_actions.py` abstrai as chamadas para a API do Telegram para enviar e editar mensagens, incluindo a adição de botões inline para escolhas interativas.
*   **Firebase Hosting:** A ficha de personagem web é hospedada no Firebase Hosting, tornando-a acessível via URL.
*   **Cloud Functions:** A lógica do bot e a API que serve a ficha de personagem são implementadas como funções sem servidor no Google Cloud Functions, ativadas pelos webhooks do Telegram e pelas requisições da web app.

**Visão de Futuro (Baseado no `ROADMAP_IMPLEMENTACAO_DND5E.MD`):**

O roadmap detalha as próximas etapas para expandir o jogo, divididas em fases:

*   **Fase 1 (Alicerce):** Foco em completar a implementação das mecânicas básicas do personagem D&D 5e (atributos, raças, bônus de proficiência, PV, CA inicial, perícias, equipamento inicial).
*   **Fase 2 (Essenciais):** Implementação de combate mais robusto (ataque, dano), magia (truques e magias de nível 1), habilidades de classe de nível 1 e sistemas de descanso.
*   **Fase 3 (Expansão):** Adição de mais conteúdo (raças, backgrounds, talentos, magias, equipamentos, itens mágicos, monstros) e mecânicas como condições, diário de missões, mapa interativo e sistema de reputação.
*   **Fase 4 (Avançados/Multiplayer):** Recursos mais complexos como ficha web totalmente interativa (clicar em habilidades/itens), ciclo de dia/noite, modo multiplayer (gerenciar múltiplos jogadores no mesmo chat, iniciativa) e uma IA do Mestre mais sofisticada.

**Tecnologias Utilizadas:**

*   Python (linguagem principal da lógica do bot)
*   API do Telegram Bot
*   API do Google Gemini
*   Firebase (Firestore, Hosting, Cloud Functions)
*   HTML, CSS, JavaScript (para a web app da ficha)

Em suma, "As Terras de Aethel" é um projeto em desenvolvimento ativo com o objetivo de criar uma experiência de RPG de mesa adaptada para o formato de bot de chat, utilizando a flexibilidade do Telegram e a capacidade narrativa da inteligência artificial do Gemini, com um claro plano de expansão baseado nas regras de D&D 5e.

---

### Conteúdo do arquivo: /FUTURO_DE_AETHEL.md


Em suma, "As Terras de Aethel" é um projeto em desenvolvimento ativo com o objetivo de criar uma experiência de RPG de mesa adaptada para o formato de bot de chat, utilizando a flexibilidade do Telegram e a capacidade narrativa da inteligência artificial do Gemini, com um claro plano de expansão baseado nas regras de D&D 5e.

---

### Conteúdo do arquivo: /FUTURO_DE_AETHEL.md


Em suma, "As Terras de Aethel" é um projeto em desenvolvimento ativo com o objetivo de criar uma experiência de RPG de mesa adaptada para o formato de bot de chat, utilizando a flexibilidade do Telegram e a capacidade narrativa da inteligência artificial do Gemini, com um claro plano de expansão baseado nas regras de D&D 5e.