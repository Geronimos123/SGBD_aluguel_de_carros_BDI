// js/lista-carros.js
// Dependência: helpers (apiFetch, formatCurrency)
(async function () {
    // if using module-less helpers.js, they are globals
    try {
        const dados = await apiFetch("/carros");
        // backend pode retornar lista direta ou objeto {carros: []}
        const carros = Array.isArray(dados) ? dados : (dados.carros || []);

        const container = document.getElementById("lista-carros");
        if (!container) return console.warn("container #lista-carros não encontrado");

        container.innerHTML = "";

        if (carros.length === 0) {
            container.innerHTML = "<p>Nenhum carro encontrado.</p>";
            return;
        }

        carros.forEach(carro => {
            // propriedades esperadas: placa, nome, imagem_url or imagem, preco or preco_diaria, tipo_categoria, status_carro
            const placa = carro.placa || carro.id || "";
            const nome = carro.nome || "Sem nome";
            const imagem = carro.imagem || carro.imagem_url || "placeholder.png";
            const preco = carro.preco || carro.preco_diaria || 0;
            const categoria = carro.tipo_categoria || carro.categoria || "";

            let status = carro.status_carro || carro.status || "DISPONIVEL";
            let statusColor = "green";
            if (status === "ALUGADO") statusColor = "orange";
            if (status === "MANUTENCAO" || status === "EM_MANUTENCAO") statusColor = "red";

            const card = document.createElement("div");
            card.className = "col-md-4 col-sm-6 car-card mb-4";
            card.innerHTML = `
                <div class="card h-100 shadow-sm">
                    <a href="carro.html?placa=${encodeURIComponent(placa)}" class="text-decoration-none text-dark">
                        <img src="images/${imagem}" class="card-img-top" alt="${nome}" style="height:200px;object-fit:cover;" onerror="this.src='images/placeholder.png'">
                        <div class="card-body">
                            <h5 class="card-title">${nome}</h5>
                            <p class="card-text text-muted">${categoria}</p>
                            <h6 class="text-primary">${formatCurrency(preco)} / dia</h6>
                            <span class="badge" style="background-color:${statusColor};color:#fff;">${status}</span>
                        </div>
                    </a>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Erro ao carregar carros:", e);
        alert("Erro ao carregar carros. Veja console.");
    }
})();
