import re
import unicodedata
from pathlib import Path

import pandas as pd
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
            elif "devolu" in nome_low:
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
        repo = SqlitePMPVRepository()
        try:
            periodos_cons = {r["periodo"] for r in repo.listar_periodos()}
            periodos_pmpv = {r["periodo"] for r in repo.listar_pmpv_mensal()}
            return sorted(list(periodos_cons | periodos_pmpv), reverse=True)
        finally:
            repo.fechar()

    def buscar_pmpv(self, periodo: str):
        repo = SqlitePMPVRepository()
        try:
            return repo.buscar_pmpv_mensal(periodo)
        finally:
            repo.fechar()

    def salvar_cgf(self, periodo: str, valor: float):
        consolidacao = ServicosConsolidacao()
        try:
            dados = consolidacao.salvar_cgf(periodo, valor)
            return dados["rpv"]
        finally:
            consolidacao.fechar()