// ═══════════════════════════════════════════════════════════════════════
//  Controlador do formulário de indicação (Alpine.js)
//  Bloqueia o envio se houver qualquer campo vazio ou documento inválido.
// ═══════════════════════════════════════════════════════════════════════

const BACKEND = "http://localhost:8000";

function formularioIndicacao() {
  return {
    // ─── ESTADO ──────────────────────────────────────────────────────
    form: {
      executivo: "",
      cnpj_industria: "",
      doc_representante: "",
      varejistas: [""],
      detalhes: "",
    },
    tocados: {},              // { campo: true } — só mostra erro depois de "tocar"
    varejistasTocados: {},    // { idx: true }
    enviando: false,
    tentouEnviar: false,
    msgSucesso: false,
    msgErro: "",

    init() {
      // nada a carregar no MVP — painel agora fica em página separada
    },

    // ─── MARCAR CAMPOS COMO "TOCADOS" ────────────────────────────────
    tocarCampo(nome)        { this.tocados[nome] = true; },
    tocarVarejista(idx)     { this.varejistasTocados[idx] = true; },

    // ─── VALIDAÇÃO POR CAMPO ─────────────────────────────────────────
    // Retorna string com a mensagem de erro ou "" se está OK.
    // Só retorna erro se o campo foi tocado OU se o usuário tentou enviar.
    erro(campo) {
      if (!this.tocados[campo] && !this.tentouEnviar) return "";

      const valor = (this.form[campo] || "").trim();

      if (campo === "executivo") {
        if (!valor) return "Informe seu nome ou e-mail.";
        return "";
      }

      if (campo === "cnpj_industria") {
        const d = Validacao.somenteDigitos(valor);
        if (!d) return "Informe o CNPJ da indústria.";
        if (d.length !== 14) return `CNPJ incompleto (${d.length}/14 dígitos).`;
        if (!Validacao.validarCNPJ(d)) return "CNPJ inválido.";
        return "";
      }

      if (campo === "doc_representante") {
        const d = Validacao.somenteDigitos(valor);
        if (!d) return "Informe o CPF ou CNPJ do representante.";
        if (d.length < 11) return `Documento incompleto (${d.length} dígitos). CPF tem 11, CNPJ tem 14.`;
        if (d.length > 11 && d.length < 14) return `CNPJ incompleto (${d.length}/14 dígitos).`;
        if (d.length !== 11 && d.length !== 14) return "Documento deve ter 11 (CPF) ou 14 (CNPJ) dígitos.";
        if (!Validacao.validarDocumentoRepresentante(d)) {
          return d.length === 11 ? "CPF inválido." : "CNPJ inválido.";
        }
        return "";
      }

      return "";
    },

    // Erro específico de um varejista da lista
    erroVarejista(idx) {
      if (!this.varejistasTocados[idx] && !this.tentouEnviar) return "";

      const valor = (this.form.varejistas[idx] || "").trim();
      const d = Validacao.somenteDigitos(valor);

      if (!d) return "Informe o CNPJ do varejista.";
      if (d.length !== 14) return `CNPJ incompleto (${d.length}/14 dígitos).`;
      if (!Validacao.validarCNPJ(d)) return "CNPJ inválido.";

      // Duplicado na própria lista
      const digitosLista = this.form.varejistas.map(v => Validacao.somenteDigitos(v));
      const apareceuAntes = digitosLista.slice(0, idx).includes(d);
      if (apareceuAntes) return "CNPJ já adicionado acima.";

      return "";
    },

    // ─── VALIDAÇÃO GLOBAL DO FORMULÁRIO ──────────────────────────────
    formValido() {
      // Checa todos os campos estáticos
      const campos = ["executivo", "cnpj_industria", "doc_representante"];
      for (const c of campos) {
        const valor = (this.form[c] || "").trim();

        if (c === "executivo" && !valor) return false;
        if (c === "cnpj_industria") {
          const d = Validacao.somenteDigitos(valor);
          if (d.length !== 14 || !Validacao.validarCNPJ(d)) return false;
        }
        if (c === "doc_representante") {
          const d = Validacao.somenteDigitos(valor);
          if (d.length !== 11 && d.length !== 14) return false;
          if (!Validacao.validarDocumentoRepresentante(d)) return false;
        }
      }

      // Pelo menos 1 varejista, todos válidos, sem duplicados
      if (this.form.varejistas.length < 1) return false;
      const digitos = [];
      for (const v of this.form.varejistas) {
        const d = Validacao.somenteDigitos(v || "");
        if (d.length !== 14 || !Validacao.validarCNPJ(d)) return false;
        if (digitos.includes(d)) return false;
        digitos.push(d);
      }

      return true;
    },

    // ─── CAMPO DINÂMICO DE VAREJISTAS ────────────────────────────────
    adicionarVarejista() {
      if (this.form.varejistas.length >= 20) return;
      this.form.varejistas.push("");
    },

    removerVarejista(idx) {
      if (this.form.varejistas.length <= 1) return;
      this.form.varejistas.splice(idx, 1);
      // limpa o "tocado" do item removido para não deixar erro órfão
      delete this.varejistasTocados[idx];
    },

    // ─── ENVIO ───────────────────────────────────────────────────────
    async enviar() {
      this.tentouEnviar = true;
      this.msgErro = "";
      this.msgSucesso = false;

      if (!this.formValido()) {
        // marca todos os campos como tocados para exibir os erros
        ["executivo", "cnpj_industria", "doc_representante"].forEach(c => this.tocados[c] = true);
        this.form.varejistas.forEach((_, i) => this.varejistasTocados[i] = true);
        return;
      }

      this.enviando = true;

      // Monta o payload enviando apenas dígitos (sem máscara) para o backend
      const payload = {
        executivo:          this.form.executivo.trim(),
        cnpj_industria:     Validacao.somenteDigitos(this.form.cnpj_industria),
        doc_representante:  Validacao.somenteDigitos(this.form.doc_representante),
        cnpjs_varejistas:   this.form.varejistas.map(v => Validacao.somenteDigitos(v)).join(","),
        detalhes:           this.form.detalhes.trim(),
      };

      try {
        const resposta = await fetch(`${BACKEND}/indicacoes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (resposta.ok) {
          this.msgSucesso = true;
          this.resetar();
          setTimeout(() => this.msgSucesso = false, 4000);
        } else {
          const erro = await resposta.json().catch(() => ({}));
          const detalhe = erro?.detail;
          this.msgErro = typeof detalhe === "string"
            ? detalhe
            : "Erro ao enviar. Verifique os dados e tente novamente.";
        }
      } catch (err) {
        this.msgErro = "Erro de conexão com o servidor. Tente novamente.";
      }

      this.enviando = false;
    },

    resetar() {
      this.form = {
        executivo: "",
        cnpj_industria: "",
        doc_representante: "",
        varejistas: [""],
        detalhes: "",
      };
      this.tocados = {};
      this.varejistasTocados = {};
      this.tentouEnviar = false;
    },
  };
}

// Expõe para o Alpine.js
window.formularioIndicacao = formularioIndicacao;
