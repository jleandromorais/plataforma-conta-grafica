import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
from Src.Database.database import DatabasePMPV
from Src.common.periodos import is_periodo_valido
from Src.common.precisao import arredondar_tarifa
from Src.Services.servicos_consolidacao import ServicosConsolidacao
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

    def processar_arquivos(self, arquivos: list, fat_col: str, fat_cons_col: str, 
                           fat_cons_val: str, canc_col: str, dev_col: str) -> dict:
        """Lê os ficheiros selecionados, aplica as regras de negócio e gera os logs."""
        logs = []
        total_faturado = total_canceladas = total_devolucoes = total_consumo_proprio = 0.0

        for path in arquivos:
            nome = Path(path).name
            nome_low = nome.lower()
            
            try:
                df = self.ler_tabela(path)
            except Exception as e:
                logs.append(f"[ERRO] {e}\n")
                continue
                
            if df is None:
                continue

            # Processamento de Notas Faturadas ou Complementares
            if "faturada" in nome_low or "complementar" in nome_low:
                logs.append(f"🟢 FATURADA: {nome}")
                fat_col_real = self._resolver_coluna(df, fat_col, ["Volume Faturado", "Volume"])
                if fat_col_real is None:
                    logs.append(f"   [!] Coluna '{fat_col}' ausente. Ignorado.\n")
                    continue
                if fat_col_real != fat_col:
                    logs.append(f"   [i] Coluna de faturado localizada automaticamente: '{fat_col_real}'")
                    
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

            # Processamento de Canceladas / Denegadas
            elif "cancelad" in nome_low or "denegad" in nome_low:
                logs.append(f"🔴 CANCELADAS: {nome}")
                canc_col_real = self._resolver_coluna(df, canc_col, ["Volume Canc/Deneg", "Volume Canc Deneg", "Volume Canceladas", "Volume Denegadas", "Volume Cancelada"])
                if canc_col_real is None:
                    logs.append(f"   [!] Coluna de canceladas não encontrada a partir de '{canc_col}'.\n")
                else:
                    if canc_col_real != canc_col:
                        logs.append(f"   [i] Coluna de canceladas localizada automaticamente: '{canc_col_real}'")
                    df[canc_col_real] = self._converter_serie_numerica(df[canc_col_real])
                    vol_canc = df[canc_col_real].sum()
                    total_canceladas += float(vol_canc)
                    logs.append(f"   - Canceladas: {vol_canc:,.2f}\n")

            # Processamento de Devoluções
            # "devolv" cobre "NF Devolvidas …" — antes só "devolu" (Devolução)
            # era aceito e o arquivo de devolvidas era ignorado em silêncio.
            elif "devolu" in nome_low or "devolv" in nome_low:
                logs.append(f"🟡 DEVOLUÇÃO: {nome}")
                dev_col_real = self._resolver_coluna(df, dev_col, ["Volume Devolução", "Volume Devolucao", "Volume de Devolução", "Volume de Devolucao"])
                if dev_col_real is None:
                    logs.append(f"   [!] Coluna de devoluções não encontrada a partir de '{dev_col}'.\n")
                else:
                    if dev_col_real != dev_col:
                        logs.append(f"   [i] Coluna de devoluções localizada automaticamente: '{dev_col_real}'")
                    df[dev_col_real] = self._converter_serie_numerica(df[dev_col_real])
                    vol_dev = df[dev_col_real].sum()
                    total_devolucoes += float(vol_dev)
                    logs.append(f"   - Devoluções: {vol_dev:,.2f}\n")

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
            raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
        if pmpv and pmpv > 0:
            origem, valor = "manual", pmpv
        else:
            valor = self.buscar_pmpv(periodo) or 0.0
            origem = "banco" if valor > 0 else "ausente"
        valor = arredondar_tarifa(valor) if valor > 0 else 0.0
        cgf_rs = float(volume_final) * valor if valor > 0 else None
        return {"periodo": periodo, "pmpv": valor, "pmpv_origem": origem,
                "volume_final": float(volume_final), "cgf_rs": cgf_rs}

    def salvar_com_pmpv(self, periodo: str, resumo: dict, pmpv: float) -> dict:
        """Grava o CGF em R$ (volume final × PMPV) e o resumo de volumes.

        Exige PMPV > 0: sem ele o desktop gravava o VOLUME (m³) no campo do
        CGF em R$, e esse número entrava no RPV/SCG como se fosse dinheiro.
        """
        if not is_periodo_valido(periodo):
            raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
        if not pmpv or pmpv <= 0:
            raise ValueError(f"Sem PMPV para {periodo}: calcule e salve o PMPV antes de salvar o CGF.")
        volume_final = float(resumo.get("volume_final") or 0.0)
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
        anos = re.findall(r'\b(20\d{2})\b', caminho)
        ano = int(anos[-1]) if anos else date.today().year
        return f"{_ABREVS[mes_num - 1]}/{ano}"


_MESES_DETECT = {
    "JANEIRO": 1, "JAN": 1, "FEVEREIRO": 2, "FEV": 2, "MARÇO": 3, "MARCO": 3, "MAR": 3,
    "ABRIL": 4, "ABR": 4, "MAIO": 5, "MAI": 5, "JUNHO": 6, "JUN": 6,
    "JULHO": 7, "JUL": 7, "AGOSTO": 8, "AGO": 8, "SETEMBRO": 9, "SET": 9,
    "OUTUBRO": 10, "OUT": 10, "NOVEMBRO": 11, "NOV": 11, "DEZEMBRO": 12, "DEZ": 12,
}
_ABREVS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]