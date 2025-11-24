from flask import Blueprint, request, jsonify
from database.conector import DatabaseManager
from datetime import datetime

aluguel_blueprint = Blueprint("aluguel", __name__)

# =========================================================
# Helpers
# =========================================================
def internal_error(msg="Erro interno no servidor"):
    print(f"DEBUG: {msg}")
    return jsonify({"erro": msg}), 500

def validate_fields(data, required_fields):
    missing = [f for f in required_fields if f not in data or data[f] in (None, "")]
    return missing

def parse_date(s):
    # espera 'YYYY-MM-DD'
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

# =========================================================
# 1) LISTAR ALUGUÉIS (Histórico Geral)
# =========================================================
@aluguel_blueprint.route("/aluguel", methods=["GET"])
def listar_alugueis():
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                a.num_locacao,
                a.data_retirada,
                a.valor_previo,
                a.tipo_acessorio,
                a.num_funcionario,
                a.placa,
                -- buscar cpf(s) associados via HistoricoAluguel (pode ser 1 por locação)
                (SELECT string_agg(h.cpf, ',') FROM HistoricoAluguel h WHERE h.num_locacao = a.num_locacao) AS cpfs,
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM Devolucao d WHERE d.num_locacao = a.num_locacao
                    ) THEN 'FINALIZADO'
                    ELSE 'EM_ANDAMENTO'
                END AS status_aluguel
            FROM Aluguel a
            ORDER BY a.data_retirada DESC;
        """
        dados = db.execute_select_all(query)
        return jsonify({"alugueis": dados}), 200
    except Exception as e:
        return internal_error(str(e))


# =========================================================
# 2) DETALHES DE UM ALUGUEL (com possíveis acessórios armazenados em tipo_acessorio)
# =========================================================
@aluguel_blueprint.route("/aluguel/<int:num_locacao>", methods=["GET"])
def obter_aluguel(num_locacao):
    db = DatabaseManager()
    try:
        query_main = "SELECT * FROM Aluguel WHERE num_locacao = %s"
        aluguel = db.execute_select_one(query_main, (num_locacao,))
        if not aluguel:
            return jsonify({"erro": "Aluguel não encontrado"}), 404

        # pegar cpfs no histórico
        cpfs = db.execute_select_all("SELECT cpf FROM HistoricoAluguel WHERE num_locacao = %s", (num_locacao,))
        aluguel["cpfs"] = [r["cpf"] for r in cpfs] if cpfs else []

        return jsonify(aluguel), 200
    except Exception as e:
        return internal_error(str(e))


# =========================================================
# 3) ABRIR NOVA LOCAÇÃO
# # =========================================================
@aluguel_blueprint.route("/aluguel", methods=["POST"])
def abrir_locacao():
    data = request.json or {}
    # exigir cpf_cliente mesmo que Aluguel não guarde — vamos inserir em HistoricoAluguel
    required = ["placa", "cpf_cliente", "num_funcionario", "data_retirada", "data_prevista_devolucao"]
    missing = validate_fields(data, required)
    if missing:
        return jsonify({"erro": "Campos faltando", "campos": missing}), 400

    # parse datas
    data_retirada = parse_date(data["data_retirada"])
    data_prevista = parse_date(data["data_prevista_devolucao"])
    if not data_retirada or not data_prevista:
        return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400
    if data_prevista < data_retirada:
        return jsonify({"erro": "data_prevista_devolucao não pode ser anterior a data_retirada."}), 400

    db = DatabaseManager()
    try:
        # 1) verificar se o carro existe
        carro = db.execute_select_one("SELECT placa, tipo_categoria, num_manutencao FROM Carro WHERE placa = %s", (data["placa"],))
        if not carro:
            return jsonify({"erro": "Carro inexistente"}), 404

        # 2) verificar manutenção associada (Carro.num_manutencao -> Manutencao.data_retorno)
        num_m = carro.get("num_manutencao")
        if num_m:
            man = db.execute_select_one("SELECT data_retorno FROM Manutencao WHERE num_manutencao = %s", (num_m,))
            if man and (man.get("data_retorno") is None or man.get("data_retorno") > datetime.today().date()):
                return jsonify({"erro": "Carro em manutenção e indisponível."}), 400

        # 3) verificar se já existe aluguel ativo para essa placa (Aluguel sem Devolucao)
        check_active = """
            SELECT 1 FROM Aluguel a
            LEFT JOIN Devolucao d ON d.num_locacao = a.num_locacao
            WHERE a.placa = %s AND d.num_locacao IS NULL
            LIMIT 1;
        """
        ativo = db.execute_select_one(check_active, (data["placa"],))
        if ativo:
            return jsonify({"erro": "Carro já está alugado (aluguel sem devolução)."}), 400

        # 4) inserir Aluguel
        # tipo_acessorio na tabela é VARCHAR(50) — se o cliente enviar lista, juntamos por ', '
        acessorios = data.get("acessorios")
        if isinstance(acessorios, list):
            tipo_acessorio = ", ".join(acessorios)[:50]  # cortar para caber no campo se preciso
        else:
            tipo_acessorio = (acessorios or data.get("tipo_acessorio") or None)
            if tipo_acessorio and len(tipo_acessorio) > 50:
                tipo_acessorio = tipo_acessorio[:50]

        query_aluguel = """
            INSERT INTO Aluguel
            (data_retirada, valor_previo, tipo_acessorio, num_funcionario, placa)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING num_locacao;
        """
        valor_previsto = data.get("valor_previsto")
        loc = db.execute_insert_returning(query_aluguel, (
            data_retirada,
            valor_previsto,
            tipo_acessorio,
            data["num_funcionario"],
            data["placa"]
        ))
        num_locacao = loc["num_locacao"]

        # 5) registrar histórico do cliente na tabela HistoricoAluguel
        cpf = data["cpf_cliente"]
        db.execute_statement(
            "INSERT INTO HistoricoAluguel (num_locacao, cpf) VALUES (%s, %s)",
            (num_locacao, cpf)
        )

        # Se o seu DatabaseManager expõe conn, comitar explicitamente
        try:
            if hasattr(db, "conn") and db.conn:
                db.conn.commit()
        except Exception:
            pass

        return jsonify({"mensagem": "Locação realizada!", "num_locacao": num_locacao}), 201

    except Exception as e:
        # tentar rollback se possível
        try:
            if hasattr(db, "conn") and db.conn:
                db.conn.rollback()
        except Exception:
            pass
        return internal_error(f"Erro ao abrir locação: {str(e)}")


# =========================================================
# 4) REALIZAR DEVOLUÇÃO
#    - cria Pagamento (tabela Pagamento tem coluna 'valor')
#    - insere registro em Devolucao (num_locacao, num_pagamento, combustivel_completo, estado_carro)
#    - se estado indicar dano, cria registro em Manutencao e atualiza Carro.num_manutencao
# =========================================================
@aluguel_blueprint.route("/aluguel/devolver", methods=["POST"])
def devolver_carro():
    data = request.json or {}
    required = ["num_locacao", "estado_carro", "combustivel_completo", "valor_final"]
    missing = validate_fields(data, required)
    if missing:
        return jsonify({"erro": "Campos faltando", "campos": missing}), 400

    db = DatabaseManager()
    try:
        # checar aluguel
        aluguel = db.execute_select_one("SELECT placa FROM Aluguel WHERE num_locacao = %s", (data["num_locacao"],))
        if not aluguel:
            return jsonify({"erro": "Aluguel não encontrado"}), 404
        placa = aluguel["placa"]

        # 1) criar Pagamento (tabela Pagamento tem col 'valor')
        query_pag = "INSERT INTO Pagamento (valor) VALUES (%s) RETURNING num_pagamento;"
        pag = db.execute_insert_returning(query_pag, (data["valor_final"],))
        num_pagamento_final = pag["num_pagamento"]

        # 2) inserir Devolucao
        query_dev = """
            INSERT INTO Devolucao (num_locacao, num_pagamento, combustivel_completo, estado_carro)
            VALUES (%s, %s, %s, %s);
        """
        db.execute_statement(query_dev, (
            data["num_locacao"],
            num_pagamento_final,
            data["combustivel_completo"],
            data["estado_carro"]
        ))

        # 3) Se o carro sofreu avaria, criar Manutencao e associar ao carro (Carro.num_manutencao)
        estado = (data["estado_carro"] or "").upper()
        novo_num_manut = None
        if any(tok in estado for tok in ("BATIDO", "AVARIA", "QUEBRADO", "AMASSADO", "COLISAO", "COLISÃO", "COLIDIDO")):
            # inserir Manutencao com data_retorno NULL indicando pendente
            query_ins_m = "INSERT INTO Manutencao (cpf_mecanico, custo, data_retorno) VALUES (%s, %s, %s) RETURNING num_manutencao;"
            m = db.execute_insert_returning(query_ins_m, (None, 0.0, None))
            novo_num_manut = m["num_manutencao"]
            # atualizar Carro para referenciar esta manutencao
            db.execute_statement("UPDATE Carro SET num_manutencao = %s WHERE placa = %s", (novo_num_manut, placa))

        # commit se possível
        try:
            if hasattr(db, "conn") and db.conn:
                db.conn.commit()
        except Exception:
            pass

        msg = "Devolução realizada com sucesso!"
        extra = {"num_pagamento": num_pagamento_final}
        if novo_num_manut:
            extra["num_manutencao_criado"] = novo_num_manut
            extra["observacao"] = "Carro enviado para manutenção."

        return jsonify({"mensagem": msg, **extra}), 200

    except Exception as e:
        try:
            if hasattr(db, "conn") and db.conn:
                db.conn.rollback()
        except Exception:
            pass
        return internal_error(f"Erro na devolução: {str(e)}")
