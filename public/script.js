// Função para preencher os dados da ficha no HTML
function displayCharData(data) {
    document.getElementById('char-nome').textContent = data.nome || "Não definido";
    document.getElementById('char-classe').textContent = data.classe || "Não definido";
    document.getElementById('char-nivel').textContent = data.nivel || "1";
    document.getElementById('char-background').textContent = data.background || "Nenhuma história contada...";
    document.getElementById('char-motivacao').textContent = data.motivacao || "Um mistério...";
    document.getElementById('char-falha').textContent = data.falha || "Ninguém é perfeito.";
    document.getElementById('char-oficio').textContent = data.oficio || "Nenhum";

    const habilidadesLista = document.getElementById('char-habilidades');
    habilidadesLista.innerHTML = ''; // Limpa a lista antes de adicionar
    if (data.habilidades_aprendidas && data.habilidades_aprendidas.length > 0) {
        data.habilidades_aprendidas.forEach(hab => {
            const li = document.createElement('li');
            li.textContent = hab;
            habilidadesLista.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = "Nenhuma habilidade aprendida.";
        habilidadesLista.appendChild(li);
    }
}

// Evento que dispara quando a página web do Telegram está pronta
window.addEventListener('load', () => {
    // Verifica se a API do Telegram Web App está disponível
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        tg.ready(); // Informa ao Telegram que a página está pronta

        // O 'passaporte' assinado pelo Telegram
        const initData = tg.initData;

        // URL da nossa API na nuvem (substitua pela URL da sua função get_char_sheet)
        const apiUrl = 'https://us-central1-meu-rpg-duna.cloudfunctions.net/get_char_sheet';

        // Faz a chamada para a nossa API, enviando os dados seguros
        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ initData: initData })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Erro da API:', data.error);
                document.getElementById('char-nome').textContent = "Erro ao carregar a ficha.";
            } else {
                displayCharData(data);
            }
        })
        .catch(error => {
            console.error('Erro de rede ou fetch:', error);
            document.getElementById('char-nome').textContent = "Não foi possível conectar ao servidor.";
        });
    } else {
        console.error("API do Telegram Web App não encontrada.");
        document.getElementById('char-nome').textContent = "Abra esta página através do bot no Telegram.";
    }
});