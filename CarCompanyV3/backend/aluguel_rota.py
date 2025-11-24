from flask import Blueprint, request, jsonify
from database.conector import DatabaseManager
from datetime import datetime, date, timedelta
import re

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
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

# =========================================================
# Funções de Cálculo de Multas
# =========================================================

def calcular_multa_atraso(db, num_locacao, data_devolucao):
    """Calcula multa por atraso na devolução"""
    try:
        # Buscar data prevista e preço da diária
        query = """
            SELECT a.data_prevista_devolucao, cat.preco_diaria
            FROM Aluguel a
            JOIN Carro c ON a.placa = c.placa
            JOIN Categoria cat ON c.tipo_categoria = cat.tipo
            WHERE a.num_locacao = %s
        """
        aluguel = db.execute_select_one(query, (num_locacao,))
        
        if not aluguel:
            return 0, 0
        
        data_prevista = aluguel['data_prevista_devolucao']
        preco_diaria = float(aluguel['preco_diaria'])
        
        if data_devolucao <= data_prevista:
            return 0, 0
        
        dias_atraso = (data_devolucao - data_prevista).days
        valor_multa = dias_atraso * preco_diaria * 0.5  # 50% da diária por dia
        
        return valor_multa, dias_atraso
        
    except Exception as e:
        print(f"Erro ao calcular multa por atraso: {e}")
        return 0, 0

def calcular_multa_tanque(combustivel_completo):
    """Calcula multa por tanque não cheio"""
    if not combustivel_completo:
        return 100.00  # Valor fixo de R$ 100,00
    return 0.00

def calcular_multa_danos(valor_danos):
    """Calcula multa por danos no veículo"""
    try:
        return float(valor_danos or 0)
    except (ValueError, TypeError):
        return 0.00

def calcular_multa_km(db, num_locacao, km_registro):
    """Calcula multa por excesso de quilometragem"""
    try:
        # Buscar km previsto
        query = "SELECT km_previsto FROM Aluguel WHERE num_locacao = %s"
        aluguel = db.execute_select_one(query, (num_locacao,))
        
        if not aluguel or not aluguel.get('km_previsto'):
            return 0, 0
        
        km_previsto = aluguel['km_previsto']
        km_excedente = max(km_registro - km_previsto, 0)
        valor_por_km = 0.50  # R$ 0,50 por km excedente
        valor_multa = km_excedente * valor_por_km
        
        return valor_multa, km_excedente
        
    except Exception as e:
        print(f"Erro ao calcular multa por km: {e}")
        return 0, 0

def calcular_multa_atraso_progressivo(db, num_locacao, data_devolucao):
    """Calcula multa progressiva por atraso"""
    try:
        query = """
            SELECT a.data_prevista_devolucao, cat.preco_diaria
            FROM Aluguel a
            JOIN Carro c ON a.placa = c.placa
            JOIN Categoria cat ON c.tipo_categoria = cat.tipo
            WHERE a.num_locacao = %s
        """
        aluguel = db.execute_select_one(query, (num_locacao,))
        
        if not aluguel:
            return 0, 0
        
        data_prevista = aluguel['data_prevista_devolucao']
        preco_diaria = float(aluguel['preco_diaria'])
        
        if data_devolucao <= data_prevista:
            return 0, 0
        
        dias_atraso = (data_devolucao - data_prevista).days
        
        # Faixas progressivas
        if dias_atraso <= 3:
            multiplicador = 0.5  # 50% da diária
        elif dias_atraso <= 7:
            multiplicador = 1.0  # 100% da diária
        else:
            multiplicador = 1.5  # 150% da diária
        
        valor_multa = dias_atraso * preco_diaria * multiplicador
        return valor_multa, dias_atraso
        
    except Exception as e:
        print(f"Erro ao calcular multa progressiva: {e}")
        return 0, 0

# =========================================================
# Funções de Cálculo de Descontos
# =========================================================

def calcular_desconto_cliente_fiel(db, cpf_cliente):
    """Desconto para clientes com 5 ou mais locações"""
    try:
        query = "SELECT COUNT(*) as total FROM Aluguel WHERE cpf_cliente = %s"
        resultado = db.execute_select_one(query, (cpf_cliente,))
        
        if resultado and resultado['total'] >= 5:
            return 50.00  # R$ 50,00 fixo
        return 0.00
    except Exception as e:
        print(f"Erro ao calcular desconto fidelidade: {e}")
        return 0.00

def calcular_desconto_reserva_antecipada(db, num_locacao):
    """Desconto por reserva antecipada (mais de 7 dias)"""
    try:
        query = "SELECT data_retirada FROM Aluguel WHERE num_locacao = %s"
        aluguel = db.execute_select_one(query, (num_locacao,))
        
        if not aluguel:
            return 0.00
        
        # Se a data de retirada for mais de 7 dias após a data atual de criação
        # (Aqui estamos usando a data atual como proxy para data da reserva)
        dias_antecedencia = (aluguel['data_retirada'] - date.today()).days
        
        if dias_antecedencia >= 7:
            return 30.00  # R$ 30,00 fixo
        return 0.00
        
    except Exception as e:
        print(f"Erro ao calcular desconto reserva antecipada: {e}")
        return 0.00

def calcular_desconto_sem_multas(db, cpf_cliente, num_locacao_atual):
    """Desconto por não ter multas nas últimas 5 locações"""
    try:
        # Buscar últimas 5 locações (excluindo a atual)
        query = """
            SELECT a.num_locacao
            FROM Aluguel a
            WHERE a.cpf_cliente = %s AND a.num_locacao != %s
            ORDER BY a.data_retirada DESC
            LIMIT 5
        """
        locacoes = db.execute_select_all(query, (cpf_cliente, num_locacao_atual))
        
        if len(locacoes) < 5:
            return 0.00
        
        # Verificar se alguma dessas locações teve multa
        for locacao in locacoes:
            query_multas = """
                SELECT 1 FROM Multa m
                JOIN Pagamento p ON m.num_pagamento = p.num_pagamento
                JOIN Devolucao d ON d.num_pagamento = p.num_pagamento
                WHERE d.num_locacao = %s
            """
            tem_multa = db.execute_select_one(query_multas, (locacao['num_locacao'],))
            if tem_multa:
                return 0.00
        
        return 40.00  # R$ 40,00 fixo
        
    except Exception as e:
        print(f"Erro ao calcular desconto sem multas: {e}")
        return 0.00

def calcular_desconto_todas_categorias(db, cpf_cliente):
    """Desconto por ter alugado todas as categorias"""
    try:
        query = """
            SELECT COUNT(DISTINCT c.tipo_categoria) as categorias_utilizadas
            FROM Aluguel a
            JOIN Carro c ON a.placa = c.placa
            WHERE a.cpf_cliente = %s
        """
        resultado = db.execute_select_one(query, (cpf_cliente,))
        
        total_categorias_query = "SELECT COUNT(*) as total FROM Categoria"
        total_categorias = db.execute_select_one(total_categorias_query)
        
        if (resultado and total_categorias and 
            resultado['categorias_utilizadas'] == total_categorias['total']):
            return 60.00  # R$ 60,00 fixo
        return 0.00
        
    except Exception as e:
        print(f"Erro ao calcular desconto todas categorias: {e}")
        return 0.00

def calcular_desconto_todos_acessorios(db, cpf_cliente):
    """Desconto por ter usado todos os acessórios"""
    try:
        query = """
            SELECT COUNT(DISTINCT aa.tipo_acessorio) as acessorios_utilizados
            FROM Aluguel a
            JOIN Aluguel_Acessorio aa ON a.num_locacao = aa.num_locacao
            WHERE a.cpf_cliente = %s
        """
        resultado = db.execute_select_one(query, (cpf_cliente,))
        
        total_acessorios_query = "SELECT COUNT(*) as total FROM Acessorio"
        total_acessorios = db.execute_select_one(total_acessorios_query)
        
        if (resultado and total_acessorios and 
            resultado['acessorios_utilizados'] == total_acessorios['total']):
            return 45.00  # R$ 45,00 fixo
        return 0.00
        
    except Exception as e:
        print(f"Erro ao calcular desconto todos acessórios: {e}")
        return 0.00

# =========================================================
# 4) REALIZAR DEVOLUÇÃO - ATUALIZADA COM MULTAS E DESCONTOS
# =========================================================
@aluguel_blueprint.route("/aluguel/devolver", methods=["POST"])
def devolver_carro():
    data = request.json or {}
    required = ["num_locacao", "estado_carro", "combustivel_completo"]
    missing = validate_fields(data, required)
    if missing:
        return jsonify({"erro": "Campos faltando", "campos": missing}), 400

    db = DatabaseManager()
    try:
        # 1) Buscar aluguel e verificar se não foi devolvido
        aluguel = db.execute_select_one("""
            SELECT a.*, c.tipo_categoria, cat.preco_diaria, c.placa, a.cpf_cliente
            FROM Aluguel a
            JOIN Carro c ON a.placa = c.placa
            JOIN Categoria cat ON c.tipo_categoria = cat.tipo
            WHERE a.num_locacao = %s 
            AND NOT EXISTS (
                SELECT 1 FROM Devolucao d WHERE d.num_locacao = a.num_locacao
            )
        """, (data["num_locacao"],))
        
        if not aluguel:
            return jsonify({"erro": "Aluguel não encontrado ou já devolvido"}), 404

        placa = aluguel["placa"]
        cpf_cliente = aluguel["cpf_cliente"]
        data_devolucao = date.today()

        # 2) Calcular valor base do aluguel
        data_prevista = aluguel["data_prevista_devolucao"]
        dias_locacao = max((data_devolucao - aluguel["data_retirada"]).days, 1)
        valor_base = float(aluguel["preco_diaria"]) * dias_locacao

        # 3) CALCULAR MULTAS
        multas = []
        valor_total_multas = 0.0

        # Multa por Atraso
        multa_atraso, dias_atraso = calcular_multa_atraso(db, data["num_locacao"], data_devolucao)
        if multa_atraso > 0:
            multas.append({
                "tipo": "ATRASO",
                "valor": multa_atraso,
                "referencia": f"{dias_atraso} dias",
                "codigo_motivo": "ATRASO"
            })
            valor_total_multas += multa_atraso

        # Multa por Tanque não cheio
        multa_tanque = calcular_multa_tanque(data["combustivel_completo"])
        if multa_tanque > 0:
            multas.append({
                "tipo": "TANQUE_NAO_CHEIO",
                "valor": multa_tanque,
                "referencia": None,
                "codigo_motivo": "TANQUE"
            })
            valor_total_multas += multa_tanque

        # Multa por Danos
        valor_danos = data.get("valor_danos", 0)
        multa_danos = calcular_multa_danos(valor_danos)
        if multa_danos > 0:
            multas.append({
                "tipo": "DANOS_VEICULO",
                "valor": multa_danos,
                "referencia": f"Valor danos: R$ {multa_danos}",
                "codigo_motivo": "DANO"
            })
            valor_total_multas += multa_danos

        # Multa por Quilometragem (se km_registro fornecido)
        km_registro = data.get("km_registro")
        if km_registro:
            multa_km, km_excedente = calcular_multa_km(db, data["num_locacao"], km_registro)
            if multa_km > 0:
                multas.append({
                    "tipo": "EXCESSO_QUILOMETRAGEM",
                    "valor": multa_km,
                    "referencia": f"{km_excedente} km excedentes",
                    "codigo_motivo": "KM_EXC"
                })
                valor_total_multas += multa_km

        # 4) CALCULAR DESCONTOS
        descontos = []
        valor_total_descontos = 0.0

        # Desconto Cliente Fiel
        desc_fiel = calcular_desconto_cliente_fiel(db, cpf_cliente)
        if desc_fiel > 0:
            descontos.append({
                "tipo": "CLIENTE_FIEL",
                "valor": desc_fiel,
                "codigo_desconto": "LOYALTY_50"
            })
            valor_total_descontos += desc_fiel

        # Desconto Reserva Antecipada
        desc_reserva = calcular_desconto_reserva_antecipada(db, data["num_locacao"])
        if desc_reserva > 0:
            descontos.append({
                "tipo": "RESERVA_ANTECIPADA",
                "valor": desc_reserva,
                "codigo_desconto": "EARLY_BOOKING"
            })
            valor_total_descontos += desc_reserva

        # Desconto Sem Multas
        desc_sem_multas = calcular_desconto_sem_multas(db, cpf_cliente, data["num_locacao"])
        if desc_sem_multas > 0:
            descontos.append({
                "tipo": "SEM_MULTAS",
                "valor": desc_sem_multas,
                "codigo_desconto": "NOFINE"
            })
            valor_total_descontos += desc_sem_multas

        # Desconto Todas Categorias
        desc_categorias = calcular_desconto_todas_categorias(db, cpf_cliente)
        if desc_categorias > 0:
            descontos.append({
                "tipo": "TODAS_CATEGORIAS",
                "valor": desc_categorias,
                "codigo_desconto": "ALLCATS"
            })
            valor_total_descontos += desc_categorias

        # Desconto Todos Acessórios
        desc_acessorios = calcular_desconto_todos_acessorios(db, cpf_cliente)
        if desc_acessorios > 0:
            descontos.append({
                "tipo": "TODOS_ACESSORIOS",
                "valor": desc_acessorios,
                "codigo_desconto": "ALLACC"
            })
            valor_total_descontos += desc_acessorios

        # 5) Calcular valor final
        valor_final = valor_base + valor_total_multas - valor_total_descontos
        valor_final = max(valor_final, 0)  # Não permitir valor negativo

        # 6) Criar Pagamento
        query_pag = "INSERT INTO Pagamento (valor_total, forma_pagamento) VALUES (%s, %s) RETURNING num_pagamento;"
        forma_pagamento = data.get("forma_pagamento", "Cartão Crédito")
        pag = db.execute_insert_returning(query_pag, (valor_final, forma_pagamento))
        num_pagamento_final = pag["num_pagamento"]

        # 7) Inserir Devolucao com dados adicionais
        query_dev = """
            INSERT INTO Devolucao 
            (num_locacao, num_pagamento, combustivel_completo, estado_carro, data_real_devolucao, km_registro, valor_danos)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        db.execute_statement(query_dev, (
            data["num_locacao"],
            num_pagamento_final,
            data["combustivel_completo"],
            data["estado_carro"],
            data_devolucao,
            km_registro,
            valor_danos
        ))

        # 8) Registrar Multas no banco
        for multa in multas:
            db.execute_statement(
                "INSERT INTO Multa (num_pagamento, tipo_multa, valor, codigo_motivo, referencia) VALUES (%s, %s, %s, %s, %s)",
                (num_pagamento_final, multa["tipo"], multa["valor"], multa["codigo_motivo"], multa["referencia"])
            )

        # 9) Registrar Descontos no banco
        for desconto in descontos:
            db.execute_statement(
                "INSERT INTO Desconto (num_pagamento, tipo_desconto, valor, codigo_desconto, flag_ativo) VALUES (%s, %s, %s, %s, %s)",
                (num_pagamento_final, desconto["tipo"], desconto["valor"], desconto["codigo_desconto"], True)
            )

        # 10) Atualizar status do carro baseado no estado
        estado = (data["estado_carro"] or "").upper()
        novo_status = "DISPONIVEL"
        novo_num_manut = None

        if any(tok in estado for tok in ("BATIDO", "AVARIA", "QUEBRADO", "AMASSADO", "COLISAO", "COLISÃO", "COLIDIDO", "DANIFICADO")) or multa_danos > 0:
            # Criar Manutencao
            query_ins_m = """
                INSERT INTO Manutencao (placa_carro, custo, data_inicio, descricao) 
                VALUES (%s, %s, %s, %s) 
                RETURNING num_manutencao;
            """
            descricao = f"Manutenção necessária: {estado}" if multa_danos == 0 else f"Manutenção por danos no valor de R$ {multa_danos}"
            m = db.execute_insert_returning(query_ins_m, (
                placa, 
                multa_danos,
                data_devolucao,
                descricao
            ))
            if m:
                novo_num_manut = m["num_manutencao"]
                novo_status = "MANUTENCAO"

        # Atualizar carro
        if novo_num_manut:
            db.execute_statement(
                "UPDATE Carro SET status_carro = %s, num_manutencao = %s WHERE placa = %s",
                (novo_status, novo_num_manut, placa)
            )
        else:
            db.execute_statement(
                "UPDATE Carro SET status_carro = %s WHERE placa = %s",
                (novo_status, placa)
            )

        # Commit final
        if hasattr(db, "conn") and db.conn:
            db.conn.commit()

        # 11) Preparar resposta detalhada
        response_data = {
            "mensagem": "Devolução realizada com sucesso!",
            "num_pagamento": num_pagamento_final,
            "resumo_financeiro": {
                "valor_base": valor_base,
                "total_multas": valor_total_multas,
                "total_descontos": valor_total_descontos,
                "valor_final": valor_final
            },
            "multas_aplicadas": multas,
            "descontos_aplicados": descontos,
            "detalhes": {
                "dias_locacao": dias_locacao,
                "data_devolucao": data_devolucao.isoformat(),
                "status_carro": novo_status
            }
        }
        
        if dias_atraso > 0:
            response_data["detalhes"]["dias_atraso"] = dias_atraso
            
        if novo_num_manut:
            response_data["num_manutencao"] = novo_num_manut
            response_data["observacao"] = "Carro enviado para manutenção."

        return jsonify(response_data), 200

    except Exception as e:
        try:
            if hasattr(db, "conn") and db.conn:
                db.conn.rollback()
        except:
            pass
        return internal_error(f"Erro na devolução: {str(e)}")

# =========================================================
# Endpoints Adicionais para Consulta de Multas e Descontos
# =========================================================

@aluguel_blueprint.route("/aluguel/<int:num_locacao>/multas", methods=["GET"])
def obter_multas_aluguel(num_locacao):
    """Retorna todas as multas aplicadas em um aluguel"""
    db = DatabaseManager()
    try:
        query = """
            SELECT m.*, p.valor_total as valor_pagamento
            FROM Multa m
            JOIN Pagamento p ON m.num_pagamento = p.num_pagamento
            JOIN Devolucao d ON d.num_pagamento = p.num_pagamento
            WHERE d.num_locacao = %s
        """
        multas = db.execute_select_all(query, (num_locacao,))
        return jsonify({"multas": multas}), 200
    except Exception as e:
        return internal_error(str(e))

@aluguel_blueprint.route("/aluguel/<int:num_locacao>/descontos", methods=["GET"])
def obter_descontos_aluguel(num_locacao):
    """Retorna todos os descontos aplicados em um aluguel"""
    db = DatabaseManager()
    try:
        query = """
            SELECT d.*, p.valor_total as valor_pagamento
            FROM Desconto d
            JOIN Pagamento p ON d.num_pagamento = p.num_pagamento
            JOIN Devolucao dev ON dev.num_pagamento = p.num_pagamento
            WHERE dev.num_locacao = %s
        """
        descontos = db.execute_select_all(query, (num_locacao,))
        return jsonify({"descontos": descontos}), 200
    except Exception as e:
        return internal_error(str(e))

@aluguel_blueprint.route("/clientes/<cpf>/historico-multas", methods=["GET"])
def historico_multas_cliente(cpf):
    """Retorna histórico de multas de um cliente"""
    db = DatabaseManager()
    try:
        query = """
            SELECT m.*, a.num_locacao, a.data_retirada, c.nome as nome_carro
            FROM Multa m
            JOIN Pagamento p ON m.num_pagamento = p.num_pagamento
            JOIN Devolucao d ON d.num_pagamento = p.num_pagamento
            JOIN Aluguel a ON a.num_locacao = d.num_locacao
            JOIN Carro c ON a.placa = c.placa
            WHERE a.cpf_cliente = %s
            ORDER BY a.data_retirada DESC
        """
        multas = db.execute_select_all(query, (cpf,))
        return jsonify({"multas": multas}), 200
    except Exception as e:
        return internal_error(str(e))