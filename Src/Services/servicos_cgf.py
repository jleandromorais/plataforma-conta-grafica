import pandas as pd
from pathlib import Path
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository

class ServicosCGF:
    """Especialista no processamento de planilhas (Excel/CSV) e cálculos do CGF."""

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

        if col_configurada and col_configurada in df.columns and val_configurado:
            serie = df[col_configurada].astype(str).str.upper().str.strip()
            mask |= (serie == val_configurado.upper())

        TERMOS = ["consumo", "proprio", "próprio", "consumo proprio", "consumo próprio", "cons. proprio", "cons proprio"]
        for col in df.columns:
            if df[col].dtype == object or str(df[col].dtype) == "string":
                serie_col = df[col].astype(str).str.lower().str.strip()
                for termo in TERMOS:
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
                if fat_col not in df.columns:
                    logs.append(f"   [!] Coluna '{fat_col}' ausente. Ignorado.\n")
                    continue
                    
                mask_cons = self.mascara_consumo(df, fat_cons_col, fat_cons_val)
                qtd_cons = mask_cons.sum()

                df_cons = df[mask_cons].copy()
                df_sem_cons = df[~mask_cons].copy()

                df_sem_cons[fat_col] = pd.to_numeric(df_sem_cons[fat_col], errors="coerce")
                df_cons[fat_col]     = pd.to_numeric(df_cons[fat_col],     errors="coerce")

                vol_fat  = df_sem_cons[fat_col].sum()
                vol_cons = df_cons[fat_col].sum()
                
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
                if canc_col in df.columns:
                    df[canc_col] = pd.to_numeric(df[canc_col], errors="coerce")
                    vol_canc = df[canc_col].sum()
                    total_canceladas += float(vol_canc)
                    logs.append(f"   - Canceladas: {vol_canc:,.2f}\n")

            # Processamento de Devoluções
            elif "devolu" in nome_low:
                logs.append(f"🟡 DEVOLUÇÃO: {nome}")
                if dev_col in df.columns:
                    df[dev_col] = pd.to_numeric(df[dev_col], errors="coerce")
                    vol_dev = df[dev_col].sum()
                    total_devolucoes += float(vol_dev)
                    logs.append(f"   - Devoluções: {vol_dev:,.2f}\n")

        # Cálculo Final CGF
        volume_final = total_faturado - total_canceladas - total_devolucoes

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