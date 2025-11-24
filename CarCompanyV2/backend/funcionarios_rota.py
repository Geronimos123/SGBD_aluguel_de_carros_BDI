from flask import Blueprint, request, jsonify
from database.conector import DatabaseManager
import re
from psycopg2 import IntegrityError

funcionarios_blueprint = Blueprint("funcionarios", __name__)

# ----------------------
# Helpers
# ----------------------
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

def validar_cpf(cpf: str):
    return bool(re.fullmatch(r"\d{11}", cpf or ""))

# ----------------------
# 1 — Listar funcionários (para dropdown / lista completa)
# ----------------------
@funcionarios_blueprint.route("/funcionarios", methods=["GET"])
def listar_funcionarios():
    db = DatabaseManager()
    try:
        query = """
            SELECT num_funcionario, cpf, nome, data_inicio, endereco, telefone, qnt_vendas
            FROM Funcionario
            ORDER BY nome;
        """
        dados = db.execute_select_all(query)
        return jsonify({"funcionarios": dados}), 200
    except Exception as e:
        return internal_error(str(e))

# ----------------------
# 2 — Criar funcionário
# ----------------------
@funcionarios_blueprint.route("/funcionarios", methods=["POST"])
def criar_funcionario():
    data = request.json or {}
    required = ["cpf", "nome", "data_inicio"]
    missing = validate_fields(data, required)
    if missing:
        return bad_request("Campos faltando", missing)

    if not validar_cpf(data["cpf"]):
        return bad_request("CPF inválido. Deve conter 11 dígitos numéricos.")

    db = DatabaseManager()
    try:
        query = """
            INSERT INTO Funcionario (cpf, nome, data_inicio, endereco, telefone, qnt_vendas)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING num_funcionario;
        """
        res = db.execute_insert_returning(query, (
            data["cpf"],
            data["nome"],
            data["data_inicio"],
            data.get("endereco"),
            data.get("telefone"),
            data.get("qnt_vendas", 0)
        ))
        new_id = res.get("num_funcionario") if res else None
        return jsonify({"mensagem": "Funcionário cadastrado com sucesso!", "num_funcionario": new_id}), 201
    except IntegrityError as ie:
        # CPF duplicado, fk violation etc.
        return bad_request("Erro de integridade: possível CPF duplicado ou dado inválido.")
    except Exception as e:
        return internal_error(str(e))

# ----------------------
# 3 — Obter funcionário por ID
# ----------------------
@funcionarios_blueprint.route("/funcionarios/<int:num_funcionario>", methods=["GET"])
def obter_funcionario(num_funcionario):
    db = DatabaseManager()
    try:
        query = """
            SELECT num_funcionario, cpf, nome, data_inicio, endereco, telefone, qnt_vendas
            FROM Funcionario
            WHERE num_funcionario = %s;
        """
        funcionario = db.execute_select_one(query, (num_funcionario,))
        if not funcionario:
            return jsonify({"erro": "Funcionário não encontrado"}), 404
        return jsonify(funcionario), 200
    except Exception as e:
        return internal_error(str(e))

# ----------------------
# 4 — Atualizar funcionário (dinâmico)
# ----------------------
@funcionarios_blueprint.route("/funcionarios/<int:num_funcionario>", methods=["PUT"])
def atualizar_funcionario(num_funcionario):
    data = request.json or {}
    db = DatabaseManager()
    try:
        # se CPF presente, validar
        if "cpf" in data and not validar_cpf(data["cpf"]):
            return bad_request("CPF inválido. Deve conter 11 dígitos numéricos.")

        query = """
            UPDATE Funcionario
            SET cpf = COALESCE(%s, cpf),
                nome = COALESCE(%s, nome),
                data_inicio = COALESCE(%s, data_inicio),
                endereco = COALESCE(%s, endereco),
                telefone = COALESCE(%s, telefone),
                qnt_vendas = COALESCE(%s, qnt_vendas)
            WHERE num_funcionario = %s;
        """
        db.execute_statement(
            query,
            (
                data.get("cpf"),
                data.get("nome"),
                data.get("data_inicio"),
                data.get("endereco"),
                data.get("telefone"),
                data.get("qnt_vendas"),
                num_funcionario,
            ),
        )
        return jsonify({"mensagem": "Funcionário atualizado com sucesso!"}), 200
    except IntegrityError:
        return bad_request("Erro de integridade ao atualizar (ex: CPF duplicado).")
    except Exception as e:
        return internal_error(str(e))

# ----------------------
# 5 — Deletar funcionário
# ----------------------
@funcionarios_blueprint.route("/funcionarios/<int:num_funcionario>", methods=["DELETE"])
def deletar_funcionario(num_funcionario):
    db = DatabaseManager()
    try:
        query = "DELETE FROM Funcionario WHERE num_funcionario = %s;"
        db.execute_statement(query, (num_funcionario,))
        return jsonify({"mensagem": "Funcionário removido com sucesso!"}), 200
    except IntegrityError:
        return bad_request("Não foi possível remover: existe referência a este funcionário (FK).")
    except Exception as e:
        return internal_error(str(e))

# ----------------------
# 6 — Ranking de Vendas
# ----------------------
@funcionarios_blueprint.route("/funcionarios/ranking", methods=["GET"])
def ranking_vendas():
    db = DatabaseManager()
    try:
        query = """
            SELECT num_funcionario, cpf, nome, qnt_vendas
            FROM Funcionario
            ORDER BY qnt_vendas DESC;
        """
        dados = db.execute_select_all(query)
        return jsonify({"ranking": dados}), 200
    except Exception as e:
        return internal_error(str(e))
