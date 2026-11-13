import re
import unicodedata
from pathlib import Path

import pandas as pd
from Src.Database.database import DatabasePMPV
from Src.common.periodos import ano_do_caminho, is_periodo_valido
from Src.common.precisao import arredondar_tarifa, arredondar_volume

TOL_PROVA_REAL_RS = 1.0   # R$: abaixo disso é arredondamento
TOL_VOLUME_M3 = 0.01      # m³: o volume final é gravado com 2 casas
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository

class ServicosCGF:
    """Especialista no processamento de planilhas (Excel/CSV) e cálculos do CGF."""

    @staticmethod
    def _normalizar_texto(valor: str) -> str:
        texto = "" if valor is None else str(valor).strip().lower()
        texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
        texto = re.sub(r"[^a-z0-9]+", " ", texto)
        return " ".join(texto.split())

    @staticmethod
    def _converter_serie_numerica(serie: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(serie):
            return pd.to_numeric(serie, errors="coerce")

        texto = serie.astype(str).str.strip()
        texto = texto.str.replace(r"[^0-9,.-]", "", regex=True)

        mascara_br = texto.str.contains(",", na=False) & texto.str.contains(r"\.", na=False)
        texto.loc[mascara_br] = texto.loc[mascara_br].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)

        mascara_virgula = texto.str.contains(",", na=False) & ~texto.str.contains(r"\.", na=False)
        texto.loc[mascara_virgula] = texto.loc[mascara_virgula].str.replace(",", ".", regex=False)

        return pd.to_numeric(texto, errors="coerce")

    @classmethod
    def _resolver_coluna(cls, df: pd.DataFrame, col_configurada: str, aliases: list[str]) -> str | None:
        if df is None or df.empty:
            return None

        mapa_colunas = {cls._normalizar_texto(col): col for col in df.columns}
        candidatos = [col_configurada, *aliases]

        for candidato in candidatos:
            chave = cls._normalizar_texto(candidato)
            if chave in mapa_colunas:
                return mapa_colunas[chave]

        for candidato in candidatos:
            chave = cls._normalizar_texto(candidato)
            if not chave:
                continue
            for col_norm, col_real in mapa_colunas.items():
                if chave in col_norm or col_norm in chave:
                    return col_real

        return None

    @staticmethod
    def ler_tabela(path: str):
        try:
            ext = Path(path).suffix.lower()
            if ext in [".xlsx", ".xls"]:
                return pd.read_excel(path)
            elif ext == ".csv":
                return pd.read_csv(path, sep=";", engine="python")
            return None
        except Exception as e:
            raise Exception(f"Erro ao ler {path}: {e}")

    @staticmethod
    def mascara_consumo(df: pd.DataFrame, col_configurada: str, val_configurado: str) -> pd.Series:
        """Cria uma máscara Booleana (True/False) identificando as linhas de consumo próprio."""
        mask = pd.Series([False] * len(df), index=df.index)

        termos = [
            "consumo",
            "proprio",
            "consumo proprio",
            "cons proprio",
            "cons prop",
            "uso consumo",
        ]

        if col_configurada and col_configurada in df.columns and val_configurado:
            serie = df[col_configurada].map(ServicosCGF._normalizar_texto)
            valor_norm = ServicosCGF._normalizar_texto(val_configurado)
            mask |= (serie == valor_norm)
            if valor_norm:
                mask |= serie.str.contains(valor_norm, na=False, regex=False)

        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                serie_col = df[col].map(ServicosCGF._normalizar_texto)
                for termo in termos:
                    mask |= serie_col.str.contains(termo, na=False, regex=False)
        return mask

    # Palavras do NOME do arquivo que dizem o tipo da planilha. A tela web repete
    # esta regra em Front_end/src/pages/CGF/index.tsx (tipoDoArquivo): mantenha iguais.
    # Ordem importa: faturada/complementar é testada antes de cancelada.
    PALAVRAS_FATURADA = ("faturada", "complementar")
    PALAVRAS_CANCELADA = ("canc", "deneg", "rejeitad")   # cobre "NF canc.rejeitadas.deneg"
    PALAVRAS_DEVOLUCAO = ("devolu", "devolv")             # "devolv" cobre "NF Devolvidas …"

    @classmethod
    def tipo_do_nome(cls, nome: str) -> str | None:
        """'faturada' | 'cancelada' | 'devolucao' pelo nome do arquivo, ou None."""
        n = nome.lower()
        if any(p in n for p in cls.PALAVRAS_FATURADA):
            return "faturada"
        if any(p in n for p in cls.PALAVRAS_CANCELADA):
            return "cancelada"
        if any(p in n for p in cls.PALAVRAS_DEVOLUCAO):
            return "devolucao"
        return None

    @staticmethod
    def _problema(arquivo: str, gravidade: str, codigo: str, mensagem: str, tecnico: str | None = None) -> dict:
        return {"arquivo": arquivo, "gravidade": gravidade, "codigo": codigo, "mensagem": mensagem, "tecnico": tecnico}

    def processar_arquivos(self, arquivos: list, fat_col: str, fat_cons_col: str,
                           fat_cons_val: str, canc_col: str, dev_col: str) -> dict:
        """Lê os ficheiros selecionados, aplica as regras de negócio e gera os logs.

        Além dos logs, devolve `problemas`: o que impediu ou afetou a leitura de
        cada arquivo, em texto para o usuário (ver Front_end/SPEC_ERROS.md).
        """
        logs = []
        problemas: list[dict] = []
        total_faturado = total_canceladas = total_devolucoes = total_consumo_proprio = 0.0
        tipos_enviados: set[str] = set()
        rotulo_total = {"faturada": "O faturado", "cancelada": "O total de canceladas", "devolucao": "O total de devoluções"}
        rotulo_tipo = {"faturada": "faturadas", "cancelada": "canceladas", "devolucao": "devoluções"}

        def coluna(df, nome, tipo, configurada, aliases):
            """Coluna real da planilha; registra o problema quando não acha ou usa um apelido."""
            real = self._resolver_coluna(df, configurada, aliases)
            if real is None:
                logs.append(f"   [!] Coluna '{configurada}' ausente. Ignorado.\n")
                problemas.append(self._problema(
                    nome, "erro", "coluna_ausente",
                    f"Não achei a coluna \"{configurada}\" na planilha de {rotulo_tipo[tipo]}. "
                    f"{rotulo_total[tipo]} deste arquivo ficou em 0. Confira o nome em \"Colunas das planilhas\".",
                    "colunas encontradas: " + ", ".join(str(c) for c in df.columns),
                ))
            elif self._normalizar_texto(real) != self._normalizar_texto(configurada):
                logs.append(f"   [i] Coluna localizada automaticamente: '{real}'")
                problemas.append(self._problema(
                    nome, "info", "coluna_por_apelido", f"Usei a coluna \"{real}\" no lugar de \"{configurada}\".",
                ))
            return real

        for path in arquivos:
            nome = Path(path).name
            tipo = self.tipo_do_nome(nome)

            if tipo is None:
                problemas.append(self._problema(
                    nome, "erro", "tipo_nao_reconhecido",
                    "Não sei se é faturada, cancelada ou devolução: o nome precisa conter faturada, complementar, "
                    "cancelada, denegada, rejeitada, devolução ou devolvida. O arquivo ficou de fora, então o "
                    "volume final pode estar incompleto. Renomeie e envie de novo.",
                ))
                continue
            tipos_enviados.add(tipo)

            try:
                df = self.ler_tabela(path)
            except Exception as e:
                causa = type(e.__cause__ or e.__context__ or e).__name__
                logs.append(f"[ERRO] Não foi possível ler {nome}: {causa}\n")
                problemas.append(self._problema(
                    nome, "erro", "planilha_ilegivel",
                    "Não consegui abrir a planilha. Ela pode estar corrompida, protegida por senha ou aberta em "
                    "outro programa. Salve de novo no Excel (.xlsx) e envie.",
                    causa,
                ))
                continue

            if df is None:
                continue
            if df.empty:
                logs.append(f"   [!] {nome}: planilha vazia.\n")
                problemas.append(self._problema(nome, "aviso", "planilha_vazia", "A planilha está vazia; nada foi somado."))
                continue

            # Processamento de Notas Faturadas ou Complementares
            if tipo == "faturada":
                logs.append(f"🟢 FATURADA: {nome}")
                fat_col_real = coluna(df, nome, tipo, fat_col, ["Volume Faturado", "Volume"])
                if fat_col_real is None:
                    continue

                mask_cons = self.mascara_consumo(df, fat_cons_col, fat_cons_val)
                qtd_cons = mask_cons.sum()

                df_cons = df[mask_cons].copy()
                df_sem_cons = df[~mask_cons].copy()

                df_sem_cons[fat_col_real] = self._converter_serie_numerica(df_sem_cons[fat_col_real])
                df_cons[fat_col_real] = self._converter_serie_numerica(df_cons[fat_col_real])

                vol_fat  = df_sem_cons[fat_col_real].sum()
                vol_cons = df_cons[fat_col_real].sum()

                total_faturado += float(vol_fat)
                total_consumo_proprio += float(vol_cons)

                logs.append(f"   + Faturado limpo:   {vol_fat:,.2f}")
                if qtd_cons > 0:
                    logs.append(f"   - Consumo próprio:  {vol_cons:,.2f}  ({qtd_cons} linha(s) detectada(s))\n")
                else:
                    logs.append(f"   (nenhum consumo próprio detectado)\n")
                    problemas.append(self._problema(
                        nome, "info", "consumo_nao_encontrado",
                        f"Nenhuma linha \"{fat_cons_val}\" na coluna \"{fat_cons_col}\": consumo próprio = 0.",
                    ))

            # Processamento de Canceladas / Denegadas
            elif tipo == "cancelada":
                logs.append(f"🔴 CANCELADAS: {nome}")
                canc_col_real = coluna(df, nome, tipo, canc_col, ["Volume Canc/Deneg", "Volume Canc Deneg", "Volume Canceladas", "Volume Denegadas", "Volume Cancelada"])
                if canc_col_real is not None:
                    df[canc_col_real] = self._converter_serie_numerica(df[canc_col_real])
                    vol_canc = df[canc_col_real].sum()
                    total_canceladas += float(vol_canc)
                    logs.append(f"   - Canceladas: {vol_canc:,.2f}\n")

            # Processamento de Devoluções
            else:
                logs.append(f"🟡 DEVOLUÇÃO: {nome}")
                dev_col_real = coluna(df, nome, tipo, dev_col, ["Volume Devolução", "Volume Devolucao", "Volume de Devolução", "Volume de Devolucao"])
                if dev_col_real is not None:
                    df[dev_col_real] = self._converter_serie_numerica(df[dev_col_real])
                    vol_dev = df[dev_col_real].sum()
                    total_devolucoes += float(vol_dev)
                    logs.append(f"   - Devoluções: {vol_dev:,.2f}\n")

        if "faturada" not in tipos_enviados:
            problemas.append(self._problema(
                "", "erro", "sem_faturadas",
                "Nenhuma planilha de faturadas foi enviada: o volume final ficaria só com devoluções. "
                "Envie a planilha \"NF faturadas e complementares\".",
            ))
        for tipo in ("cancelada", "devolucao"):
            if tipo not in tipos_enviados:
                problemas.append(self._problema(
                    "", "aviso", "tipo_ausente",
                    f"Nenhuma planilha de {rotulo_tipo[tipo]} enviada: esse total ficou em 0. "
                    f"Se o mês não teve {rotulo_tipo[tipo]}, pode seguir.",
                ))

        # Cálculo Final CGF — canceladas não integram o VF (apenas devoluções e consumo próprio)
        volume_final = total_faturado - total_devolucoes

        # Montar Log de Resumo
        logs.append("-" * 40)
        logs.append("📊 RESUMO GERAL:")
        logs.append(f" (+) Faturado (s/ cons. próprio): {total_faturado:,.4f}")
        if total_consumo_proprio:
            logs.append(f"   ↳ Consumo Próprio excluído:   {total_consumo_proprio:,.4f}  (já retirado do faturado acima)")
        logs.append(f" (-) Canceladas:                  {total_canceladas:,.4f}")
        logs.append(f" (-) Devoluções:                  {total_devolucoes:,.4f}")
        logs.append(f"\n  => VOLUME FINAL CGF (VF):       {volume_final:,.4f}")

        return {
            "logs": logs,
            "problemas": problemas,
            "volume_final": volume_final,
            "volume_faturado": total_faturado,
            "volume_canceladas": total_canceladas,
            "volume_devolucoes": total_devolucoes,
            "volume_consumo_proprio": total_consumo_proprio,
        }

    # Interações com Banco de Dados
    def obter_periodos(self):
        with SqlitePMPVRepository() as repo:
            periodos_cons = {r["periodo"] for r in repo.listar_periodos()}
            periodos_pmpv = {r["periodo"] for r in repo.listar_pmpv_mensal()}
            return sorted(list(periodos_cons | periodos_pmpv), reverse=True)

    def buscar_pmpv(self, periodo: str):
        with SqlitePMPVRepository() as repo:
            return repo.buscar_pmpv_mensal(periodo)

    def salvar_cgf(self, periodo: str, valor: float):
        with ServicosConsolidacao() as consolidacao:
            dados = consolidacao.salvar_cgf(periodo, valor)
            return dados["rpv"]

    def calcular_cgf_rs(self, periodo: str, volume_final: float, pmpv: float | None = None) -> dict:
        """CGF em R$ = volume final × PMPV, sem gravar nada.

        `pmpv` informado (>0) é usado como digitado; ausente, busca o PMPV
        salvo do mês. Sem PMPV, devolve cgf_rs=None em vez de falhar: a tela
        mostra "—" e pede o valor.
        """
        if not is_periodo_valido(periodo):
            raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
        if pmpv and pmpv > 0:
            origem, valor = "manual", pmpv
        else:
            valor = self.buscar_pmpv(periodo) or 0.0
            origem = "banco" if valor > 0 else "ausente"
        valor = arredondar_tarifa(valor) if valor > 0 else 0.0
        volume_final = arredondar_volume(volume_final)
        cgf_rs = volume_final * valor if valor > 0 else None
        return {"periodo": periodo, "pmpv": valor, "pmpv_origem": origem,
                "volume_final": volume_final, "cgf_rs": cgf_rs}

    def salvar_com_pmpv(self, periodo: str, resumo: dict, pmpv: float) -> dict:
        """Grava o CGF em R$ (volume final × PMPV) e o resumo de volumes.

        Exige PMPV > 0: sem ele o desktop gravava o VOLUME (m³) no campo do
        CGF em R$, e esse número entrava no RPV/SCG como se fosse dinheiro.
        """
        if not is_periodo_valido(periodo):
            raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
        if not pmpv or pmpv <= 0:
            raise ValueError(f"Sem PMPV para {periodo}: calcule e salve o PMPV antes de salvar o CGF.")
        volume_final = arredondar_volume(resumo.get("volume_final"))
        if volume_final == 0.0:
            raise ValueError("Volume final zerado: processe as planilhas de NF antes de salvar.")
        # PMPV com 4 casas, como a tela desktop (e o histórico gravado) usa.
        pmpv = arredondar_tarifa(pmpv)
        cgf_rs = volume_final * pmpv
        rpv = self.salvar_cgf(periodo, cgf_rs)
        with DatabasePMPV() as db:
            db.salvar_cgf_resumo(
                periodo,
                resumo.get("volume_faturado", 0.0),
                resumo.get("volume_canceladas", 0.0),
                resumo.get("volume_devolucoes", 0.0),
                resumo.get("volume_consumo_proprio", 0.0),
                volume_final,
            )
        return {"cgf_rs": cgf_rs, "rpv": rpv}

    def prova_real(self, periodo: str) -> dict:
        """A conta do CGF gravado do mês, aberta: faturado − devoluções = volume final, e
        volume final × PMPV = CGF em R$, comparados com o que está gravado. Não grava nada.

        Usa só o que o banco guarda (resumo de volumes, PMPV do mês e CGF da consolidação),
        com os mesmos arredondamentos de `salvar_com_pmpv` (volume 2 casas, PMPV 4 casas).
        """
        if not is_periodo_valido(periodo):
            raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
        with DatabasePMPV() as db:
            resumo = db.buscar_cgf_resumo(periodo) or {}
            cons = db.buscar_consolidacao(periodo) or {}
            pmpv_banco = db.buscar_pmpv_mensal(periodo)

        tem_resumo = bool(resumo)
        faturado = float(resumo.get("volume_faturado") or 0.0)
        devolucoes = float(resumo.get("volume_devolucoes") or 0.0)
        vf_gravado = float(resumo.get("volume_final") or 0.0)
        vf_calculado = arredondar_volume(faturado - devolucoes)
        pmpv = arredondar_tarifa(pmpv_banco) if pmpv_banco else None
        cgf_gravado = float(cons["cgf"]) if cons.get("cgf") is not None else None
        # Sem o resumo de volumes (mês gravado só com o total) não há o que multiplicar: não dá para provar.
        cgf_calculado = vf_calculado * pmpv if pmpv and tem_resumo else None
        dif_volume = vf_calculado - vf_gravado
        dif_cgf = cgf_calculado - cgf_gravado if cgf_calculado is not None and cgf_gravado is not None else None
        volume_confere = tem_resumo and abs(dif_volume) <= TOL_VOLUME_M3
        cgf_confere = dif_cgf is not None and abs(dif_cgf) <= TOL_PROVA_REAL_RS
        return {
            "periodo": periodo,
            "tem_resumo": tem_resumo,
            "volume_faturado": faturado,
            "volume_canceladas": float(resumo.get("volume_canceladas") or 0.0),
            "volume_devolucoes": devolucoes,
            "volume_consumo_proprio": float(resumo.get("volume_consumo_proprio") or 0.0),
            "volume_final_calculado": vf_calculado,
            "volume_final_gravado": vf_gravado if tem_resumo else None,
            "diferenca_volume": dif_volume if tem_resumo else None,
            "volume_confere": volume_confere,
            "pmpv": pmpv,
            "cgf_calculado": cgf_calculado,
            "cgf_gravado": cgf_gravado,
            "diferenca_cgf": dif_cgf,
            "cgf_confere": cgf_confere,
            "confere": volume_confere and cgf_confere,
            "data_atualizacao": (resumo.get("data_atualizacao") or "")[:16],
        }

    def historico(self) -> list[dict]:
        """Resumo de volumes gravado por período + CGF em R$ da consolidação."""
        with DatabasePMPV() as db:
            resumos = db.listar_cgf_resumos()
            linhas = []
            for r in resumos:
                cons = db.buscar_consolidacao(r["periodo"]) or {}
                linhas.append({
                    "periodo": r["periodo"],
                    "volume_faturado": r.get("volume_faturado") or 0.0,
                    "volume_canceladas": r.get("volume_canceladas") or 0.0,
                    "volume_devolucoes": r.get("volume_devolucoes") or 0.0,
                    "volume_consumo_proprio": r.get("volume_consumo_proprio") or 0.0,
                    "volume_final": r.get("volume_final") or 0.0,
                    "cgf_rs": cons.get("cgf") or 0.0,
                    "data_atualizacao": (r.get("data_atualizacao") or "")[:16],
                })
        from Src.common.periodos import ordenar_historico
        return ordenar_historico(linhas)

    @staticmethod
    def periodo_do_nome_arquivo(caminho: str) -> str:
        """Extrai 'Jan/2026' do nome do arquivo ou da pasta (ex.: 'NF Faturadas
        01.26.xlsx' não tem mês por extenso → ''; 'Janeiro 2026/NF...' → 'Jan/2026')."""
        tokens = re.split(r'[\s\-_\./\\]+', Path(caminho).stem.upper())
        tokens += re.split(r'[\s\-_\./\\]+', Path(caminho).parent.name.upper())
        mes_num = 0
        for tok in reversed(tokens):
            if tok in _MESES_DETECT:
                mes_num = _MESES_DETECT[tok]
                break
        if not mes_num:
            # Padrão "MM.AA" / "MM-AAAA" usado nos nomes das planilhas de NF
            # (ex.: "NF Faturadas e complementares 01.26.xlsx" → Jan/2026).
            m = re.search(r'(?<!\d)(0[1-9]|1[0-2])[.\-_/](\d{2}|20\d{2})(?!\d)', Path(caminho).stem)
            if not m:
                return ""
            ano = int(m.group(2)) if len(m.group(2)) == 4 else 2000 + int(m.group(2))
            return f"{_ABREVS[int(m.group(1)) - 1]}/{ano}"
        ano = ano_do_caminho(caminho)
        return f"{_ABREVS[mes_num - 1]}/{ano}" if ano else ""


_MESES_DETECT = {
    "JANEIRO": 1, "JAN": 1, "FEVEREIRO": 2, "FEV": 2, "MARÇO": 3, "MARCO": 3, "MAR": 3,
    "ABRIL": 4, "ABR": 4, "MAIO": 5, "MAI": 5, "JUNHO": 6, "JUN": 6,
    "JULHO": 7, "JUL": 7, "AGOSTO": 8, "AGO": 8, "SETEMBRO": 9, "SET": 9,
    "OUTUBRO": 10, "OUT": 10, "NOVEMBRO": 11, "NOV": 11, "DEZEMBRO": 12, "DEZ": 12,
}
_ABREVS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]