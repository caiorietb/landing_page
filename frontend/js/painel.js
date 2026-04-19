// ═══════════════════════════════════════════════════════════════════════
//  Controlador do painel de indicações (Alpine.js)
//  Carrega do GET /indicacoes, filtra em tempo real e expande linhas.
// ═══════════════════════════════════════════════════════════════════════

const BACKEND = "http://localhost:8000";

function painelIndicacoes() {
  return {
    indicacoes: [],
    carregando: true,
    erro: false,
    busca: "",
    expandido: null,

    async carregar() {
      this.carregando = true;
      this.erro = false;
      this.expandido = null;

      try {
        const resposta = await fetch(`${BACKEND}/indicacoes`);
        if (!resposta.ok) throw new Error("status " + resposta.status);
        this.indicacoes = await resposta.json();
      } catch (err) {
        this.erro = true;
        this.indicacoes = [];
      }

      this.carregando = false;
    },

    // Filtra localmente por executivo (parcial, case-insensitive) ou CNPJ da indústria
    resultadosFiltrados() {
      const termo = (this.busca || "").trim().toLowerCase();
      if (!termo) return this.indicacoes;

      const termoDigitos = Validacao.somenteDigitos(termo);

      return this.indicacoes.filter(item => {
        const executivoMatch = (item.executivo || "").toLowerCase().includes(termo);
        const cnpjMatch = termoDigitos && (item.cnpj_industria || "").includes(termoDigitos);
        return executivoMatch || cnpjMatch;
      });
    },

    // ─── HELPERS ────────────────────────────────────────────────────
    listarVarejistas(cnpjsStr) {
      return (cnpjsStr || "")
        .split(",")
        .map(c => Validacao.somenteDigitos(c))
        .filter(c => c.length > 0);
    },

    contarVarejistas(cnpjsStr) {
      return this.listarVarejistas(cnpjsStr).length;
    },

    formatarDoc(doc) {
      const d = Validacao.somenteDigitos(doc);
      if (d.length === 11) return Validacao.mascararCPF(d);
      if (d.length === 14) return Validacao.mascararCNPJ(d);
      return doc;
    },

    formatarData(iso) {
      if (!iso) return "";
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit"
      });
    },
  };
}

window.painelIndicacoes = painelIndicacoes;
