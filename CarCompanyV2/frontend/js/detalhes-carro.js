// js/detalhes.js
(async function () {
    try {
        const placa = qparam("placa");
        if (!placa) {
            alert("Carro não especificado na URL.");
            window.location.href = "index.html";
            return;
        }

        const carro = await apiFetch(`/carros/${encodeURIComponent(placa)}`);

        // mapear campos
        const nome = carro.nome || "Sem nome";
        const imagem = carro.imagem || carro.imagem_url || "placeholder.png";
        const descricao = carro.descricao || carro.descricao_categoria || "";
        const preco = carro.preco || carro.preco_diaria || 0;
        const status = carro.status_carro || carro.status || "DISPONIVEL";

        // preencher DOM
        const imgEl = document.getElementById("carro-imagem");
        if (imgEl) {
            imgEl.src = `images/${imagem}`;
            imgEl.alt = nome;
        }
        setText("carro-nome", nome);
        setText("carro-descricao", descricao);
        const precoEl = document.getElementById("carro-preco");
        if (precoEl) precoEl.textContent = `${formatCurrency(preco)} / dia`;

        // detalhes técnicos (se existirem)
        const detalhes = [];
        if (carro.ano) detalhes.push(`Ano: ${carro.ano}`);
        if (carro.quilometragem) detalhes.push(`KM: ${carro.quilometragem}`);
        if (carro.chassi) detalhes.push(`Chassi: ${carro.chassi}`);
        if (carro.placa) detalhes.push(`Placa: ${carro.placa}`);
        setText("carro-detalhes", detalhes.join(" | "));

        // botão alugar
        const btnAlugar = document.querySelector(".btn-alugar");
        if (btnAlugar) {
            if (status !== "DISPONIVEL") {
                btnAlugar.classList.add("disabled");
                btnAlugar.href = "#";
                btnAlugar.textContent = `Indisponível (${status})`;
            } else {
                btnAlugar.href = `alugar.html?placa=${encodeURIComponent(carro.placa)}`;
            }
        }
    } catch (e) {
        console.error("Erro detalhes:", e);
        alert("Erro ao carregar detalhes do carro.");
    }
})();
