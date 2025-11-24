// js/lista-carros.js - CORRIGIDO
(async function () {
    try {
        const container = document.getElementById("lista-carros");
        if (!container) {
            console.warn("Container #lista-carros não encontrado");
            return;
        }

        container.innerHTML = '<div class="text-center">Carregando carros...</div>';

        const dados = await apiFetch("/carros");
        const carros = Array.isArray(dados) ? dados : (dados.carros || []);

        if (carros.length === 0) {
            container.innerHTML = `
                <div class="col-12 text-center">
                    <p class="text-muted">Nenhum carro encontrado.</p>
                </div>
            `;
            return;
        }

        let html = '';
        carros.forEach(carro => {
            const placa = carro.placa || "";
            const nome = carro.nome || "Sem nome";
            const imagem = carro.imagem || carro.imagem_url || "placeholder.png";
            const preco = carro.preco || carro.preco_diaria || 0;
            const categoria = carro.tipo_categoria || carro.categoria || "";
            const status = carro.status_carro || carro.status || "DISPONIVEL";

            let statusColor = "success";
            let statusText = "Disponível";
            
            if (status === "ALUGADO") {
                statusColor = "warning";
                statusText = "Alugado";
            } else if (status === "MANUTENCAO") {
                statusColor = "danger";
                statusText = "Manutenção";
            }

            html += `
                <div class="col-md-4 col-sm-6 car-card mb-4">
                    <div class="card h-100 shadow-sm">
                        <a href="carro.html?placa=${encodeURIComponent(placa)}" class="text-decoration-none text-dark">
                            <img src="images/${imagem}" class="card-img-top" alt="${nome}" 
                                 style="height:200px;object-fit:cover;" 
                                 onerror="this.src='images/placeholder.png'">
                            <div class="card-body">
                                <h5 class="card-title">${nome}</h5>
                                <p class="card-text text-muted">${categoria}</p>
                                <h6 class="text-primary">${formatCurrency(preco)} / dia</h6>
                                <span class="badge bg-${statusColor}">${statusText}</span>
                            </div>
                        </a>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

    } catch (e) {
        console.error("Erro ao carregar carros:", e);
        const container = document.getElementById("lista-carros");
        if (container) {
            container.innerHTML = `
                <div class="col-12 text-center">
                    <p class="text-danger">Erro ao carregar carros. Tente novamente.</p>
                    <button class="btn btn-primary" onclick="location.reload()">Recarregar</button>
                </div>
            `;
        }
    }
})();