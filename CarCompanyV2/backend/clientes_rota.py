from flask import Blueprint, request, jsonify
from database.conector import DatabaseManager

clientes_blueprint = Blueprint("clientes", __name__)


# ============================================================
# Helpers
# ============================================================
def bad_request(msg, fields=None):
    resp = {"erro": msg}
    if fields:
        resp["faltando"] = fields
    return jsonify(resp), 400


def internal_error(msg="Erro interno no servidor"):
    print(f"DEBUG: {msg}")
    return jsonify({"erro": msg}), 500


def validate_fields(data, required):
    missing = [f for f in required if f not in data or data[f] in (None, "")]
    return missing


# ============================================================
# 1. Listar clientes
# ============================================================
@clientes_blueprint.route("/clientes", methods=["GET"])
def listar_clientes():
    db = DatabaseManager()
    try:
        query = """
            SELECT cpf, nome, endereco, telefone
            FROM Cliente
            ORDER BY nome;
        """
        clientes = db.execute_select_all(query)
        return jsonify({"clientes": clientes}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 2. Obter cliente por CPF
# ============================================================
@clientes_blueprint.route("/clientes/<cpf>", methods=["GET"])
def obter_cliente(cpf):
    db = DatabaseManager()
    try:
        query = "SELECT * FROM Cliente WHERE cpf = %s;"
        cliente = db.execute_select_one(query, (cpf,))

        if not cliente:
            return jsonify({"erro": "Cliente não encontrado"}), 404

        return jsonify(cliente), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 3. Buscar por parte do nome
# ============================================================
@clientes_blueprint.route("/clientes/busca/<nome>", methods=["GET"])
def buscar_por_nome(nome):
    db = DatabaseManager()
    try:
        query = """
            SELECT cpf, nome, endereco, telefone
            FROM Cliente
            WHERE nome ILIKE %s
            ORDER BY nome;
        """
        # ILIKE faz busca case-insensitive no PostgreSQL
        dados = db.execute_select_all(query, (f"%{nome}%",))
        return jsonify({"clientes": dados}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 4. Criar cliente
# ============================================================
@clientes_blueprint.route("/clientes", methods=["POST"])
def criar_cliente():
    data = request.json or {}

    required = ["cpf", "nome"]
    missing = validate_fields(data, required)
    if missing:
        return bad_request("Campos obrigatórios ausentes", missing)

    db = DatabaseManager()

    try:
        query = """
            INSERT INTO Cliente (cpf, nome, endereco, telefone)
            VALUES (%s, %s, %s, %s);
        """
        db.execute_statement(
            query,
            (
                data["cpf"],
                data["nome"],
                data.get("endereco"),
                data.get("telefone"),
            ),
        )

        return jsonify({"mensagem": "Cliente cadastrado com sucesso!"}), 201
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 5. Atualizar cliente
# ============================================================
@clientes_blueprint.route("/clientes/<cpf>", methods=["PUT"])
def atualizar_cliente(cpf):
    data = request.json or {}
    db = DatabaseManager()

    try:
        # CORREÇÃO: Uso de COALESCE para permitir atualização parcial
        query = """
            UPDATE Cliente
            SET nome = COALESCE(%s, nome),
                endereco = COALESCE(%s, endereco),
                telefone = COALESCE(%s, telefone)
            WHERE cpf = %s;
        """
        db.execute_statement(
            query,
            (
                data.get("nome"),
                data.get("endereco"),
                data.get("telefone"),
                cpf,
            ),
        )

        return jsonify({"mensagem": "Cliente atualizado com sucesso!"}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 6. Remover cliente
# ============================================================
@clientes_blueprint.route("/clientes/<cpf>", methods=["DELETE"])
def deletar_cliente(cpf):
    db = DatabaseManager()
    try:
        query = "DELETE FROM Cliente WHERE cpf = %s;"
        success = db.execute_statement(query, (cpf,))
        
        if not success:
             # Geralmente falha se o cliente tiver aluguéis (FK)
             return jsonify({"erro": "Não é possível remover cliente com histórico de aluguel."}), 400

        return jsonify({"mensagem": "Cliente removido com sucesso!"}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 7. Histórico de locações
# ============================================================
@clientes_blueprint.route("/clientes/<cpf>/historico", methods=["GET"])
def historico_cliente(cpf):
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                a.num_locacao,
                a.data_retirada,
                a.valor_previsto,
                a.placa,
                c.tipo_categoria,
                c.nome as nome_carro,
                CASE 
                    WHEN EXISTS (SELECT 1 FROM Devolucao d WHERE d.num_locacao = a.num_locacao) 
                    THEN 'FINALIZADO' 
                    ELSE 'EM ANDAMENTO' 
                END as status
            FROM Aluguel a
            JOIN Carro c ON c.placa = a.placa
            WHERE a.cpf_cliente = %s
            ORDER BY a.data_retirada DESC;
        """
        dados = db.execute_select_all(query, (cpf,))
        return jsonify({"historico": dados}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 8. Promoção — Clientes que alugaram TODAS as categorias
# ============================================================
@clientes_blueprint.route("/clientes/promocao/todas-categorias", methods=["GET"])
def clientes_todas_categorias():
    db = DatabaseManager()

    try:
        query = """
            SELECT cli.cpf, cli.nome
            FROM Cliente cli
            WHERE NOT EXISTS (
                SELECT 1 FROM Categoria cat
                EXCEPT
                SELECT DISTINCT car.tipo_categoria
                FROM Aluguel al
                JOIN Carro car ON car.placa = al.placa
                WHERE al.cpf_cliente = cli.cpf
            );
        """
        dados = db.execute_select_all(query)
        return jsonify({"clientes_promocao": dados}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 9. Promoção — Clientes que usaram TODOS os acessórios
# ============================================================
@clientes_blueprint.route("/clientes/promocao/todos-acessorios", methods=["GET"])
def clientes_todos_acessorios():
    db = DatabaseManager()

    try:
        # CORREÇÃO: Ajustado para usar a tabela Aluguel_Acessorio
        query = """
            SELECT cli.cpf, cli.nome
            FROM Cliente cli
            WHERE NOT EXISTS (
                SELECT ac.tipo FROM Acessorio ac
                EXCEPT
                SELECT DISTINCT aa.tipo_acessorio
                FROM Aluguel_Acessorio aa
                JOIN Aluguel a ON a.num_locacao = aa.num_locacao
                WHERE a.cpf_cliente = cli.cpf
            );
        """
        dados = db.execute_select_all(query)
        return jsonify({"clientes_promocao": dados}), 200
    except Exception as e:
        return internal_error(str(e))