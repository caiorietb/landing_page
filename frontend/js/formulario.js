// ═══════════════════════════════════════════════════════════════════════
//  Controlador do formulário de indicação (Alpine.js) — v2.1
//
//  Alinhado ao schema Pydantic IndicacaoCreate em backend/schemas.py
//  e ao index.html com 3 seções (Identificação · Participantes · Lojistas).
//
//  Melhorias v2.1 (sobre v2):
//    • API `erroLojista(idx, campo)` / `marcarLojista(idx, campo)` casando
//      com as bindings do index.html.
//    • `formValido()` reativo (não força marcação) — permite UI feedback
//      no botão de submit sem revelar erros antes do tempo.
//    • Máscara de WhatsApp + pré-preenchimento de UF via DDD (preview).
//    • Auto-expansão do lojista com erro + scroll-to-error no submit.
//    • `lojistaAberto` como único índice (null/number) — elimina bug de
//      múltiplos abertos que o accordion original tinha.
//    • Toast com mensagem de dedup dedicada (`duplicada=true` do backend).
// ═══════════════════════════════════════════════════════════════════════

const BACKEND = (window.BLU_BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

const BRANCO_GESTOR = () => ({ nome: "", email: "", celular: "", cargo: "" });
const BRANCO_REP    = () => ({ nome: "", documento: "", email: "", celular: "", tipo_bonificacao: "" });
const BRANCO_LOJ    = () => ({
  cnpj: "",
  razao_social: "",
  nome_fantasia: "",
  email: "",
  whatsapp: "",
  tipo_produto: "",                 // PagBlu | CredBlu | Split
  condicao_especial: false,
  condicao_especial_descricao: "",
  observacoes: "",
});

const CAMPOS_LOJ = [
  "cnpj", "razao_social", "nome_fantasia", "email",
  "whatsapp", "tipo_produto", "condicao_especial_descricao",
];
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// ─── DDD → UF (preview de regionalização no front) ────────────────────
const DDD_UF = {
  "11":"SP","12":"SP","13":"SP","14":"SP","15":"SP","16":"SP","17":"SP","18":"SP","19":"SP",
  "21":"RJ","22":"RJ","24":"RJ",
  "27":"ES","28":"ES",
  "31":"MG","32":"MG","33":"MG","34":"MG","35":"MG","37":"MG","38":"MG",
  "41":"PR","42":"PR","43":"PR","44":"PR","45":"PR","46":"PR",
  "47":"SC","48":"SC","49":"SC",
  "51":"RS","53":"RS","54":"RS","55":"RS",
  "61":"DF","62":"GO","64":"GO","63":"TO","65":"MT","66":"MT","67":"MS",
  "68":"AC","69":"RO","71":"BA","73":"BA","74":"BA","75":"BA","77":"BA",
  "79":"SE","81":"PE","87":"PE","82":"AL","83":"PB","84":"RN","85":"CE","88":"CE",
  "86":"PI","89":"PI","91":"PA","93":"PA","94":"PA","92":"AM","97":"AM",
  "95":"RR","96":"AP","98":"MA","99":"MA",
};

function formularioIndicacao() {
  return {
    // ─── OPÇÕES ESTÁTICAS ────────────────────────────────────────────
    opcoesParticipantes: [
      { value: "apenas_gestor",           label: "Apenas Gestor da indústria" },
      { value: "gestor_e_representante",  label: "Gestor + Representante (REP)" },
      { value: "gestor_e_vendas_interno", label: "Gestor + Vendas Interno Blu" },
      { value: "apenas_representante",    label: "Apenas Representante (REP)" },
      { value: "direta",                  label: "Indicação direta (sem gestor/REP)" },
    ],
    opcoesCargo: [
      { value: "CEO_Dono",              label: "CEO / Dono" },
      { value: "Diretor_Financeiro",    label: "Diretor Financeiro" },
      { value: "Gerente_Financeiro",    label: "Gerente Financeiro" },
      { value: "Supervisor_Financeiro", label: "Supervisor Financeiro" },
      { value: "Analista_Financeiro",   label: "Analista Financeiro" },
      { value: "Diretor_Comercial",     label: "Diretor Comercial" },
      { value: "Gerente_Comercial",     label: "Gerente Comercial" },
      { value: "Supervisor_Comercial",  label: "Supervisor Comercial" },
      { value: "Analista_Comercial",    label: "Analista Comercial" },
      { value: "Outros",                label: "Outros" },
    ],

    // ─── DADOS DO BACKEND (autocomplete / selects) ───────────────────
    fornecedores: [],
    feiras: [],
    fornecedorBusca: "",
    fornecedorAberto: false,

    // ─── FORM ────────────────────────────────────────────────────────
    form: {
      executivo:     { nome: "", email: "" },
      fornecedor:    { id: null, codigo: "", cnpj: "", razao_social: "" },
      tipo:          "varejo",
      eh_feira:      false,
      feira_nome:    "",
      participantes: "",
      gestor:        BRANCO_GESTOR(),
      representante: BRANCO_REP(),
      prioridade:    "imediato",
      data_contato:  "",
      lojistas:      [BRANCO_LOJ()],
    },

    // ─── ESTADO UI ───────────────────────────────────────────────────
    tocados: {},                    // paths "executivo.nome", "lojistas.2.cnpj", etc.
    tentouEnviar: false,
    enviando: false,
    lojistaAberto: 0,               // null | number — só 1 aberto por vez
    toast: { visible: false, tipo: "success", titulo: "", msg: "" },
    _toastTimer: null,

    // ─── GETTERS ─────────────────────────────────────────────────────
    get precisaGestor() {
      return ["apenas_gestor", "gestor_e_representante", "gestor_e_vendas_interno"]
        .includes(this.form.participantes);
    },
    get precisaRep() {
      return ["gestor_e_representante", "apenas_representante"]
        .includes(this.form.participantes);
    },
    get hojeISO() {
      const d = new Date();
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const dd = String(d.getDate()).padStart(2, "0");
      return `${yyyy}-${mm}-${dd}`;
    },

    // ─── INIT ────────────────────────────────────────────────────────
    async init() {
      await Promise.all([this.carregarFornecedores(), this.carregarFeiras()]);
    },

    async carregarFornecedores() {
      try {
        const r = await fetch(`${BACKEND}/fornecedores`);
        if (r.ok) this.fornecedores = await r.json();
      } catch (_) { /* offline-friendly */ }
    },
    async carregarFeiras() {
      try {
        const r = await fetch(`${BACKEND}/feiras`);
        if (r.ok) this.feiras = await r.json();
      } catch (_) { /* offline-friendly */ }
    },

    // ─── FORNECEDOR (autocomplete) ───────────────────────────────────
    fornecedoresFiltrados() {
      const q = (this.fornecedorBusca || "").trim().toLowerCase();
      if (!q) return this.fornecedores;
      const qDigits = Validacao.somenteDigitos(q);
      return this.fornecedores.filter(f =>
        (f.codigo || "").toLowerCase().includes(q) ||
        (f.razao_social || "").toLowerCase().includes(q) ||
        (f.apelido || "").toLowerCase().includes(q) ||
        (qDigits && (f.cnpj || "").includes(qDigits))
      );
    },
    selecionarFornecedor(f) {
      this.form.fornecedor = {
        id: f.id,
        codigo: f.codigo,
        cnpj: f.cnpj,
        razao_social: f.razao_social,
      };
      this.fornecedorBusca = `${f.codigo} · ${f.razao_social}`;
      this.fornecedorAberto = false;
      this.marcar("fornecedor");
    },
    limparFornecedor() {
      this.form.fornecedor = { id: null, codigo: "", cnpj: "", razao_social: "" };
      this.fornecedorBusca = "";
    },

    // ─── "TOUCHED" ───────────────────────────────────────────────────
    marcar(path) { this.tocados[path] = true; },
    marcarLojista(idx, campo) { this.tocados[`lojistas.${idx}.${campo}`] = true; },

    marcarTudo() {
      ["executivo.nome", "executivo.email", "fornecedor",
       "participantes", "feira_nome", "data_contato",
       "gestor.nome", "gestor.email",
       "representante.nome", "representante.documento"].forEach(p => this.marcar(p));
      this.form.lojistas.forEach((_, i) =>
        CAMPOS_LOJ.forEach(c => this.marcarLojista(i, c)));
    },

    // ─── ERROS POR CAMPO (strings amigáveis) ─────────────────────────
    erroCampo(path) {
      if (!this.tocados[path] && !this.tentouEnviar) return "";

      // Executivo (nome OU email — ao menos um)
      if (path === "executivo.nome" || path === "executivo.email") {
        const nome  = (this.form.executivo.nome  || "").trim();
        const email = (this.form.executivo.email || "").trim();
        if (!nome && !email) return "Informe nome ou e-mail.";
        if (path === "executivo.email" && email && !EMAIL_RE.test(email))
          return "E-mail inválido.";
        return "";
      }

      if (path === "fornecedor") {
        if (!this.form.fornecedor.codigo && !this.form.fornecedor.cnpj)
          return "Selecione o fornecedor.";
        return "";
      }

      if (path === "feira_nome") {
        if (this.form.eh_feira && !(this.form.feira_nome || "").trim())
          return "Selecione a feira.";
        return "";
      }
      if (path === "data_contato") {
        if (this.form.prioridade === "programado" && !this.form.data_contato)
          return "Informe a data para contato.";
        if (this.form.data_contato && this.form.data_contato < this.hojeISO)
          return "A data não pode estar no passado.";
        return "";
      }

      if (path === "participantes") {
        if (this.form.tipo === "varejo" && !this.form.participantes)
          return "Escolha a composição.";
        return "";
      }

      if (path === "gestor.nome" && this.precisaGestor) {
        if (!(this.form.gestor.nome || "").trim()) return "Informe o nome do gestor.";
        return "";
      }
      if (path === "gestor.email" && this.precisaGestor) {
        const e = (this.form.gestor.email || "").trim();
        if (!e) return "Informe o e-mail do gestor.";
        if (!EMAIL_RE.test(e)) return "E-mail inválido.";
        return "";
      }

      if (path === "representante.nome" && this.precisaRep) {
        if (!(this.form.representante.nome || "").trim())
          return "Informe o nome do REP.";
        return "";
      }
      if (path === "representante.documento" && this.precisaRep) {
        const d = Validacao.somenteDigitos(this.form.representante.documento || "");
        if (!d) return "Informe CPF ou CNPJ do REP.";
        if (d.length !== 11 && d.length !== 14) return "CPF tem 11 e CNPJ tem 14 dígitos.";
        if (!Validacao.validarDocumentoRepresentante(d))
          return d.length === 11 ? "CPF inválido." : "CNPJ inválido.";
        return "";
      }

      // Lojista — delegador para erroLojista
      const m = /^lojistas\.(\d+)\.(.+)$/.exec(path);
      if (m) return this.erroLojista(+m[1], m[2]);

      return "";
    },

    // ─── ERROS POR LOJISTA (chamado direto pelo HTML) ────────────────
    erroLojista(idx, campo) {
      const key = `lojistas.${idx}.${campo}`;
      if (!this.tocados[key] && !this.tentouEnviar) return "";

      const lj = this.form.lojistas[idx];
      if (!lj) return "";

      const v = (lj[campo] ?? "").toString().trim();

      if (campo === "cnpj") {
        const d = Validacao.somenteDigitos(v);
        if (!d) return "Informe o CNPJ.";
        if (d.length !== 14) return `CNPJ incompleto (${d.length}/14).`;
        if (!Validacao.validarCNPJ(d)) return "CNPJ inválido.";
        const outros = this.form.lojistas.filter((_, j) => j !== idx)
          .map(o => Validacao.somenteDigitos(o.cnpj || ""));
        if (outros.includes(d)) return "CNPJ repetido na lista.";
        return "";
      }
      if (campo === "razao_social"  && !v) return "Informe a razão social.";
      if (campo === "nome_fantasia" && !v) return "Informe o nome fantasia.";
      if (campo === "email") {
        if (!v) return "Informe o e-mail.";
        if (!EMAIL_RE.test(v)) return "E-mail inválido.";
        return "";
      }
      if (campo === "whatsapp") {
        const d = Validacao.somenteDigitos(v);
        if (!d) return "Informe WhatsApp com DDD.";
        if (d.length < 10) return `Precisa de DDD + número (${d.length}/10).`;
        if (d.length > 11) return "Máximo 11 dígitos.";
        return "";
      }
      if (campo === "tipo_produto" && !v)
        return "Escolha PagBlu, CredBlu ou Split.";
      if (campo === "condicao_especial_descricao") {
        if (lj.condicao_especial && !v) return "Descreva a condição especial.";
        return "";
      }
      return "";
    },

    lojistaTemErro(idx) {
      return CAMPOS_LOJ.some(c => !!this.erroLojista(idx, c));
    },

    // ─── PREVIEW DE UF VIA DDD (front — só orientativo) ──────────────
    ufPreview(idx) {
      const ddd = Validacao.extrairDDD(this.form.lojistas[idx]?.whatsapp || "");
      return ddd && DDD_UF[ddd] ? DDD_UF[ddd] : null;
    },

    // ─── FORM GLOBAL VÁLIDO? (sem marcar) ────────────────────────────
    formValido() {
      // Copia do erroCampo sem depender de "tocados" — avalia o estado real.
      const f = this.form;
      const nome = (f.executivo.nome || "").trim();
      const email = (f.executivo.email || "").trim();
      if (!nome && !email) return false;
      if (email && !EMAIL_RE.test(email)) return false;
      if (!f.fornecedor.codigo && !f.fornecedor.cnpj) return false;
      if (f.eh_feira && !(f.feira_nome || "").trim()) return false;
      if (f.prioridade === "programado" && !f.data_contato) return false;
      if (f.tipo === "varejo" && !f.participantes) return false;
      if (this.precisaGestor) {
        if (!(f.gestor.nome || "").trim()) return false;
        if (!EMAIL_RE.test((f.gestor.email || "").trim())) return false;
      }
      if (this.precisaRep) {
        if (!(f.representante.nome || "").trim()) return false;
        const d = Validacao.somenteDigitos(f.representante.documento || "");
        if (d.length !== 11 && d.length !== 14) return false;
        if (!Validacao.validarDocumentoRepresentante(d)) return false;
      }
      if (f.lojistas.length < 1) return false;
      const seen = new Set();
      for (const l of f.lojistas) {
        const d = Validacao.somenteDigitos(l.cnpj || "");
        if (d.length !== 14 || !Validacao.validarCNPJ(d)) return false;
        if (seen.has(d)) return false;
        seen.add(d);
        if (!(l.razao_social || "").trim())  return false;
        if (!(l.nome_fantasia || "").trim()) return false;
        if (!EMAIL_RE.test((l.email || "").trim())) return false;
        const w = Validacao.somenteDigitos(l.whatsapp || "");
        if (w.length < 10 || w.length > 11) return false;
        if (!["PagBlu", "CredBlu", "Split"].includes(l.tipo_produto)) return false;
        if (l.condicao_especial && !(l.condicao_especial_descricao || "").trim())
          return false;
      }
      return true;
    },

    lojistasPendentes() {
      return this.form.lojistas.filter((_, i) => this.lojistaTemErro(i)).length;
    },

    // ─── LOJISTAS DINÂMICOS ──────────────────────────────────────────
    adicionarLojista() {
      if (this.form.lojistas.length >= 50) return;
      this.form.lojistas.push(BRANCO_LOJ());
      this.lojistaAberto = this.form.lojistas.length - 1;
      this.$nextTick(() => this.scrollParaLojista(this.lojistaAberto));
    },
    removerLojista(idx) {
      if (this.form.lojistas.length <= 1) return;
      this.form.lojistas.splice(idx, 1);
      Object.keys(this.tocados).forEach(k => {
        if (k.startsWith(`lojistas.${idx}.`)) delete this.tocados[k];
      });
      if (this.lojistaAberto === idx) this.lojistaAberto = 0;
    },
    scrollParaLojista(idx) {
      const el = document.querySelectorAll("article")[idx];
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    },

    // ─── ENVIO ───────────────────────────────────────────────────────
    async enviar() {
      this.tentouEnviar = true;
      this.marcarTudo();

      if (!this.formValido()) {
        // abre o primeiro lojista com erro e rola até o primeiro campo com problema
        const idxComErro = this.form.lojistas.findIndex((_, i) => this.lojistaTemErro(i));
        if (idxComErro >= 0) this.lojistaAberto = idxComErro;
        this.mostrarToast("warn", "Revise o formulário",
          this.lojistasPendentes()
            ? `${this.lojistasPendentes()} lojista(s) com pendência.`
            : "Há campos pendentes acima.");
        this.$nextTick(() => {
          const primeiro = document.querySelector(".border-rose-400, .border-rose-300");
          if (primeiro) primeiro.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        return;
      }

      const payload = this.montarPayload();
      this.enviando = true;

      try {
        const r = await fetch(`${BACKEND}/indicacoes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await r.json().catch(() => ({}));

        if (r.status === 201 && body?.duplicada) {
          this.mostrarToast("warn", "Indicação já registrada",
            body.mensagem ||
            "Dedup idempotente: essa mesma indicação (mesmo fornecedor + participantes + lojistas) já foi salva hoje.");
          this.resetar();
        } else if (r.status === 201) {
          this.mostrarToast("success", "Indicação registrada!",
            body.mensagem || "Time comercial foi notificado.");
          this.resetar();
        } else if (r.status === 422) {
          const det = typeof body?.detail === "string"
            ? body.detail
            : Array.isArray(body?.detail)
              ? body.detail.map(d => d.msg || JSON.stringify(d)).join(" · ")
              : "Verifique os dados.";
          this.mostrarToast("error", "Dados inválidos", det);
        } else {
          this.mostrarToast("error", "Erro no servidor",
            body?.detail || `HTTP ${r.status} — tente novamente.`);
        }
      } catch (_) {
        this.mostrarToast("error", "Sem conexão",
          "Não consegui falar com o backend. Verifique sua rede.");
      } finally {
        this.enviando = false;
      }
    },

    montarPayload() {
      const f = this.form;

      const executivo = {};
      if (f.executivo.nome?.trim())  executivo.nome  = f.executivo.nome.trim();
      if (f.executivo.email?.trim()) executivo.email = f.executivo.email.trim().toLowerCase();

      const fornecedor = {};
      if (f.fornecedor.codigo) fornecedor.codigo = f.fornecedor.codigo;
      if (f.fornecedor.cnpj)   fornecedor.cnpj   = Validacao.somenteDigitos(f.fornecedor.cnpj);

      const payload = {
        executivo,
        fornecedor,
        tipo: f.tipo,
        eh_feira: !!f.eh_feira,
        feira_nome: f.eh_feira ? (f.feira_nome || null) : null,
        participantes: f.tipo === "varejo" ? (f.participantes || null) : null,
        prioridade: f.prioridade,
        data_contato: f.prioridade === "programado" ? (f.data_contato || null) : null,
        lojistas: f.lojistas.map(l => ({
          cnpj: Validacao.somenteDigitos(l.cnpj),
          razao_social: l.razao_social.trim(),
          nome_fantasia: l.nome_fantasia.trim(),
          email: l.email.trim().toLowerCase(),
          whatsapp: Validacao.somenteDigitos(l.whatsapp),
          tipo_produto: l.tipo_produto,
          condicao_especial: !!l.condicao_especial,
          condicao_especial_descricao: l.condicao_especial
            ? (l.condicao_especial_descricao?.trim() || null) : null,
          observacoes: l.observacoes?.trim() || null,
        })),
      };

      if (this.precisaGestor) {
        payload.gestor = {
          nome:    f.gestor.nome.trim(),
          email:   f.gestor.email.trim().toLowerCase(),
          celular: f.gestor.celular?.trim() || null,
          cargo:   f.gestor.cargo || null,
        };
      }
      if (this.precisaRep) {
        payload.representante = {
          nome:      f.representante.nome.trim(),
          documento: Validacao.somenteDigitos(f.representante.documento),
          email:     f.representante.email?.trim().toLowerCase() || null,
          celular:   f.representante.celular?.trim() || null,
          tipo_bonificacao: f.representante.tipo_bonificacao || null,
        };
      }

      return payload;
    },

    // ─── TOAST ───────────────────────────────────────────────────────
    mostrarToast(tipo, titulo, msg) {
      this.toast = { visible: true, tipo, titulo, msg: msg || "" };
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => (this.toast.visible = false), 7000);
    },

    resetar() {
      this.form = {
        executivo:     { nome: "", email: "" },
        fornecedor:    { id: null, codigo: "", cnpj: "", razao_social: "" },
        tipo:          "varejo",
        eh_feira:      false,
        feira_nome:    "",
        participantes: "",
        gestor:        BRANCO_GESTOR(),
        representante: BRANCO_REP(),
        prioridade:    "imediato",
        data_contato:  "",
        lojistas:      [BRANCO_LOJ()],
      };
      this.fornecedorBusca = "";
      this.tocados = {};
      this.tentouEnviar = false;
      this.lojistaAberto = 0;
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  };
}

// Expõe para o Alpine.js
window.formularioIndicacao = formularioIndicacao;
