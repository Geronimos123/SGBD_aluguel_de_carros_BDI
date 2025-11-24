// js/detalhes-carro.js 
(async function () {
    try {
        const placa = qparam("placa");
        if (!placa) {
            showError("Carro não especificado.");
            window.location.href = "index.html";
            return;
        }

        // Mostrar loading
        setText("carro-nome", "Carregando...");
        setText("carro-descricao", "");
        setText("carro-preco", "");

        const carro = await apiFetch(`/carros/${encodeURIComponent(placa)}`);

        // Preencher dados
        const nome = carro.nome || "Sem nome";
        const imagem = carro.imagem || carro.imagem_url || "placeholder.png";
        const descricao = carro.descricao || carro.descricao_categoria || "Descrição não disponível.";
        const preco = carro.preco || carro.preco_diaria || 0;
        const status = carro.status_carro || carro.status || "DISPONIVEL";

        // Imagem
        const imgEl = document.getElementById("carro-imagem");
        if (imgEl) {
            imgEl.src = `images/${imagem}`;
            imgEl.alt = nome;
            imgEl.onerror = function() {
                this.src = 'images/placeholder.png';
            };
        }

        // Informações básicas
        setText("carro-nome", nome);
        setText("carro-descricao", descricao);
        
        const precoEl = document.getElementById("carro-preco");
        if (precoEl) precoEl.textContent = `${formatCurrency(preco)} / dia`;

        // Detalhes técnicos
        const detalhes = [];
        if (carro.ano) detalhes.push(`Ano: ${carro.ano}`);
        if (carro.quilometragem) detalhes.push(`KM: ${carro.quilometragem.toLocaleString()}`);
        if (carro.chassi) detalhes.push(`Chassi: ${carro.chassi}`);
        if (carro.placa) detalhes.push(`Placa: ${carro.placa}`);
        
        const detalhesEl = document.getElementById("carro-detalhes");
        if (detalhesEl) {
            detalhesEl.textContent = detalhes.join(" | ");
        }

        // Botão alugar
        const btnAlugar = document.querySelector(".btn-alugar");
        if (btnAlugar) {
            if (status !== "DISPONIVEL") {
                btnAlugar.classList.add("disabled");
                btnAlugar.innerHTML = `<h3>INDISPONÍVEL (${status})</h3>`;
                btnAlugar.href = "#";
                btnAlugar.onclick = (e) => e.preventDefault();
            } else {
                btnAlugar.href = `alugar.html?placa=${encodeURIComponent(placa)}`;
                btnAlugar.innerHTML = `<h3>ALUGAR AGORA</h3>`;
            }
        }

    } catch (e) {
        console.error("Erro detalhes:", e);
        showError("Erro ao carregar detalhes do carro.");
        window.location.href = "index.html";
    }
})();