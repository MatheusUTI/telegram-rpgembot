# O Futuro de Aethel: Roadmap de Desenvolvimento do RPG

Este documento delineia as ideias e direções futuras para o desenvolvimento do Telegram RPG Bot "As Terras de Aethel". O objetivo é criar uma experiência imersiva, dinâmica e expansível para os jogadores.

## I. Mundo e História (Worldbuilding & Lore)

### 1. Conflito Central e Narrativa Principal
*   **Conceito:** A Guilda dos Inventores (focada em tecnologia a vapor, progresso a qualquer custo) entra em conflito crescente com o Círculo dos Magos (guardiões da magia tradicional, receosos do desequilíbrio que a nova tecnologia pode causar).
*   **Impacto:** Este conflito será o pano de fundo para muitas missões, dilemas morais e oportunidades para o jogador influenciar o mundo.
*   **Ideia de Implementação:** Missões iniciais podem introduzir ambas as facções e suas filosofias, forçando o jogador a interagir e, eventualmente, tomar partido (ou tentar um caminho neutro).

### 2. Fações Adicionais
*   **Conceito:** Introduzir uma terceira força principal, como uma Igreja/Ordem Religiosa (ex: "Os Guardiões do Equilíbrio") que se opõe à "desnaturalidade" da tecnologia a vapor excessiva e à "arrogância" da magia descontrolada. Ou talvez uma facção subterrânea de "Renegados" que utilizam ambas as forças de formas proibidas.
*   **Impacto:** Aumenta a complexidade política, oferece mais escolhas de alianças e inimizades, e diversifica os tipos de missões e NPCs.

### 3. Geografia Expansível
*   **Conceito:** Mover-se além da cidade inicial (Aethelburg?).
*   **Exemplos de Locais:**
    *   **Porto Tempestade:** Uma cidade portuária movimentada, centro de comércio e contrabando, com forte presença da Guilda dos Inventores testando navios a vapor.
    *   **Cidadela de Granito:** Uma fortaleza anã nas montanhas, conhecida por sua engenharia tradicional e desconfiança de magia e "novidades".
    *   **Bosque Sussurrante:** Uma floresta ancestral, lar de criaturas mágicas e eremitas do Círculo dos Magos.
    *   **Ruínas Esquecidas:** Antigas ruínas de uma civilização perdida, com segredos e perigos.
*   **Impacto:** Cada local terá sua própria cultura, NPCs, monstros, recursos e linhas de missão. O Gemini pode ser usado para gerar descrições atmosféricas ricas para cada nova área explorada.

## II. Imersão do Jogador

### 1. Diário de Missões (Quest Log)
*   **Conceito:** Integrar um resumo claro dos objetivos ativos e concluídos do jogador.
*   **Implementação:**
    *   Na ficha de personagem web (`public/index.html`), adicionar uma seção "Diário de Missões".
    *   No Firestore (`jogadores/{user_id}/missoes_ativas` e `jogadores/{user_id}/missoes_concluidas`), armazenar informações como: título da missão, descrição, objetivos atuais, PNJ relacionado.
    *   Comandos como `/missoes` no Telegram para listar rapidamente.

### 2. Memória de Longo Prazo do Bot (Contexto Persistente)
*   **Conceito:** O bot (e o Mestre-Gemini) deve "lembrar-se" de interações chave com PNJs, decisões importantes do jogador e eventos passados para influenciar diálogos e desdobramentos futuros.
*   **Implementação:**
    *   Uso de "flags" no Firestore no documento do jogador (`jogadores/{user_id}/flags_mundo` ou `jogadores/{user_id}/estado_narrativo`):
        *   Ex: `salvou_mercador_da_guilda: true`, `confrontou_mago_em_biblioteca: "hostil"`, `faccao_aliada: "inventores"`.
    *   Essas flags seriam consultadas e potencialmente incluídas em prompts para o Gemini, ou usadas pela lógica do bot para alterar respostas de NPCs e disponibilidade de missões.

### 3. Ciclo de Dia e Noite / Passagem de Tempo
*   **Conceito:** Implementar uma passagem de tempo (simplificada ou mais detalhada) que afete o mundo.
*   **Impacto:**
    *   **Lojas e Serviços:** Alguns podem fechar à noite.
    *   **PNJs:** Diferentes rotinas para PNJs.
    *   **Monstros:** Certos monstros podem aparecer apenas à noite ou em condições específicas.
    *   **Atmosfera:** Narrações do Gemini podem refletir a hora do dia.
    *   **Missões:** Algumas missões podem ter componentes que só podem ser feitos de dia ou à noite.
*   **Implementação (Simplificada):** Um contador de "turnos de ação" do jogador. A cada X ações, o tempo avança (manhã -> tarde -> noite -> madrugada -> manhã). Armazenar `estado_tempo_atual` no jogador ou globalmente.

## III. Mecânicas de Jogo Aprimoradas

### 1. Mapa Interativo (Web)
*   **Conceito:** Uma página web (separada ou integrada à ficha) com um mapa do mundo que se revela à medida que o jogador explora novas áreas.
*   **Implementação:**
    *   Pode começar com uma imagem de mapa "velado" (fog of war).
    *   À medida que o jogador visita locais, a API da ficha envia os locais conhecidos (`jogadores/{user_id}/locais_descobertos`).
    *   O JavaScript no lado do cliente revela as seções correspondentes do mapa.
    *   Pontos de interesse clicáveis poderiam mostrar uma breve descrição ou permitir "viagem rápida" (se implementado).

### 2. Ficha de Personagem Web Interativa
*   **Conceito:** Tornar os elementos da ficha web (habilidades, itens de inventário) clicáveis para mostrar mais detalhes.
*   **Implementação:**
    *   Ao clicar em uma habilidade, mostrar sua descrição completa (do `classes.json`).
    *   Ao clicar em um item, mostrar sua descrição, estatísticas, talvez um botão "Usar" (que enviaria um comando de volta para o bot via `window.Telegram.WebApp.sendData()`).

### 3. Sistema de Reputação
*   **Conceito:** As ações do jogador (boas, más, neutras, alinhadas com facções) afetam como diferentes fações e PNJs o percebem e tratam.
*   **Implementação:**
    *   No Firestore (`jogadores/{user_id}/reputacao`):
        *   `guilda_inventores: 10`
        *   `circulo_magos: -5`
        *   `guarda_da_cidade: 2`
    *   Certas ações (completar missões, escolhas em diálogos) modificariam esses valores.
    *   A reputação influenciaria preços em lojas, disponibilidade de missões, reações de PNJs (amigável, neutro, hostil).

## IV. Visão de Longo Prazo (Sonhos Maiores)

### 1. Modo Multiplayer (Cooperativo)
*   **Conceito:** Permitir que o bot gerencie uma aventura para um pequeno grupo de amigos (2-4 jogadores) no mesmo chat do Telegram.
*   **Desafios:**
    *   Gerenciamento de turnos ou ações simultâneas.
    *   Estado compartilhado do grupo (localização, missões).
    *   Como o Gemini lidaria com múltiplos inputs e narraria para um grupo.
    *   Distribuição de recompensas/XP.
*   **Ideia Inicial:** Começar com um modelo onde um jogador é o "líder da ação" por turno, ou todos decidem uma ação em conjunto. O bot responderia ao grupo.

---

## Próximos Passos / Foco Inicial (Sugestões)

1.  **Mundo e História - Base:**
    *   Detalhar o conflito central (Guilda vs. Círculo) e criar 2-3 PNJs chave para cada facção.
    *   Definir Aethelburg (cidade inicial) e 1-2 locais próximos para exploração inicial.
2.  **Imersão - Fundamentos:**
    *   **Diário de Missões (Simples):** Implementar a estrutura no Firestore e uma visualização básica na ficha web. Começar com missões de introdução ao conflito.
    *   **Memória de Longo Prazo (Básica):** Introduzir algumas flags simples baseadas nas primeiras missões para testar o conceito.
3.  **Mecânicas - Qualidade de Vida:**
    *   **Ficha Web Interativa (Detalhes de Habilidades):** Permitir que o jogador clique nas habilidades na ficha para ver suas descrições.

---