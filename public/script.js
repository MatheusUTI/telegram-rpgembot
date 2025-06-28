// Versão final, apontando para o endpoint de API correto.
const ATRIBUTOS_MAP_DISPLAY = { 'for': 'Força', 'des': 'Destreza', 'con': 'Constituição', 'int': 'Inteligência', 'sab': 'Sabedoria', 'car': 'Carisma' };

function displayCharData(ficha) {
    setText('char-name', ficha.nome);
    setText('char-race', ficha.raca_info.nome_exibido);
    setText('char-class', ficha.classe_info.nome_exibido);
    setText('char-level', ficha.nivel);
    const atributos = ficha.atributos || {};
    const modificadores = ficha.modificadores || {};
    for (const attr in atributos) {
        setText(`attr-${attr}`, atributos[attr]);
        const mod = modificadores[attr] || 0;
        setText(`mod-${attr}`, (mod >= 0 ? '+' : '') + mod);
    }
    setText('stat-ac', ficha.ca_final);
    const iniciativa = ficha.iniciativa || 0;
    setText('stat-initiative', (iniciativa >= 0 ? '+' : '') + iniciativa);
    setText('stat-speed', ficha.deslocamento);
    const pv = ficha.pontos_vida || {};
    setText('hp-current', pv.atuais);
    setText('hp-max', pv.maximos);
    const hpPercent = (pv.maximos > 0) ? (pv.atuais / pv.maximos) * 100 : 0;
    const hpBar = document.getElementById('hp-current-bar');
    if (hpBar) { hpBar.style.width = `${hpPercent}%`; }
    const PERICIAS_MAP = { 'Acrobacia': 'des', 'Arcanismo': 'int', 'Atletismo': 'for', 'Atuação': 'car', 'Enganação': 'car', 'Furtividade': 'des', 'História': 'int', 'Intimidação': 'car', 'Intuição': 'sab', 'Investigação': 'int', 'Lidar com Animais': 'sab', 'Medicina': 'sab', 'Natureza': 'int', 'Percepção': 'sab', 'Persuasão': 'car', 'Prestidigitação': 'des', 'Religião': 'int', 'Sobrevivência': 'sab' };
    populateSkillsList('saving-throws-list', Object.keys(modificadores), ficha.testes_resistencia_proficientes || [], ficha, true);
    populateSkillsList('skills-list', Object.keys(PERICIAS_MAP), ficha.pericias_proficientes || [], ficha, false, PERICIAS_MAP);
    const currency = ficha.currency || {};
    setText('currency-da', currency.dracmas_aco || 0);
    setText('currency-cp', currency.cravos_prata || 0);
    setText('currency-ff', currency.fragmentos_ferro || 0);
    renderInventory(ficha.inventario || []);
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
    setText('char-background', ficha.background);
    setText('char-motivacao', ficha.motivacao);
    setText('char-falha', ficha.falha);
    document.getElementById('loader').style.display = 'none';
    document.getElementById('ficha-container').style.display = 'block';
}

function renderInventory(inventory) {
    const inventoryListDiv = document.getElementById('inventory-list');
    inventoryListDiv.innerHTML = '';
    if (inventory.length === 0) {
        inventoryListDiv.innerHTML = '<div class="inventory-item">Mochila vazia.</div>';
        return;
    }
    inventory.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'inventory-item';
        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = item.nome_exibido || "Item desconhecido";
        itemDiv.appendChild(nameSpan);
        if (item.engastes && item.engastes.length > 0) {
            const socketsContainer = document.createElement('div');
            socketsContainer.className = 'sockets-container';
            item.engastes.forEach(engaste => {
                const socketDiv = document.createElement('div');
                socketDiv.className = 'socket';
                if (engaste.gema) {
                    const origem = engaste.gema.origem_racial.toLowerCase();
                    socketDiv.classList.add(`gema-${origem}`);
                    socketDiv.title = engaste.gema.nome_exibido;
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

function setText(id, text) {
    const element = document.getElementById(id);
    if (element) { element.textContent = text || ''; }
}

function populateSkillsList(listId, allSkills, proficientSkills, ficha, isSavingThrow = false, skillsMap = {}) {
    const listElement = document.getElementById(listId);
    if (!listElement) return;
    listElement.innerHTML = '';
    const modificadores = ficha.modificadores || {};
    const bonusProf = ficha.proficiencia_bonus || 0;
    allSkills.forEach(skillKey => {
        const proficientKey = isSavingThrow ? skillKey : skillKey.toLowerCase();
        const isProficient = proficientSkills.includes(proficientKey);
        const attrKey = isSavingThrow ? skillKey : (skillsMap[skillKey] || 'int');
        const modValue = modificadores[attrKey] || 0;
        const totalBonus = isProficient ? modValue + bonusProf : modValue;
        const li = document.createElement('li');
        const pip = isProficient ? '<span class="proficient-pip">●</span>' : '<span class="proficient-pip">&nbsp;&nbsp;</span>';
        const bonusStr = (totalBonus >= 0 ? '+' : '') + totalBonus;
        const displayName = isSavingThrow ? (ATRIBUTOS_MAP_DISPLAY[skillKey] || skillKey.toUpperCase()) : skillKey;
        li.innerHTML = `${pip} <b>${bonusStr}</b> ${displayName}`;
        listElement.appendChild(li);
    });
}

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
    
    // --- ALTERAÇÃO ARQUITETURAL: Aponta para o novo URL relativo da API ---
    const apiUrl = '/api/get_char_sheet';

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
        if (!data.ficha) throw new Error("O objeto 'ficha' não foi encontrado nos dados recebidos.");
        displayCharData(data.ficha); 
    })
    .catch(error => {
        console.error('Erro ao carregar a ficha:', error);
        setText('loader', `Não foi possível carregar a ficha. ${error.message}`);
    });
});