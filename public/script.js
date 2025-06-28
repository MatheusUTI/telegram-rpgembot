// O motor que dá vida à Ficha de Personagem V3.

/**
 * Função principal para preencher todos os elementos da ficha com os dados do jogador.
 * @param {object} ficha - O objeto 'ficha' completo vindo do Firestore.
 */
function displayCharData(ficha) {
    // --- Bloco de Identidade ---
    setText('char-name', ficha.nome);
    setText('char-race', ficha.raca_info.nome_exibido); // Usa o nome de exibição
    setText('char-class', ficha.classe_info.nome_exibido); // Usa o nome de exibição
    setText('char-level', ficha.nivel);

    // --- Bloco de Atributos ---
    const atributos = ficha.atributos || {};
    const modificadores = ficha.modificadores || {};
    for (const attr in atributos) {
        setText(`attr-${attr}`, atributos[attr]);
        const mod = modificadores[attr] || 0;
        setText(`mod-${attr}`, (mod >= 0 ? '+' : '') + mod);
    }

    // --- Bloco de Combate ---
    setText('stat-ac', ficha.ca_final);
    const iniciativa = ficha.iniciativa || 0;
    setText('stat-initiative', (iniciativa >= 0 ? '+' : '') + iniciativa);
    setText('stat-speed', ficha.deslocamento);

    // --- Bloco de Pontos de Vida ---
    const pv = ficha.pontos_vida || {};
    setText('hp-current', pv.atuais);
    setText('hp-max', pv.maximos);
    const hpPercent = (pv.maximos > 0) ? (pv.atuais / pv.maximos) * 100 : 0;
    const hpBar = document.getElementById('hp-current-bar');
    if (hpBar) {
        hpBar.style.width = `${hpPercent}%`;
    }

    // --- Bloco de Perícias e Testes de Resistência ---
    const PERICIAS_MAP = {
        'Acrobacia': 'des', 'Arcanismo': 'int', 'Atletismo': 'for', 'Atuação': 'car', 'Enganação': 'car', 
        'Furtividade': 'des', 'História': 'int', 'Intimidação': 'car', 'Intuição': 'sab', 'Investigação': 'int', 
        'Lidar com Animais': 'sab', 'Medicina': 'sab', 'Natureza': 'int', 'Percepção': 'sab', 'Persuasão': 'car', 
        'Prestidigitação': 'des', 'Religião': 'int', 'Sobrevivência': 'sab'
    };
    populateSkillsList('saving-throws-list', Object.keys(modificadores), ficha.testes_resistencia_proficientes || [], ficha, true);
    populateSkillsList('skills-list', Object.keys(PERICIAS_MAP), ficha.pericias_proficientes || [], ficha, false, PERICIAS_MAP);

    // --- Bloco de Equipamento e Economia ---
    const currency = ficha.currency || {};
    setText('currency-da', currency.dracmas_aco || 0);
    setText('currency-cp', currency.cravos_prata || 0);
    setText('currency-ff', currency.fragmentos_ferro || 0);
    
    // --- ALTERAÇÃO ARQUITETURAL: Nova renderização do inventário ---
    renderInventory(ficha.inventario || []);

    // --- Bloco de Habilidades e Proficiências ---
    const featuresList = document.getElementById('features-list');
    featuresList.innerHTML = '';
    if (ficha.habilidades_aprendidas && ficha.habilidades_aprendidas.length > 0) {
        ficha.habilidades_aprendidas.forEach(hab => {
            const li = document.createElement('li');
            li.textContent = hab;
            featuresList.appendChild(li);
        });
    } else {
        featuresList.innerHTML = '<li>Nenhum talento especial.</li>';
    }
    
    // --- Bloco de Personalidade ---
    setText('char-background', ficha.background);
    setText('char-motivacao', ficha.motivacao);
    setText('char-falha', ficha.falha);
    
    // Mostra a ficha e esconde o loader
    document.getElementById('loader').style.display = 'none';
    document.getElementById('ficha-container').style.display = 'block';
}

/**
 * Nova função para renderizar o inventário com engastes.
 * @param {Array} inventory - A lista de itens do inventário.
 */
function renderInventory(inventory) {
    const inventoryListDiv = document.getElementById('inventory-list');
    inventoryListDiv.innerHTML = ''; // Limpa a lista

    if (inventory.length === 0) {
        inventoryListDiv.innerHTML = '<div class="inventory-item">Mochila vazia.</div>';
        return;
    }

    inventory.forEach(item => {
        // Cria o container principal do item
        const itemDiv = document.createElement('div');
        itemDiv.className = 'inventory-item';

        // Cria o nome do item
        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = item.nome_exibido || "Item desconhecido";
        itemDiv.appendChild(nameSpan);

        // Cria o container para os engastes, se existirem
        if (item.engastes && item.engastes.length > 0) {
            const socketsContainer = document.createElement('div');
            socketsContainer.className = 'sockets-container';

            item.engastes.forEach(engaste => {
                const socketDiv = document.createElement('div');
                socketDiv.className = 'socket';
                
                // Se o engaste tiver uma gema, colore-o
                if (engaste.gema) {
                    const origem = engaste.gema.origem_racial.toLowerCase();
                    socketDiv.classList.add(`gema-${origem}`);
                    socketDiv.title = engaste.gema.nome_exibido; // Mostra o nome da gema ao passar o rato
                } else {
                    socketDiv.title = "Engaste Vazio";
                }
                socketsContainer.appendChild(socketDiv);
            });
            itemDiv.appendChild(socketsContainer);
        }
        
        inventoryListDiv.appendChild(itemDiv);
    });
}


/**
 * Helper para definir o texto de um elemento de forma segura.
 * @param {string} id - O ID do elemento HTML.
 * @param {string|number} text - O texto a ser inserido.
 */
function setText(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = text || '';
    }
}

/**
 * Constrói as listas de perícias e testes de resistência.
 */
function populateSkillsList(listId, allSkills, proficientSkills, ficha, isSavingThrow = false, skillsMap = {}) {
    const listElement = document.getElementById(listId);
    if (!listElement) return;
    listElement.innerHTML = '';
    const modificadores = ficha.modificadores || {};
    const bonusProf = ficha.proficiencia_bonus || 0;

    allSkills.forEach(skillName => {
        // Normaliza a chave da perícia para minúsculas para a verificação de proficiência
        const proficientKey = isSavingThrow ? skillName : skillName.toLowerCase();
        const isProficient = proficientSkills.includes(proficientKey);
        
        const attrKey = isSavingThrow ? skillName : (skillsMap[skillName] || 'int');
        const modValue = modificadores[attrKey] || 0;
        const totalBonus = isProficient ? modValue + bonusProf : modValue;

        const li = document.createElement('li');
        const pip = isProficient ? '<span class="proficient-pip">●</span>' : '<span class="proficient-pip">&nbsp;&nbsp;</span>';
        const bonusStr = (totalBonus >= 0 ? '+' : '') + totalBonus;
        
        const attrName = isSavingThrow ? ficha.racas_info[skillName]?.nome_exibido || skillName.toUpperCase() : skillName;
        li.innerHTML = `${pip} <b>${bonusStr}</b> ${attrName}`;
        listElement.appendChild(li);
    });
}

// --- PONTO DE ENTRADA ---
window.addEventListener('load', () => {
    const tg = window.Telegram.WebApp;
    if (!tg) {
        console.error("API do Telegram Web App não encontrada.");
        setText('loader', "Erro: Abra esta página através do bot no Telegram.");
        return;
    }
    
    tg.ready();
    tg.expand();

    const initData = tg.initData;
    const apiUrl = 'YOUR_API_URL_HERE/get_char_sheet'; // SUBSTITUA PELA SUA URL REAL

    fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData: initData })
    })
    .then(response => {
        if (!response.ok) throw new Error(`Erro de rede: ${response.statusText}`);
        return response.json();
    })
    .then(data => {
        if (data.error) throw new Error(`Erro da API: ${data.error}`);
        // A API retorna o documento do jogador, a ficha está dentro.
        displayCharData(data.ficha); 
    })
    .catch(error => {
        console.error('Erro ao carregar a ficha:', error);
        setText('loader', `Não foi possível carregar a ficha. ${error.message}`);
    });
});