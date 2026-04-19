// ═══════════════════════════════════════════════════════════════════════
//  Validação de CNPJ e CPF — algoritmo oficial (módulo 11)
//  Também exporta funções de máscara e detecção automática de tipo
// ═══════════════════════════════════════════════════════════════════════

// Remove tudo que não for dígito
function somenteDigitos(valor) {
  return (valor || "").replace(/\D/g, "");
}

// Valida CNPJ (14 dígitos) usando os pesos oficiais
function validarCNPJ(cnpj) {
  cnpj = somenteDigitos(cnpj);
  if (cnpj.length !== 14) return false;
  if (/^(\d)\1+$/.test(cnpj)) return false;

  const pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

  let soma = 0;
  for (let i = 0; i < 12; i++) soma += parseInt(cnpj[i], 10) * pesos1[i];
  let d1 = 11 - (soma % 11);
  if (d1 >= 10) d1 = 0;
  if (parseInt(cnpj[12], 10) !== d1) return false;

  soma = 0;
  for (let i = 0; i < 13; i++) soma += parseInt(cnpj[i], 10) * pesos2[i];
  let d2 = 11 - (soma % 11);
  if (d2 >= 10) d2 = 0;
  if (parseInt(cnpj[13], 10) !== d2) return false;

  return true;
}

// Valida CPF (11 dígitos)
function validarCPF(cpf) {
  cpf = somenteDigitos(cpf);
  if (cpf.length !== 11) return false;
  if (/^(\d)\1+$/.test(cpf)) return false;

  let soma = 0;
  for (let i = 0; i < 9; i++) soma += parseInt(cpf[i], 10) * (10 - i);
  let d1 = 11 - (soma % 11);
  if (d1 >= 10) d1 = 0;
  if (parseInt(cpf[9], 10) !== d1) return false;

  soma = 0;
  for (let i = 0; i < 10; i++) soma += parseInt(cpf[i], 10) * (11 - i);
  let d2 = 11 - (soma % 11);
  if (d2 >= 10) d2 = 0;
  if (parseInt(cpf[10], 10) !== d2) return false;

  return true;
}

// Máscara de CNPJ: 00.000.000/0000-00
function mascararCNPJ(valor) {
  const d = somenteDigitos(valor).slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

// Máscara de CPF: 000.000.000-00
function mascararCPF(valor) {
  const d = somenteDigitos(valor).slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1-$2");
}

// Detecta tipo pelo número de dígitos e aplica máscara correta.
// Enquanto o usuário digita, se tiver <=11 dígitos aplica máscara de CPF;
// acima disso, trata como CNPJ.
function mascararDocumento(valor) {
  const d = somenteDigitos(valor);
  return d.length <= 11 ? mascararCPF(d) : mascararCNPJ(d);
}

// Valida o documento do representante (aceita CPF OU CNPJ)
function validarDocumentoRepresentante(valor) {
  const d = somenteDigitos(valor);
  if (d.length === 11) return validarCPF(d);
  if (d.length === 14) return validarCNPJ(d);
  return false;
}

// Retorna "CPF" ou "CNPJ" ou null baseado no comprimento
function tipoDocumento(valor) {
  const d = somenteDigitos(valor);
  if (d.length === 11) return "CPF";
  if (d.length === 14) return "CNPJ";
  return null;
}

// Expõe as funções globalmente para os outros scripts usarem
window.Validacao = {
  validarCNPJ,
  validarCPF,
  validarDocumentoRepresentante,
  mascararCNPJ,
  mascararCPF,
  mascararDocumento,
  tipoDocumento,
  somenteDigitos,
};
