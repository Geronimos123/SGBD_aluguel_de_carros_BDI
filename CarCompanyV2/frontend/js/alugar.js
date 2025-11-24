// js/alugar.js
(async function () {
    try {
        // pré-seleção via ?placa=...
        const placaParam = qparam("placa");

        // 1) Carregar funcionários (para select #func)
        const funcData = await apiFetch("/funcionarios");
        const funcionarios = funcData.funcionarios || funcData || [];
        const selectFunc = document.getElementById("func");
        if (selectFunc) {
            selectFunc.innerHTML = `<option value="">Selecione o Funcionário</option>`;
            funcionarios.forEach(f => {
                const opt = document.createElement("option");
                opt.value = f.num_funcionario ?? f.num_funcionario; // int expected
                opt.textContent = (f.nome ? `${f.nome} ` : "") + `(ID:${f.num_funcionario}, Vendas:${f.qnt_vendas ?? 0})`;
                selectFunc.appendChild(opt);
            });
        }

        // 2) Carregar carros disponíveis para popular select #carro (opcional)
        const carrosResp = await apiFetch("/carros/disponiveis");
        const carros = carrosResp.carros_disponiveis || carrosResp || [];
        const selectCarro = document.getElementById("carro");
        const selectPlaca = document.getElementById("placa");

        if (selectCarro) {
            selectCarro.innerHTML = `<option value="">Selecione</option>`;
            carros.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c.nome || c.modelo || c.tipo_categoria || "";
                opt.textContent = `${c.nome || c.placa} - ${c.tipo_categoria || ""}`;
                selectCarro.appendChild(opt);
            });
        }

        // Se veio placa na URL, tentar pré-selecionar no select placa; senão popular placas por modelo
        async function carregarPlacasPorModelo(modelo) {
            if (!modelo) return;
            const res = await apiFetch(`/carros/placas/${encodeURIComponent(modelo)}`);
            // pode retornar lista simples; adapt
            const placas = res || res.placas || [];
            if (selectPlaca) {
                selectPlaca.innerHTML = `<option value="">Selecione</option>`;
                placas.forEach(p => {
                    const opt = document.createElement("option");
                    // se retorno é um objeto {placa: 'XYZ'}
                    opt.value = p.placa || p;
                    opt.textContent = p.placa || p;
                    if (opt.value === placaParam) opt.selected = true;
                    selectPlaca.appendChild(opt);
                });
            }
        }

        // se a página recebeu ?placa=XYZ, preenche o select placa com só essa opção
        if (placaParam && selectPlaca) {
            selectPlaca.innerHTML = `<option value="${placaParam}" selected>${placaParam}</option>`;
        } else {
            // se houver select carro, populamos placas ao mudar de modelo
            if (selectCarro) {
                selectCarro.addEventListener("change", (e) => {
                    carregarPlacasPorModelo(e.target.value);
                });
            }
        }

        // 3) Submissão do formulário
        const btn = document.querySelector(".btn-confirmar");
        if (btn) {
            btn.addEventListener("click", async (ev) => {
                ev.preventDefault();
                const selectedPlaca = (document.getElementById("placa")?.value || placaParam || "").trim();
                const cpf = document.getElementById("cpf-cliente")?.value?.trim();
                const num_funcionario = parseInt(document.getElementById("func")?.value);
                const data_retirada = document.getElementById("data-retirada")?.value;
                const data_prevista_devolucao = document.getElementById("data-devolucao")?.value;
                const seguro = !!document.getElementById("seguro")?.checked;
                // acessorios: checkboxes com class 'acessorio-check'
                const acessorios = Array.from(document.querySelectorAll(".acessorio-check:checked")).map(cb => cb.value);

                // valida
                if (!selectedPlaca || !cpf || !num_funcionario || !data_retirada || !data_prevista_devolucao) {
                    alert("Preencha todos os campos obrigatórios.");
                    return;
                }

                const payload = {
                    placa: selectedPlaca,
                    cpf_cliente: cpf,
                    num_funcionario: num_funcionario,
                    data_retirada: data_retirada,
                    data_prevista_devolucao: data_prevista_devolucao,
                    seguro_contratado: seguro,
                    acessorios: acessorios,
                    valor_previsto: parseFloat(document.getElementById("valor-previsto")?.value || 0)
                };

                try {
                    const resp = await apiFetch("/aluguel", { method: "POST", body: payload });
                    // sucesso retorna {mensagem, num_locacao}
                    alert(resp.mensagem || "Aluguel registrado!");
                    // redireciona para detalhes do aluguel ou home
                    window.location.href = "index.html";
                } catch (err) {
                    console.error("Erro ao criar aluguel:", err);
                    const body = err.body || {};
                    alert(body.erro || err.message || "Erro desconhecido");
                }
            });
        }

    } catch (e) {
        console.error("Erro alugar.js:", e);
    }
})();
