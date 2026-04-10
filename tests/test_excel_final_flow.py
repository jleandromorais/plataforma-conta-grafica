from pathlib import Path

from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters import excel_consolidado


def test_registrar_execucao_excel_final_incrementa(tmp_path):
    db_path = tmp_path / "flow.db"
    db = DatabasePMPV(db_path=str(db_path))
    try:
        db.salvar_sessao_excel_final("SessaoFlow", str(tmp_path / "final.xlsx"), ativo=True)

        exec_1 = db.registrar_execucao_excel_final(
            nome_sessao="SessaoFlow",
            periodo="Dez/2025",
            etapa="RET",
            caminho_arquivo=str(tmp_path / "final.xlsx"),
        )
        exec_2 = db.registrar_execucao_excel_final(
            nome_sessao="SessaoFlow",
            periodo="Dez/2025",
            etapa="RET",
            caminho_arquivo=str(tmp_path / "final.xlsx"),
        )

        assert exec_1 == 1
        assert exec_2 == 2

        rows = db.listar_execucoes_excel_final(nome_sessao="SessaoFlow", periodo="Dez/2025")
        assert len(rows) == 1
        assert rows[0]["execucao"] == 2
        assert rows[0]["etapa"] == "RET"
    finally:
        db.fechar()


def test_exportar_excel_final_por_periodo_gera_arquivo(tmp_path, monkeypatch):
    db_path = tmp_path / "flow_export.db"
    db = DatabasePMPV(db_path=str(db_path))
    try:
        db.criar_periodo_consolidacao("Dez/2025")
        db.atualizar_campos_consolidacao(
            "Dez/2025",
            cgr=100.0,
            cgf=20.0,
            rpv=80.0,
            ret=10.0,
            rp=5.0,
            scg=95.0,
        )
        db.salvar_ret_itens("Dez/2025", [
            {
                "arquivo": "ret_doc_1.pdf",
                "tipo_encargo": "EAT",
                "empresa": "COPERGAS",
                "nota_tipo": "ND",
                "numero_nd": "123",
                "data_vencimento": "2025-12-10",
                "valor_total": 10.0,
                "moeda_detectada": "BRL",
                "contrib_ec": "SIM",
            }
        ])
    finally:
        db.fechar()

    monkeypatch.setattr(excel_consolidado, "DatabasePMPV", lambda: DatabasePMPV(db_path=str(db_path)))
    monkeypatch.setattr(excel_consolidado.os, "startfile", lambda *_args, **_kwargs: None, raising=False)

    arquivo_saida = tmp_path / "modulo9.xlsx"
    gerado = excel_consolidado.ExcelConsolidado.exportar(periodo="Dez/2025", nome_arquivo=str(arquivo_saida))

    assert Path(gerado).exists()
    assert Path(gerado).name == "modulo9.xlsx"


def test_excel_final_destino_nao_usa_simpledialog_para_escolha():
    file_path = Path(__file__).resolve().parents[1] / "Src" / "common" / "excel_final_destino.py"
    conteudo = file_path.read_text(encoding="utf-8")

    assert "simpledialog.askstring" not in conteudo
    assert "simpledialog.askinteger" not in conteudo
