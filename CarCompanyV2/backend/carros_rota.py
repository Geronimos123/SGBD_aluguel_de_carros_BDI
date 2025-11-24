from flask import Blueprint, jsonify, request
from database.conector import DatabaseManager

carros_blueprint = Blueprint("carros", __name__)


# ============================================================
# Helpers
# ============================================================
def bad_request(msg, fields=None):
    resp = {"erro": msg}
    if fields:
        resp["faltando"] = fields
    return jsonify(resp), 400


def internal_error(msg="Erro interno no servidor"):
    return jsonify({"erro": msg}), 500


def validate_fields(data, required):
    missing = [f for f in required if f not in data or data[f] in (None, "")]
    return missing


# ============================================================
# 1. Listar todos os carros
# ============================================================
@carros_blueprint.route("/carros", methods=["GET"])
def listar_carros():
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                c.placa, 
                c.placa as id, -- Frontend antigo pode procurar por 'id'
                c.nome, 
                c.tipo_categoria, 
                c.imagem_url AS imagem,
                c.status_carro,
                cat.preco_diaria AS preco,
                cat.descricao AS descricao_categoria
            FROM Carro c
            JOIN Categoria cat ON cat.tipo = c.tipo_categoria
            ORDER BY c.nome;
        """
        carros = db.execute_select_all(query)
        return jsonify({"carros": carros}), 200
    except Exception as e:
        print(f"Erro: {e}")
        return internal_error()

# ============================================================
# 2. Obter carro por placa
# ============================================================
@carros_blueprint.route("/carros/<placa>", methods=["GET"])
def obter_carro(placa):
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                c.placa, 
                c.placa as id,
                c.nome, 
                c.ano,
                c.quilometragem,
                c.chassi,
                c.tipo_categoria, 
                c.imagem_url AS imagem,
                c.status_carro,
                cat.descricao,
                cat.preco_diaria AS preco
            FROM Carro c
            JOIN Categoria cat ON cat.tipo = c.tipo_categoria
            WHERE c.placa = %s;
        """
        carro = db.execute_select_one(query, (placa,))

        if not carro:
            return jsonify({"erro": "Carro não encontrado"}), 404

        return jsonify(carro), 200
    except Exception:
        return internal_error()

# ============================================================
# 3. Listar Placas Disponíveis por Modelo (Para o Select de Aluguel)
# ============================================================
@carros_blueprint.route("/carros/placas/<nome_modelo>", methods=["GET"])
def listar_placas_por_modelo(nome_modelo):
    db = DatabaseManager()
    try:
        query = """
            SELECT placa 
            FROM Carro 
            WHERE nome = %s AND status_carro = 'DISPONIVEL';
        """
        placas = db.execute_select_all(query, (nome_modelo,))
        return jsonify(placas), 200
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"erro": "Erro ao buscar placas"}), 500

# ============================================================
# 4. Criar carro 
# ============================================================
@carros_blueprint.route("/carros", methods=["POST"])
def criar_carro():
    data = request.json or {}
    
    # Campos obrigatórios conforme novo banco
    required = ["placa", "nome", "chassi", "ano", "tipo_categoria", "imagem_url"]
    missing = validate_fields(data, required)
    
    if missing:
        return jsonify({"erro": "Campos faltando", "campos": missing}), 400

    db = DatabaseManager()
    try:
        query = """
            INSERT INTO Carro (placa, nome, chassi, ano, tipo_categoria, imagem_url, status_carro, quilometragem)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        db.execute_statement(
            query,
            (
                data["placa"],
                data["nome"],
                data["chassi"],
                data["ano"],
                data["tipo_categoria"],
                data["imagem_url"],
                data.get("status_carro", "DISPONIVEL"),
                data.get("quilometragem", 0)
            ),
        )
        return jsonify({"mensagem": "Carro cadastrado com sucesso!"}), 201
    except Exception as e:
        print(f"Erro: {e}")
        return internal_error()


# ============================================================
# 5. Atualizar carro
# ============================================================
@carros_blueprint.route("/carros/<placa>", methods=["PUT"])
def atualizar_carro(placa):
    data = request.json or {}

    db = DatabaseManager()
    try:
        query = """
            UPDATE Carro
            SET tipo_categoria = COALESCE(%s, tipo_categoria),
                status_carro = COALESCE(%s, status_carro),
                quilometragem = COALESCE(%s, quilometragem)
            WHERE placa = %s;
        """
        db.execute_statement(
            query,
            (
                data.get("tipo_categoria"),
                data.get("status_carro"),
                data.get("quilometragem"),
                placa,
            ),
        )
        return jsonify({"mensagem": "Carro atualizado com sucesso!"}), 200
    except Exception as e:
        print("ERRO:", e)
        return internal_error()



# ============================================================
# 6. Remover carro
# ============================================================
@carros_blueprint.route("/carros/<placa>", methods=["DELETE"])
def deletar_carro(placa):
    db = DatabaseManager()
    try:
        # Cuidado: Se tiver aluguel ou manutenção, o banco vai bloquear (FK constraint)
        query = "DELETE FROM Carro WHERE placa = %s;"
        success = db.execute_statement(query, (placa,))
        if not success:
             return jsonify({"erro": "Não é possível remover este carro pois ele possui histórico."}), 400
             
        return jsonify({"mensagem": "Carro removido com sucesso!"}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 7. Listar categorias
# ============================================================
@carros_blueprint.route("/categorias", methods=["GET"])
def listar_categorias():
    db = DatabaseManager()
    try:
        query = "SELECT tipo, preco_diaria AS preco, descricao FROM Categoria ORDER BY tipo;"
        categorias = db.execute_select_all(query)
        return jsonify({"categorias": categorias}), 200
    except Exception as e:
        return internal_error(str(e))


# ============================================================
# 8. Carros com status (DISPONÍVEL / ALUGADO / EM MANUTENÇÃO)
# ============================================================
@carros_blueprint.route("/carros/status", methods=["GET"])
def listar_carros_status():
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                c.placa,
                c.tipo_categoria,
                cat.preco AS preco_categoria,
                c.num_manutencao,
                CASE
                    WHEN m.num_manutencao IS NOT NULL
                         AND (m.data_retorno IS NULL OR m.data_retorno > CURRENT_DATE)
                        THEN 'EM_MANUTENCAO'
                    WHEN EXISTS (
                        SELECT 1
                        FROM Aluguel a
                        LEFT JOIN Devolucao d ON d.num_locacao = a.num_locacao
                        WHERE a.placa = c.placa AND d.num_locacao IS NULL
                    )
                        THEN 'ALUGADO'
                    ELSE 'DISPONIVEL'
                END AS status
            FROM Carro c
            JOIN Categoria cat ON cat.tipo = c.tipo_categoria
            LEFT JOIN Manutencao m ON m.num_manutencao = c.num_manutencao
            ORDER BY c.placa;
        """
        dados = db.execute_select_all(query)
        return jsonify({"carros_status": dados}), 200
    except Exception:
        return internal_error()


# ============================================================
# 9. Carros disponíveis
# ============================================================
@carros_blueprint.route("/carros/disponiveis", methods=["GET"])
def carros_disponiveis():
    db = DatabaseManager()
    try:
        query = """
            SELECT c.placa, c.tipo_categoria, c.nome
            FROM Carro c
            WHERE NOT EXISTS (
                SELECT 1 FROM Manutencao m 
                WHERE m.placa_carro = c.placa AND m.data_retorno IS NULL
            )
            AND NOT EXISTS (
                SELECT 1 FROM Aluguel a
                LEFT JOIN Devolucao d ON d.num_locacao = a.num_locacao
                WHERE a.placa = c.placa AND d.num_locacao IS NULL
            )
            ORDER BY c.placa;
        """
        dados = db.execute_select_all(query)
        return jsonify({"carros_disponiveis": dados}), 200
    except Exception:
        return internal_error()


# ============================================================
# 10. Carros em manutenção
# ============================================================
@carros_blueprint.route("/carros/manutencao", methods=["GET"])
def carros_em_manutencao():
    db = DatabaseManager()
    try:
        # Agora a query busca na tabela Manutencao onde data_retorno é NULL
        query = """
            SELECT 
                c.placa,
                c.nome,
                m.num_manutencao,
                m.custo,
                m.data_inicio,
                m.descricao
            FROM Manutencao m
            JOIN Carro c ON c.placa = m.placa_carro
            WHERE m.data_retorno IS NULL;
        """
        dados = db.execute_select_all(query)
        return jsonify({"carros_manutencao": dados}), 200
    except Exception as e:
        print(f"Erro: {e}")
        return internal_error()