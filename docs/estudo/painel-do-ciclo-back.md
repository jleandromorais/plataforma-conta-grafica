# Painel do Ciclo comentado — back-end

**Data:** 06/11/2026

> **Nota:** os números de linha citados aqui valem para o código de hoje. Quando alguém mexer nos arquivos, eles podem mudar. Se uma linha não bater, procure pelo nome da função.

> **Valores:** todos os números deste estudo são fictícios (R$ 1.000,00, 100 m³...). Nada aqui vem do banco nem das planilhas da empresa.

> **Escopo:** este arquivo comenta só a parte do back-end que o Painel do Ciclo usa. O resto do servidor fica para outros estudos.

---

## Para que serve o back-end do Painel

O Painel do Ciclo mostra, para um trimestre, o que já foi feito em cada etapa: Auditoria (CGR), CGF, RET, Conciliação (RP), SCG, SR, PR e PV. Ele também gera a minuta da Nota Técnica. O botão **Processar** lê a pasta do mês e grava as etapas de uma vez.

O site não faz conta nem guarda nada. Ele só **pede**. Quem confere, calcula e arquiva é o back-end. Pense numa repartição:

- a **API** (FastAPI) é o *guichê* que recebe os pedidos;
- cada **router** é um *balcão por assunto* (CGF, RET, SCG...);
- o **schema** é o *formulário padrão* do pedido e da resposta;
- o **Service** é o *contador*, que faz a conta de verdade;
- o **banco SQLite** (`pmpv_data.db`) é o *arquivo-morto*;
- o **teste** é a *prova real*, que confere a conta sozinho.

O Painel faz dois tipos de pedido:

1. **Ao abrir:** só leitura. São os históricos de Auditoria, CGF, RET, Conciliação e SCG, mais PR, PV e SR do trimestre. Com isso a tela marca cada etapa como "feita" ou "falta".
2. **No Processar:** para cada etapa, primeiro *processar* (calcula sem gravar) e depois *salvar* (grava). Na Auditoria, entre os dois, ele pede as *diferenças* em relação ao que já está gravado. No CGF, ele busca o *PMPV do mês* e pede a *prévia em reais* antes de salvar.

### O caminho de um pedido

Exemplo: no Processar, o Painel salva o CGF de Mar/2026.

```
 Site (Painel do Ciclo)
   |  POST /api/cgf/salvar   + crachá (JWT)   + JSON com volumes, período e PMPV
   v
 Src/api/main.py ............ guichê: confere o crachá (_protegido) e manda ao balcão certo
   v
 Src/api/routers/cgf.py ..... balcão do CGF: função salvar()
   v
 Src/api/schemas/cgf.py ..... formulário: CGFSalvarRequest confere os campos
   v
 Src/Services/cgf/servicos_cgf.py contador: salvar_com_pmpv() faz volume x PMPV
   v
 Src/Database/database.py ... arquivo-morto: grava em "consolidacao" e "cgf_resumo"
   ^
   |  a resposta volta pelo mesmo caminho, em JSON: {"cgf_rs": ..., "rpv": ...}
```

**JSON** é o jeito de escrever dados em texto que o site e o servidor entendem, por exemplo `{"periodo": "Mar/2026", "pmpv": 2.5}`.

---

## 1. `Src/api/main.py` — a porta de entrada

### Criação do app — linhas 20–24

```python
app = FastAPI(                                   # cria o guichê (o "app")
    title="Plataforma Conta Gráfica — API",
    description="Backend FastAPI sobre Src/Services (fonte única dos cálculos).",
    version="0.1.0",
)
```

**Para quê:** aqui nasce a API. Todo pedido do Painel chega a este `app`.
**Como:** `FastAPI` é uma **classe**. Uma *classe* é um molde, como o modelo de um formulário em branco. `FastAPI(...)` preenche o molde e cria o objeto `app`.

### CORS — linhas 26–36 (resumo)

```python
_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,...").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_origins, ...)   # só esses sites podem chamar
```

**Para quê:** o navegador só deixa o site do Painel chamar a API se a API disser "esse site pode". O CORS é essa lista de convidados na portaria.

### Tradutor de erros — linha 38

```python
registrar_exception_handlers(app)   # transforma erros em mensagens legíveis (seção 3)
```

### Login obrigatório e os balcões do Ciclo — linhas 40–57

```python
# Tudo exige login, exceto /api/auth/* e /api/health.
_protegido = [Depends(usuario_atual)]                       # "antes de atender, confira o crachá"
app.include_router(pmpv.router, prefix="/api", dependencies=_protegido)       # PMPV do mês (44)
app.include_router(scg.router, prefix="/api", dependencies=_protegido)        # 45
app.include_router(pr.router, prefix="/api", dependencies=_protegido)         # 46
app.include_router(pv.router, prefix="/api", dependencies=_protegido)         # 47
app.include_router(sr.router, prefix="/api", dependencies=_protegido)         # 49
app.include_router(cgf.router, prefix="/api", dependencies=_protegido)        # 52
app.include_router(auditoria.router, prefix="/api", dependencies=_protegido)  # 53
# ... ret (54), conciliacao (55), nota_tecnica (57)
```

**Para quê:** cada balcão que o Painel usa é pendurado no guichê com endereço começando por `/api`, e todos exigem crachá. As linhas que ficaram de fora acima penduram balcões que o Painel não usa.
**Como:**
- **`Depends`** é o jeito do FastAPI dizer "antes de rodar isto, rode aquilo". Isso se chama **dependência**. Aqui, a dependência é `usuario_atual`, que confere o crachá.
- `include_router` pendura o balcão.
- `prefix="/api"` junta `/api` na frente. Assim `/cgf/salvar` vira `/api/cgf/salvar`.

---

## 2. `Src/api/auth.py` — o crachá (`usuario_atual`, linhas 129–146)

```python
def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    # ... erro(motivo) monta a resposta 401 (linhas 130–131)
    if cred is None:
        raise erro("Você não está conectado. Entre com seu e-mail e senha.")
    try:
        dados = jwt.decode(cred.credentials, _segredo(), algorithms=["HS256"])  # confere a assinatura
        uid = int(dados["sub"])                                                  # número do usuário
    except jwt.ExpiredSignatureError:
        raise erro("Sua sessão expirou (...). Entre novamente.")
    # ... outros crachás inválidos (140–141)
    with _conn() as c:
        row = c.execute("SELECT id, nome, email FROM usuarios WHERE id=?", (uid,)).fetchone()
    # ... não achou: 401 (144–145); achou: return dict(row)
```

**Para quê:** é o segurança da porta. Cada pedido do Painel (são vários ao abrir a tela) passa por aqui primeiro. Sem crachá válido, o pedido para com **401** ("não autorizado"), e o Painel manda o analista entrar de novo.
**Como:** o crachá é um **JWT**, um texto assinado com um segredo que só o servidor conhece. `jwt.decode` confere a assinatura e a validade. Depois o servidor procura o usuário no banco.

Termos novos neste bloco:
- **Função (`def`):** uma receita com nome. Recebe ingredientes, faz algo e devolve um resultado.
- **Type hints:** dicas de tipo. Em `cred: ... | None`, o parâmetro é "um crachá ou nada". Em `-> dict`, a função devolve um dicionário, que é uma lista de pares "nome: valor".
- **Exceção / `raise`:** uma *exceção* é um alarme que interrompe o trabalho. `raise` toca o alarme.
- **`try` / `except`:** "tente isto; se tocar o alarme X, faça aquilo".
- **`with`:** abre um recurso (aqui, o banco) e garante que ele seja fechado no fim, mesmo com erro. É como uma gaveta que fecha sozinha quando você sai da sala.

---

## 3. `Src/api/errors.py` — como `ValueError` vira 422

### A resposta padrão — linhas 22–26

```python
def _resposta(status: int, detail: str, codigo: str | None = None) -> JSONResponse:
    corpo = {"detail": detail}          # a mensagem que o Painel mostra
    if codigo:
        corpo["codigo"] = codigo        # código curto para o suporte (erro inesperado)
    return JSONResponse(status_code=status, content=corpo)
```

**Para quê:** todo erro sai no formato `{"detail": "..."}`. Assim o Painel sabe sempre onde achar a frase para mostrar na etapa que falhou.

### Regra de negócio quebrada vira 422 — linhas 29–32

```python
def registrar_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)                        # "quando tocar o alarme ValueError..."
    async def value_error_handler(request: Request, exc: ValueError):
        return _resposta(422, str(exc))                       # ...responda 422 com a própria frase
```

**Para quê:** os Services tocam `ValueError` quando o pedido fere uma regra. Exemplo: "Sem PMPV para Mar/2026: calcule e salve o PMPV antes de salvar o CGF." Esse alarme vira **422** ("não dá para processar"), com a frase do contador.
**Como:** a linha com `@` é um **decorator**, uma etiqueta presa na função. Aqui ela diz ao FastAPI: "quando acontecer `ValueError`, chame esta função". `async` permite esperar sem travar o servidor. Por enquanto, leia como uma função comum.

### Os outros casos — linhas 34–53 (resumo)

Arquivo que sumiu vira **404**, mostrando só o nome do arquivo (linhas 34–39). Banco ocupado ("locked") vira **503**, com "aguarde alguns segundos" (linhas 41–46). Isso pode acontecer porque o Painel faz vários pedidos ao mesmo tempo. Qualquer outro erro vira **500**, com um código de 8 letras que também vai para o log (linhas 48–53).

---

## 4. `Src/api/routers/cgf.py` — o balcão do CGF

O Painel usa as quatro rotas deste arquivo: `historico` ao abrir; `processar`, `calcular-rs` e `salvar` no Processar.

### Criação do balcão — linhas 12–25

```python
from Src.api.schemas.cgf import (CGFCalcularRSRequest, ..., CGFSalvarResponse)  # formulários
from Src.Services.cgf.servicos_cgf import ServicosCGF                                # o contador

router = APIRouter(prefix="/cgf", tags=["CGF"])   # tudo aqui começa com /cgf
_EXTENSOES = {".xlsx", ".xls", ".xlsm", ".csv"}   # tipos de arquivo aceitos no upload
```

**Para quê:** cria o balcão do CGF. Junto com o `/api` do `main.py`, os endereços ficam como `/api/cgf/processar`.
**Como:** uma **rota** (ou **endpoint**) é um endereço mais um verbo que leva a uma função. **GET** pede para ler. **POST** envia dados.

### `processar()` — linhas 28–77

```python
@router.post("/processar", response_model=CGFProcessarResponse)   # POST /api/cgf/processar
def processar(
    arquivos: list[UploadFile] = File(...),            # as planilhas de NF (obrigatório)
    col_fat_volume: str = Form("Volume Faturado"),     # nome da coluna, com valor padrão
    # ... (mais 4 nomes de coluna, linhas 32–35)
) -> CGFProcessarResponse:
    if not arquivos:
        raise ValueError("Nenhuma planilha foi enviada. ...")   # vira 422
    pasta = Path(tempfile.mkdtemp(prefix="cgf_"))               # pasta temporária
    try:
        # ... salva cada planilha na pasta (linhas 48–59)
        r = ServicosCGF().processar_arquivos(caminhos, col_fat_volume, ...)   # o contador calcula
        # ... monta a resposta (linhas 64–75)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)        # apaga a pasta, dê certo ou errado
```

**Para quê:** no Processar, o Painel manda as planilhas de NF do mês que achou na pasta. O balcão devolve os volumes. **Não grava nada**: é a prévia.
**Como:**
- **`response_model`** diz ao FastAPI qual formulário de resposta usar e conferir.
- **`try` / `finally`:** "tente; aconteça o que acontecer, no fim faça isto". É como lavar a louça mesmo se o jantar queimou: a pasta temporária sempre some.
- Nas linhas 50–59, cada arquivo passa por uma triagem. Se não for planilha, toca `ValueError` (linha 53). Se o nome não disser o tipo, vai para `ignorados` (linha 55). Depois é copiado com o nome original (linhas 56–58). A linha 64 descobre o mês pelo nome do arquivo.

> **Observação para o desenvolvedor:** a linha 25 aceita `.xlsm`, mas o contador não lê esse tipo (veja `ler_tabela` na seção 6). O arquivo é ignorado sem aviso.

### `calcular_rs()` — linhas 80–85

```python
@router.post("/calcular-rs", response_model=CGFCalcularRSResponse)
def calcular_rs(payload: CGFCalcularRSRequest) -> CGFCalcularRSResponse:   # JSON vira formulário
    """CGF em R$ = volume final × PMPV (do payload ou, se ausente, do banco). Não grava."""
    return CGFCalcularRSResponse(
        **ServicosCGF().calcular_cgf_rs(payload.periodo, payload.volume_final, payload.pmpv)
    )
```

**Para quê:** antes de salvar, o Painel mostra quanto o CGF vale em reais. Exemplo fictício: 1.000 m³ × R$ 2,5000 = R$ 2.500,00.
**Como:** o FastAPI preenche o formulário `CGFCalcularRSRequest` (o `payload`) com o JSON do pedido. O `**` "despeja" o dicionário do contador nos campos da resposta, casando nome com nome.

### `salvar()` — linhas 88–91

```python
@router.post("/salvar", response_model=CGFSalvarResponse)
def salvar(payload: CGFSalvarRequest) -> CGFSalvarResponse:
    """Grava CGF em R$ (volume final × PMPV) e o resumo de volumes. Exige PMPV."""
    return CGFSalvarResponse(**ServicosCGF().salvar_com_pmpv(payload.periodo, payload.model_dump(), payload.pmpv))
```

**Para quê:** aqui o CGF entra no arquivo-morto. Na próxima vez que o Painel abrir, a etapa CGF aparece como feita.
**Como:** o balcão não faz conta. Ele só entrega o formulário ao contador. `model_dump()` transforma o formulário num dicionário simples.

### `historico()` — linhas 94–96

```python
@router.get("/historico", response_model=list[CGFHistoricoLinha])   # GET: só leitura
def historico() -> list[CGFHistoricoLinha]:
    return [CGFHistoricoLinha(**h) for h in ServicosCGF().historico()]   # uma linha por mês
```

**Para quê:** é o pedido que o Painel faz ao abrir, para saber quais meses do trimestre já têm CGF salvo.
**Como:** `[... for h in ...]` monta uma lista numa linha só: para cada mês que o contador devolve, preenche um formulário `CGFHistoricoLinha`.

---

## 5. `Src/api/schemas/cgf.py` — os formulários

**Pydantic / `BaseModel`:** Pydantic é uma biblioteca que confere dados. Quem herda de `BaseModel` vira um formulário com campos e tipos. Se chegar texto onde se espera número, o FastAPI recusa com 422 antes de chamar a função.

### `CGFVolumes` — linhas 8–13

```python
class CGFVolumes(BaseModel):
    volume_faturado: float          # já sem consumo próprio
    volume_canceladas: float        # informativo: não entra no volume final
    volume_devolucoes: float
    volume_consumo_proprio: float   # informativo: já retirado do faturado
    volume_final: float             # faturado − devoluções
```

**Para quê:** são os cinco volumes que aparecem em quase todo pedido do CGF. Ficam escritos uma vez só.
**Como:** cada linha é `nome: tipo`. `float` é número com casas decimais.

### `CGFProcessarResponse` — linhas 16–20

```python
class CGFProcessarResponse(CGFVolumes):     # herda os 5 volumes e acrescenta:
    periodo_detectado: str          # "" quando o nome dos arquivos não indica o mês
    arquivos_ignorados: list[str]   # nome não diz se é faturada/cancelada/devolução
    problemas: list[ProblemaArquivo] = []   # avisos por arquivo
    logs: list[str]
```

**Para quê:** é a resposta do `processar`. O Painel usa `problemas` para avisar o analista antes de salvar.
**Como:** `class X(CGFVolumes)` é **herança**: X ganha todos os campos de `CGFVolumes` sem reescrever.

### `CGFSalvarRequest` — linhas 23–25

```python
class CGFSalvarRequest(CGFVolumes):
    periodo: str     # ex.: "Mar/2026"
    pmpv: float      # o PMPV do mês; o contador recusa 0
```

### `CGFCalcularRSRequest` e `CGFCalcularRSResponse` — linhas 28–39

```python
class CGFCalcularRSRequest(BaseModel):
    periodo: str
    volume_final: float
    pmpv: float | None = None       # ausente: usa o PMPV salvo do mês

class CGFCalcularRSResponse(BaseModel):
    # ...
    pmpv_origem: str                # "manual" | "banco" | "ausente"
    cgf_rs: float | None            # None sem PMPV
```

**Para quê:** a prévia em reais aceita o PMPV mandado pelo Painel ou busca o do banco. A resposta diz de onde ele veio.

### `CGFSalvarResponse` e `CGFHistoricoLinha` — linhas 42–51

```python
class CGFSalvarResponse(BaseModel):
    cgf_rs: float     # o CGF gravado, em R$
    rpv: float        # o RPV do mês, refeito depois de gravar

class CGFHistoricoLinha(CGFVolumes):
    periodo: str
    cgf_rs: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
```

**Para quê:** depois de salvar, o Painel recebe o valor gravado. No histórico, cada mês traz volumes, valor e data. É com essa lista que o Painel marca a etapa.

---

## 6. `Src/Services/cgf/servicos_cgf.py` — o contador do CGF

Este arquivo é a **fonte única da verdade** do CGF: a conta só existe aqui.

### A classe — linhas 13–14

```python
class ServicosCGF:
    """Especialista no processamento de planilhas (Excel/CSV) e cálculos do CGF."""
```

**Para quê:** reúne numa "mesa" só tudo o que o contador do CGF sabe fazer.
**Como:** as funções dentro de uma classe se chamam *métodos*. O primeiro ingrediente de cada método é **`self`**, que quer dizer "eu mesmo, este contador". Com ele, um método chama outro (`self.tipo_do_nome(...)`).

### O tipo sai do nome do arquivo — linhas 105–119

```python
    PALAVRAS_FATURADA = ("faturada", "complementar")
    PALAVRAS_CANCELADA = ("canc", "deneg", "rejeitad")
    PALAVRAS_DEVOLUCAO = ("devolu", "devolv")

    @classmethod
    def tipo_do_nome(cls, nome: str) -> str | None:
        n = nome.lower()                                   # tudo minúsculo
        if any(p in n for p in cls.PALAVRAS_FATURADA):     # tem "faturada" no nome?
            return "faturada"
        # ... cancelada (115), devolucao (117); senão None
```

**Para quê:** o sistema descobre o tipo da planilha **pelo nome do arquivo**. Por isso a pasta do mês precisa ter nomes como "NF Faturadas..." e "NF Devolvidas...".

### `processar_arquivos()`: preparação — linhas 125–137

```python
    def processar_arquivos(self, arquivos: list, fat_col: str, fat_cons_col: str,
                           fat_cons_val: str, canc_col: str, dev_col: str) -> dict:
        logs = []                                  # o "diário" do processamento
        problemas: list[dict] = []                 # avisos por arquivo, em linguagem simples
        total_faturado = total_canceladas = total_devolucoes = total_consumo_proprio = 0.0
        tipos_enviados: set[str] = set()           # quais tipos chegaram
        # ...
```

**Para quê:** antes de somar, o contador zera as calculadoras e abre duas folhas: o diário e a lista de problemas.

### Para cada arquivo: tipo e leitura — linhas 157–189

```python
        for path in arquivos:
            nome = Path(path).name
            tipo = self.tipo_do_nome(nome)
            if tipo is None:                       # nome não diz o tipo -> problema "erro", pula
                problemas.append(self._problema(nome, "erro", "tipo_nao_reconhecido", "..."))
                continue
            try:
                df = self.ler_tabela(path)         # abre a planilha como tabela (pandas)
            except Exception as e:                 # corrompida, com senha... -> "planilha_ilegivel"
                # ...
                continue
            if df is None:                         # tipo que ler_tabela não lê
                continue
```

**Para quê:** cada planilha passa por uma triagem. Os problemas viram frases para o analista em vez de derrubar o processamento todo.
**Como:** `continue` pula para o próximo arquivo. `df` é uma tabela da biblioteca pandas, como uma aba do Excel dentro do Python.

> **Observação para o desenvolvedor:** `ler_tabela` (linhas 63–72) só lê `.xlsx`, `.xls` e `.csv`. Para `.xlsm` ela devolve `None`, e a linha 184 pula o arquivo **sem registrar problema**.

### Faturadas: separar o consumo próprio — linhas 191–211

```python
            if tipo == "faturada":
                fat_col_real = coluna(df, nome, tipo, fat_col, ["Volume Faturado", "Volume"])  # acha a coluna
                # ...
                mask_cons = self.mascara_consumo(df, fat_cons_col, fat_cons_val)  # True = consumo próprio
                df_cons = df[mask_cons].copy()          # só consumo próprio
                df_sem_cons = df[~mask_cons].copy()     # todo o resto
                # ... converte texto "1.000,50" em número (204–205)
                total_faturado += float(df_sem_cons[fat_col_real].sum())    # (resumo de 207–210)
                total_consumo_proprio += float(df_cons[fat_col_real].sum())
```

**Para quê:** o gás que a própria empresa consome não é venda e sai do faturado. Exemplo fictício: 1.000 m³ faturados, com 100 m³ de consumo próprio, dão 900 m³ de faturado limpo.
**Como:** a "máscara" é uma coluna de sim/não, e `~` inverte. A função `coluna` (linhas 139–155) aceita apelidos do nome da coluna e registra um problema quando não acha nenhum.

### Canceladas e devoluções — linhas 223–241

```python
            elif tipo == "cancelada":
                canc_col_real = coluna(df, nome, tipo, canc_col, ["Volume Canc/Deneg", ...])
                if canc_col_real is not None:
                    # ...
                    total_canceladas += float(vol_canc)       # só informativo
            else:   # devolução
                dev_col_real = coluna(df, nome, tipo, dev_col, ["Volume Devolução", ...])
                if dev_col_real is not None:
                    # ...
                    total_devolucoes += float(vol_dev)        # este sim desconta
```

**Para quê:** soma cada tipo. As canceladas aparecem, mas **não descontam** do volume final.

### Avisos de tipos que faltaram — linhas 243–255

```python
        if "faturada" not in tipos_enviados:          # sem faturadas = erro
            problemas.append(self._problema("", "erro", "sem_faturadas", "..."))
        for tipo in ("cancelada", "devolucao"):       # sem as outras = só aviso
            if tipo not in tipos_enviados:
                problemas.append(self._problema("", "aviso", "tipo_ausente", "..."))
```

**Para quê:** um mês sem devoluções é possível, então é só aviso. Um mês sem faturadas não faz sentido, então é erro.

### A conta final — linhas 257–278

```python
        # Cálculo Final CGF — canceladas não integram o VF (apenas devoluções e consumo próprio)
        volume_final = total_faturado - total_devolucoes        # VF = faturado − devoluções
        # ... resumo no diário (261–268)
        return {
            "logs": logs, "problemas": problemas,
            "volume_final": volume_final, "volume_faturado": total_faturado,
            # ... canceladas, devoluções, consumo próprio
        }
```

**Para quê:** a regra do negócio em uma linha. Exemplo fictício: 900 m³ − 50 m³ devolvidos = **850 m³**.

### `calcular_cgf_rs()` — linhas 296–314

```python
    def calcular_cgf_rs(self, periodo: str, volume_final: float, pmpv: float | None = None) -> dict:
        if not is_periodo_valido(periodo):              # "Mar/2026" sim; "Teste2" não
            raise ValueError(f'O período “{periodo}” não é válido. ...')
        if pmpv and pmpv > 0:
            origem, valor = "manual", pmpv              # veio no pedido
        else:
            valor = self.buscar_pmpv(periodo) or 0.0    # procura no banco
            origem = "banco" if valor > 0 else "ausente"
        valor = arredondar_tarifa(valor) if valor > 0 else 0.0   # PMPV com 4 casas
        volume_final = arredondar_volume(volume_final)            # volume com 2 casas
        cgf_rs = volume_final * valor if valor > 0 else None      # sem PMPV: None
```

**Para quê:** é a prévia em reais do Processar. Sem PMPV, não dá erro: devolve "sem valor" e o Painel avisa que falta o PMPV.
**Como:** os arredondamentos existem para o resultado bater centavo a centavo com a planilha oficial.

### `salvar_cgf()` — linhas 291–294

```python
    def salvar_cgf(self, periodo: str, valor: float):
        with ServicosConsolidacao() as consolidacao:          # o contador da consolidação
            dados = consolidacao.salvar_cgf(periodo, valor)   # grava o CGF do mês
            return dados["rpv"]
```

**Para quê:** o CGF em reais vai para a consolidação do mês, o livro onde ficam CGR, CGF, RET e RP. Dali o SCG que o Painel mostra é calculado.

### `salvar_com_pmpv()` — linhas 316–342

```python
    def salvar_com_pmpv(self, periodo: str, resumo: dict, pmpv: float) -> dict:
        if not is_periodo_valido(periodo):
            raise ValueError(...)                                   # vira 422
        if not pmpv or pmpv <= 0:
            raise ValueError(f"Sem PMPV para {periodo}: calcule e salve o PMPV antes de salvar o CGF.")
        volume_final = arredondar_volume(resumo.get("volume_final"))
        if volume_final == 0.0:
            raise ValueError("Volume final zerado: processe as planilhas de NF antes de salvar.")
        pmpv = arredondar_tarifa(pmpv)
        cgf_rs = volume_final * pmpv                                # ex.: 850 × 2,5000 = R$ 2.125,00
        rpv = self.salvar_cgf(periodo, cgf_rs)                      # 1ª gravação: consolidação
        with DatabasePMPV() as db:
            db.salvar_cgf_resumo(periodo, ..., volume_final)        # 2ª gravação: cgf_resumo (333–341)
        return {"cgf_rs": cgf_rs, "rpv": rpv}
```

**Para quê:** é o "salvar" de verdade. Antes de gravar, ele passa por três travas: período válido, PMPV maior que zero e volume diferente de zero. A do PMPV impede que metros cúbicos sejam gravados no campo de reais.
**Como:** são duas gravações. O valor em R$ vai para `consolidacao`. Os volumes vão para `cgf_resumo`.

> **Observação para o desenvolvedor:** as duas gravações usam conexões diferentes, e a primeira já confirma ao gravar (`database.py:553`). Se a segunda falhar, a primeira fica no banco.

### `historico()` — linhas 344–362

```python
    def historico(self) -> list[dict]:
        with DatabasePMPV() as db:
            resumos = db.listar_cgf_resumos()                      # volumes de cada mês
            linhas = []
            for r in resumos:
                cons = db.buscar_consolidacao(r["periodo"]) or {}  # valor em R$ do mesmo mês
                linhas.append({"periodo": r["periodo"], ..., "cgf_rs": cons.get("cgf") or 0.0, ...})
        from Src.common.periodos import ordenar_historico
        return ordenar_historico(linhas)                           # mais recente primeiro
```

**Para quê:** junta duas gavetas, volumes (`cgf_resumo`) e reais (`consolidacao`), numa linha por mês. É essa lista que o Painel lê ao abrir.
**Como:** `ordenar_historico` (`Src/common/periodos.py:202-208`) ordena os meses do mais novo ao mais velho e marca `periodo_valido` em cada linha.

---

## 7. `Src/Database/database.py` — o arquivo-morto do CGF

**SQL** é a língua dos bancos de dados. Uma **tabela** é como uma planilha: colunas fixas e uma linha por registro.

### Abrir e fechar com segurança — linhas 72–85

```python
    def __enter__(self) -> "DatabasePMPV":       # roda no começo do "with DatabasePMPV() as db:"
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:   # roda no fim do "with"
        try:
            if self.conn is not None:
                if exc_type is None:
                    self.conn.commit()           # tudo certo: confirma
                else:
                    self.conn.rollback()         # deu erro: desfaz
        finally:
            self.fechar()                        # fecha sempre
        return False                             # não esconde o erro
```

**Para quê:** é o que faz o `with` funcionar com o banco. Ninguém deixa a gaveta aberta.
**Como:** uma **transação** é um pacote de gravações que vale inteiro ou não vale nada. `commit` carimba o pacote. `rollback` rasga. Várias funções abaixo já chamam `commit` por conta própria (linhas 553 e 1085).

### A tabela `cgf_resumo` — linhas 230–240

```python
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cgf_resumo (         -- cria se ainda não existir
                periodo                 TEXT PRIMARY KEY,   -- uma ficha por mês
                volume_faturado         REAL DEFAULT 0,
                volume_canceladas       REAL DEFAULT 0,
                volume_devolucoes       REAL DEFAULT 0,
                volume_consumo_proprio  REAL DEFAULT 0,
                volume_final            REAL DEFAULT 0,
                data_atualizacao        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
```

**Para quê:** é a ficha de volumes de cada mês.
**Como:** `PRIMARY KEY` no `periodo` quer dizer que só existe uma ficha por mês. `REAL` é número com decimais.

### A tabela `consolidacao` — linhas 286–312

```sql
CREATE TABLE IF NOT EXISTS  consolidacao(
    id INTEGER PRIMARY KEY  AUTOINCREMENT,   -- número da ficha, automático
    periodo TEXT NOT NULL,
    cgr REAL DEFAULT 0,  ret REAL DEFAULT 0,  rp REAL DEFAULT 0,   -- totais de cada etapa
    rpv REAL DEFAULT 0,  cgf REAL DEFAULT 0,
    scg REAL DEFAULT 0,                                            -- resultado final
    -- ... datas e observações (308–310)
)
```

**Para quê:** é o livro-razão do mês. Cada etapa do Processar escreve sua coluna: Auditoria escreve `cgr`, CGF escreve `cgf`, RET escreve `ret` e Conciliação escreve `rp`. O histórico do SCG que o Painel lê sai daqui.

### Criar a linha do mês — linhas 528–537

```python
    def criar_periodo_consolidacao(self, periodo: str, obs: str = "") -> int:
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute(
            "INSERT OR IGNORE INTO consolidacao (periodo, observacoes) VALUES (?, ?)",  # cria se não houver
            (periodo, obs),
        )
        self.conn.commit()
        # ... devolve o id da linha (536–537)
```

**Para quê:** garante que exista a linha do mês antes de escrever nela. `_garantir_periodo` (linhas 518–526) chama isto quando falta.
**Como:** os `?` são lugares reservados. O valor entra separado, e assim ninguém consegue "injetar" comandos no SQL.

### Gravar o CGF na consolidação — linhas 539–553 e 573–577

```python
    def _update_consolidacao(self, periodo: str, **campos):
        atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)    # ex.: "cgf = ?"
        # ...
        self.cursor.execute(
            f"UPDATE consolidacao SET {atribuicoes}, data_atualizacao = CURRENT_TIMESTAMP "
            f"WHERE periodo IN ({placeholders})", (*valores, *variantes))  # acha "Mar/26" ou "Mar/2026"
        self.conn.commit()

    def atualizar_cgf(self, periodo: str, valor: float):
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)               # cria a linha se faltar
        self._update_consolidacao(periodo, cgf=valor) # escreve só a coluna cgf
```

**Para quê:** escreve o CGF em reais na linha do mês sem mexer nas colunas das outras etapas.
**Como:** `UPDATE ... SET` altera uma linha que já existe. `IN (variantes)` aceita o mês escrito de jeitos diferentes.

### Ler a consolidação com a conta refeita — linhas 635–657

```python
    @staticmethod
    def _com_rpv_scg_calculados(registro: Dict | None) -> Dict | None:
        # ...
        rpv = float(r.get("cgr") or 0.0) - float(r.get("cgf") or 0.0)   # RPV = CGR − CGF
        r["rpv"] = rpv
        r["scg"] = rpv + float(r.get("ret") or 0.0) + float(r.get("rp") or 0.0)  # SCG = RPV + RET + RP
        return r

    def buscar_consolidacao(self, periodo: str) -> dict:
        # ...
        return self._com_rpv_scg_calculados(...)
```

**Para quê:** toda leitura refaz a conta do SCG na hora, como um contador que confere a soma antes de mostrar o livro. Assim o Painel nunca mostra um SCG velho.

### Gravar o resumo de volumes — linhas 1075–1085

```python
    def salvar_cgf_resumo(self, periodo: str, volume_faturado: float, volume_canceladas: float,
                           volume_devolucoes: float, volume_consumo_proprio: float, volume_final: float):
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO cgf_resumo
                (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
                 volume_consumo_proprio, volume_final, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
              volume_consumo_proprio, volume_final))
        self.conn.commit()
```

**Para quê:** guarda os volumes do mês. Se o Processar rodar duas vezes para Mar/2026, fica só a versão mais nova.
**Como:** **`INSERT OR REPLACE`** quer dizer "insira; se já existir uma linha com a mesma chave (`periodo`), troque pela nova". É substituir a ficha na gaveta em vez de empilhar duas.

`listar_cgf_resumos` (linhas 1090–1091 em diante) faz o caminho de volta: `SELECT * FROM cgf_resumo` traz as fichas, das mais recentes para as mais antigas.

---

## Os outros pedidos do Painel

Todos seguem o mesmo caminho do CGF: crachá → router → schema → Service → banco. "Grava?" diz se o pedido muda o arquivo-morto. Observe que nem todo `POST` grava.

**Ao abrir o Painel (só leitura):**

| Endereço | Router (arquivo:linha) | Quem faz a conta | Grava? | Para quê |
|---|---|---|---|---|
| `GET /api/auditoria/historico` | `Src/api/routers/auditoria.py:207` | `servicos_auditoria_lote.historico` | Não | Meses com CGR salvo, para marcar a etapa Auditoria. |
| `GET /api/cgf/historico` | `Src/api/routers/cgf.py:94` | `ServicosCGF.historico` | Não | Meses com CGF salvo: volumes + R$ (seção 6). |
| `GET /api/ret/historico` | `Src/api/routers/ret.py:79` | `servicos_ret_lote.historico` | Não | Meses com RET salvo. |
| `GET /api/conciliacao/historico` | `Src/api/routers/conciliacao.py:94` | `servicos_concilia_lote.historico` | Não | Meses com RP salvo. |
| `GET /api/scg/historico` | `Src/api/routers/scg.py:64` | `ServicosSCG.historico` + `buscar_dados_fontes` | Não | SCG por mês e se ele **diverge** das etapas (tolerância de R$ 0,01, linha 22). |
| `GET /api/pr?periodo=...` | `Src/api/routers/pr.py:32` | `ServicosPR.buscar_dados_periodo` | Não | PR salvo do trimestre. Sem PR salvo, responde 404 com a dica de onde salvar. |
| `POST /api/pr/apurar` | `Src/api/routers/pr.py:53` | `ServicosPR.apurar_trimestre` | Não | Calcula o PR da Nota Técnica (SCG e SR do trimestre civil ÷ VP) e lista o que falta (`pendencias`). |
| `GET /api/pv/trimestre?trimestre=...&ano=...` | `Src/api/routers/pv.py:59` | `ServicosPV.buscar_trimestre` | Não | PV = PMPV + PR do trimestre do ciclo tarifário (ex.: Fev–Abr). |
| `GET /api/sr/trimestre?label=...` | `Src/api/routers/sr.py:92` | `SRUseCases` (`uc.repo.buscar_sr_trimestre`) | Não | SR salvo do trimestre civil (ex.: `Jan/2026_Mar/2026`). Se não houver, 404. |
| `POST /api/nota-tecnica/gerar?periodo=...` | `Src/api/routers/nota_tecnica.py:16` | `Src/infrastructure/exporters/nota_tecnica` (`dados_do_ciclo`, `montar`) | Não | Monta a minuta da Nota Técnica em Word (.docx) para download. |

**No Processar:**

| Endereço | Router (arquivo:linha) | Quem faz a conta | Grava? | Para quê |
|---|---|---|---|---|
| `POST /api/auditoria/processar` | `Src/api/routers/auditoria.py:84` | `servicos_auditoria_lote.auditar_pasta` e `calcular_totais` | Não | Lê os XML/PDF da pasta do mês por empresa e calcula o CGR. |
| `POST /api/auditoria/diferencas` | `Src/api/routers/auditoria.py:165` | `diferencas_auditoria.comparar_com_gravado` | Não | Mostra onde as notas novas diferem das já gravadas, antes de sobrescrever. |
| `POST /api/auditoria/salvar` | `Src/api/routers/auditoria.py:157` | `servicos_auditoria_lote.salvar` | **Sim** | Grava o CGR (recalculado no servidor) e as notas do mês. |
| `POST /api/cgf/processar` | `Src/api/routers/cgf.py:28` | `ServicosCGF.processar_arquivos` | Não | Volumes a partir das planilhas de NF (seção 4). |
| `GET /api/pmpv/mensal/{periodo}` | `Src/api/routers/pmpv.py:51` | `PMPVUseCases` (`uc.repo.buscar_pmpv_mensal`) | Não | PMPV do mês para o CGF em R$. Se não houver, devolve 0. |
| `POST /api/cgf/calcular-rs` | `Src/api/routers/cgf.py:80` | `ServicosCGF.calcular_cgf_rs` | Não | Prévia do CGF em R$. |
| `POST /api/cgf/salvar` | `Src/api/routers/cgf.py:88` | `ServicosCGF.salvar_com_pmpv` | **Sim** | Grava o CGF em R$ na consolidação e os volumes em `cgf_resumo`. |
| `POST /api/ret/processar` | `Src/api/routers/ret.py:37` | `servicos_ret_lote.processar_pasta` | Não | Lê os PDFs das NDs e faturas de transporte (com OCR se precisar) e agrupa por mês. |
| `POST /api/ret/salvar` | `Src/api/routers/ret.py:69` | `servicos_ret_lote.salvar_meses` | **Sim** | Grava o RET de cada mês (recalculado no servidor) e os documentos. |
| `POST /api/conciliacao/processar` | `Src/api/routers/conciliacao.py:37` | `servicos_concilia_lote.processar` | Não | Lê os PDFs de receitas e despesas de penalidade. |
| `POST /api/conciliacao/salvar` | `Src/api/routers/conciliacao.py:72` | `servicos_concilia_lote.salvar` | **Sim** | Grava o RP (recalculado no servidor) e os itens do mês. |

Repare num padrão: todo "salvar" **recalcula no servidor**, em vez de confiar no número que veio do site.

Outro detalhe: `SCG`, `PR`, `PV` e `SR` recebem o contador por `Depends(get_servicos_...)`, em `Src/api/deps.py`. Cada pedido ganha um contador novo, e a conexão com o banco fecha no fim (ex.: `deps.py:32-37`). Isso importa no Painel porque ele faz vários pedidos ao mesmo tempo, e cada um tem sua própria conexão.

---

## Os testes que garantem isso

Um **teste** é um pequeno programa que usa o sistema com dados de mentira e confere se o resultado é o esperado. É a prova real. Os testes rodam com **pytest** (`pytest.ini` na raiz).

### `tests/conftest.py` — o usuário de mentira (linhas 11–18)

```python
@pytest.fixture(autouse=True)                    # roda sozinho antes de TODO teste
def _usuario_logado():
    from Src.api.auth import usuario_atual
    from Src.api.main import app

    app.dependency_overrides[usuario_atual] = lambda: {"id": 1, "nome": "Teste", "email": "teste@local"}
    yield                                        # aqui o teste roda
    app.dependency_overrides.pop(usuario_atual, None)   # depois, desfaz a troca
```

**Para quê:** a API exige crachá em tudo (seção 1). Nos testes, trocamos o segurança por um que sempre diz "é o usuário Teste". Assim cada teste confere só a regra do assunto.
**Como:** uma **fixture** do pytest é uma preparação que roda antes do teste. O que vem depois do `yield` arruma tudo no fim. `autouse=True` aplica a fixture a todos os testes. `dependency_overrides` é o jeito do FastAPI de trocar uma dependência por outra.

### A fixture `client` — `tests/test_api_cgf.py`, linhas 25–33

```python
@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "cgf_teste.db"               # banco novo, numa pasta temporária
    with DatabasePMPV(db_path=str(banco)):          # cria as tabelas vazias
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco)) # a API passa a usar ESTE banco
    from Src.api.main import app
    with TestClient(app) as c:                      # um "navegador de mentira"
        yield c
```

**Para quê:** cada teste ganha um arquivo-morto novinho e vazio. O banco real nunca é tocado.
**Como:** `PLATAFORMA_DB` é a variável que `Src/common/app_paths.py:48` lê para achar o banco. `TestClient` faz pedidos à API sem abrir servidor de verdade.

### Teste 1: processar calcula os volumes — linhas 54–64

Os dados vêm de `_arquivos_sinteticos()` (linhas 42–51), com valores inventados. Faturadas: "Gás" 1.000,50 e 2000, mais "Consumo Proprio" 300. Canceladas: 40. Devoluções: 100,25.

```python
def test_processar_calcula_volumes_e_detecta_periodo(client):
    resp = client.post("/api/cgf/processar", files=_arquivos_sinteticos())   # envia as 3 planilhas
    assert resp.status_code == 200                                 # 200 = deu certo
    r = resp.json()
    assert r["volume_faturado"] == pytest.approx(3000.5)          # 1000,50 + 2000 (sem o consumo)
    assert r["volume_consumo_proprio"] == pytest.approx(300.0)
    assert r["volume_canceladas"] == pytest.approx(40.0)
    assert r["volume_devolucoes"] == pytest.approx(100.25)
    assert r["volume_final"] == pytest.approx(3000.5 - 100.25)    # canceladas não entram
    assert r["periodo_detectado"] == "Mar/2026"                   # veio de "03.26" no nome
    assert r["arquivos_ignorados"] == []
```

**O que ele garante:** o mesmo pedido que o Processar faz, com a regra inteira conferida. O consumo próprio sai do faturado. O texto "1.000,50" vira 1000,5. As canceladas não descontam. O mês sai do nome do arquivo.
**Como:** `assert` quer dizer "garanto que isto é verdade". Se não for, o teste falha e aponta a linha. `pytest.approx` aceita diferenças minúsculas de arredondamento.

### Teste 2: salvar exige PMPV — linhas 194–200

```python
def test_salvar_exige_pmpv(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()   # 1) processa
    payload = {k: r[k] for k in ("volume_faturado", ..., "volume_final")}       # 2) pega os volumes
    resp = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mar/2026", "pmpv": 0})  # 3) PMPV zero
    assert resp.status_code == 422                     # recusado (ValueError -> 422)
    assert "PMPV" in resp.json()["detail"]             # e a mensagem fala do PMPV
    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).status_code == 404  # nada gravado
```

**O que ele garante:** a trava principal do salvar (seção 6, linhas 324–325). Sem PMPV, o servidor recusa, explica o motivo e **não grava nada**. A última linha só confere que o mês continua vazio no banco.
**Como:** o teste percorre o caminho completo do Processar: router → schema → Service → `ValueError` → `errors.py` → 422.

---

## Glossário

| Termo | O que é, em uma frase |
|---|---|
| **API** | O guichê: o programa que recebe pedidos do site e devolve respostas. |
| **JSON** | Jeito de escrever dados em texto, ex.: `{"pmpv": 2.5}`, que site e servidor entendem. |
| **Rota / endpoint** | Um endereço mais um verbo (GET, POST) que leva a uma função do servidor. |
| **GET / POST** | GET pede para ler. POST envia dados (para calcular ou gravar). |
| **Router** | Um balcão por assunto, que agrupa as rotas de um tema (ex.: tudo de `/cgf`). |
| **Função (`def`)** | Uma receita com nome: recebe ingredientes, faz algo, devolve um resultado. |
| **Classe** | Um molde. Dele saem objetos com dados e funções próprias. |
| **Método** | Uma função que mora dentro de uma classe. |
| **`self`** | "Eu mesmo": o objeto que está executando o método. |
| **Decorator (`@`)** | Uma etiqueta presa na função, que liga ou muda o que ela faz (ex.: `@router.post("/salvar")`). |
| **Type hints** | Dicas de tipo (`periodo: str`, `-> dict`) que dizem o que entra e o que sai. |
| **Pydantic / `BaseModel`** | Biblioteca de formulários: confere se os campos vieram com o tipo certo. |
| **Schema** | O formulário padrão de um pedido ou resposta, escrito com Pydantic. |
| **Herança** | `class B(A)`: B ganha tudo o que A tem e pode acrescentar mais. |
| **`response_model`** | Diz ao FastAPI qual formulário usar para conferir a resposta. |
| **Dependência / `Depends`** | Algo que roda antes da função. Ex.: conferir o crachá, entregar um Service novo. |
| **Exceção / `raise`** | Um alarme que interrompe o trabalho. `raise` toca o alarme. |
| **`try` / `except`** | "Tente; se tocar tal alarme, faça isto." |
| **`try` / `finally`** | "Tente; aconteça o que acontecer, no fim faça isto." |
| **`with`** | Abre um recurso e garante que ele seja fechado no fim, mesmo com erro. |
| **JWT** | O crachá: um texto assinado pelo servidor que prova quem é o usuário. |
| **CORS** | A lista de sites que podem chamar a API pelo navegador. |
| **401 / 404 / 422 / 500** | Não autorizado / não encontrado / pedido fere uma regra / erro inesperado. |
| **Tabela (SQL)** | Uma "planilha" do banco: colunas fixas, uma linha por registro. |
| **`PRIMARY KEY`** | A coluna que não pode repetir (ex.: uma ficha por mês). |
| **Transação** | Pacote de gravações que vale inteiro (`commit`) ou é desfeito (`rollback`). |
| **`INSERT OR REPLACE`** | "Insira; se já existir com a mesma chave, troque pela nova." |
| **`INSERT OR IGNORE`** | "Insira; se já existir, deixe como está." |
| **`UPDATE ... SET`** | Altera colunas de uma linha que já existe. |
| **Teste** | Programa que usa o sistema com dados de mentira e confere o resultado. |
| **Fixture (pytest)** | Preparação que roda antes do teste (e arruma tudo depois do `yield`). |
| **`assert`** | "Garanto que isto é verdade". Se não for, o teste falha. |

---

## Exercícios

**1.** Em `Src/api/main.py`, o que faz `_protegido` (linha 41)? O que acontece com um pedido do Painel que chega sem crachá?

<details>
<summary>Resposta</summary>

`_protegido = [Depends(usuario_atual)]` é a regra "antes de atender, confira o crachá". Ela vai em cada `include_router` dos balcões do Ciclo (linhas 44–57). Sem crachá, `usuario_atual` toca o alarme em `Src/api/auth.py:133-134` e o pedido volta com 401: "Você não está conectado...".
</details>

**2.** No Processar, o Painel tenta salvar o CGF com PMPV = 0. Em qual arquivo e linha o pedido é recusado, e qual arquivo transforma isso em 422?

<details>
<summary>Resposta</summary>

A recusa acontece em `Src/Services/cgf/servicos_cgf.py:324-325`, com `ValueError("Sem PMPV para ...")`. Quem transforma em 422 é `Src/api/errors.py:30-32`. O teste que garante isso é `test_salvar_exige_pmpv`, em `tests/test_api_cgf.py:194`.
</details>

**3.** Com valores fictícios: faturadas = 1.000 m³ (já sem consumo próprio), canceladas = 30 m³, devoluções = 50 m³. Qual é o volume final, e em qual linha está a conta?

<details>
<summary>Resposta</summary>

O volume final é 1.000 − 50 = **950 m³**. As canceladas não descontam. A conta está em `Src/Services/cgf/servicos_cgf.py:258`.
</details>

**4.** Ao abrir, o Painel chama `GET /api/cgf/historico`. De quais duas tabelas vêm os dados de cada linha?

<details>
<summary>Resposta</summary>

Os volumes vêm de `cgf_resumo` (`listar_cgf_resumos`, `database.py:1090`). O valor em R$ vem da coluna `cgf` da `consolidacao` (`buscar_consolidacao`, `database.py:652`). Quem junta as duas é `ServicosCGF.historico`, em `servicos_cgf.py:344-362`.
</details>

**5.** Na tabela "Os outros pedidos do Painel", `POST /api/pr/apurar` é um POST. Ele grava alguma coisa? Como dá para saber?

<details>
<summary>Resposta</summary>

Não grava. O router (`Src/api/routers/pr.py:53-60`) só chama `servico.apurar_trimestre`. Esse método (`Src/Services/tarifa/servicos_pr.py:185` em diante) **lê** do banco o SR salvo, o SCG e o VP, calcula o PR e devolve. Ele não chama nenhuma função de salvar. É POST só porque recebe no corpo do pedido a lista dos 3 meses.
</details>
