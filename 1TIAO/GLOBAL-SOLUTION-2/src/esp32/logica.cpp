// Máquina de estados do nó da faixa. Ver logica.h e a spec (§5).
//
// Prioridade: ambulância > pedestre já na faixa > travessia estendida (cartão ou câmera) > chuva > escola > pedestre detectado
// > normal. "Pedestre já na faixa" = fases PedestreVerde/PedestrePisca, que NUNCA são interrompidas (nem pela
// ambulância) e o vermelho dos carros estendido enquanto a visão disser que a faixa segue ocupada.
#include "logica.h"

const char* nomeModo(Modo m) {
  switch (m) {
    case Modo::Normal: return "normal";
    case Modo::Pedestre: return "pedestre";
    case Modo::Escola: return "escola";
    case Modo::Chuva: return "chuva";
    case Modo::Ambulancia: return "ambulancia";
  }
  return "?";
}

const char* nomeFase(Fase f) {
  switch (f) {
    case Fase::CarrosVerde: return "carros_verde";
    case Fase::CarrosAmarelo: return "carros_amarelo";
    case Fase::VermelhoTotal: return "vermelho_total";
    case Fase::PedestreVerde: return "pedestre_verde";
    case Fase::PedestrePisca: return "pedestre_pisca";
  }
  return "?";
}

No::No(float comprimentoM) : comprimento_(comprimentoM > 0 ? comprimentoM : 10.0f) {}

void No::emitir(const char* tipo, int32_t valor) {
  if (n_ == FILA) {  // fila cheia: descarta o mais antigo (o sketch drena a cada passo; não deve acontecer)
    ini_ = (ini_ + 1) % FILA;
    n_--;
  }
  fila_[(ini_ + n_) % FILA] = Evento{tipo, valor};
  n_++;
}

bool No::proximoEvento(Evento& e) {
  if (n_ == 0) return false;
  e = fila_[ini_];
  ini_ = (ini_ + 1) % FILA;
  n_--;
  return true;
}

void No::mudarModo(Modo m, uint32_t /*agora*/) {
  if (m == modo_) return;
  modo_ = m;
  emitir("modo_alterado", static_cast<int32_t>(m));
}

float No::etaRestante(uint32_t agora) const { return etaS_ - (agora - etaDesde_) / 1000.0f; }

bool No::ambulanciaPerto(uint32_t agora) const {
  return modo_ == Modo::Ambulancia && etaRestante(agora) <= ETA_BLOQUEIO_S;
}

void No::encerrarAmbulancia(uint32_t agora) {
  etaS_ = -1;
  mudarModo(Modo::Normal, agora);
  if (pedidoGuardado_) {  // quem apertou durante a ambulância é atendido sem apertar de novo
    pedidoGuardado_ = false;
    pedidoEstendido_ = true;
    emitir("pedido_atendido_apos_ambulancia", 0);
  }
}

void No::comando(const Comando& c, uint32_t agora) {
  comandoRecebido_ = true;
  ultimoComando_ = agora;
  if (c.modo == Modo::Ambulancia) {
    if (c.fim) {  // "fim" sem ambulância ativa: só conta como contato da central
      if (modo_ == Modo::Ambulancia) encerrarAmbulancia(agora);
      return;
    }
    etaS_ = c.etaS;
    etaDesde_ = agora;
    mudarModo(Modo::Ambulancia, agora);
    return;
  }
  if (modo_ == Modo::Ambulancia) encerrarAmbulancia(agora);  // outro modo encerra a ambulância (e atende o pedido)
  faixaOcupada_ = c.faixaOcupada;
  alagamento_ = c.alagamento;
  mudarModo(c.modo, agora);
  // a câmera viu quem precisa de mais tempo: mesmo efeito do cartão, para quem esqueceu o cartão
  if (c.modo == Modo::Pedestre && c.estendida) pedirTempo(agora, false);
}

void No::comandoInvalido(uint32_t /*agora*/) { emitir("comando_invalido", 0); }

uint32_t No::duracao(Fase f) const {
  const bool chuva = modo_ == Modo::Chuva;
  switch (f) {
    case Fase::CarrosVerde: return VERDE_CARROS;
    case Fase::CarrosAmarelo: return chuva ? AMARELO_CHUVA : AMARELO;
    case Fase::VermelhoTotal: return chuva ? VERMELHO_TOTAL_CHUVA : VERMELHO_TOTAL;
    case Fase::PedestreVerde:
      return static_cast<uint32_t>(comprimento_ / (faseEstendida_ ? VEL_ESTENDIDA : VEL_NORMAL) * 1000.0f);
    case Fase::PedestrePisca: return PISCA;
  }
  return 1000;
}

void No::irPara(Fase f, uint32_t agora) {
  fase_ = f;
  inicioFase_ = agora;
  if (f == Fase::PedestreVerde) {
    faseEstendida_ = pedidoEstendido_ || modo_ == Modo::Escola;
    if (pedidoEstendido_) {
      pedidoEstendido_ = false;
      emitir("travessia_estendida", static_cast<int32_t>(duracao(f) / 1000));
    }
  } else if (f == Fase::CarrosVerde) {
    faseEstendida_ = false;
  }
}

void No::cartao(uint32_t agora) {
  // uma leitura por segundo no máximo (encostar o cartão várias vezes seguidas gera um único pedido)
  if (cartaoJaLido_ && agora - ultimoCartao_ < INTERVALO_CARTAO) return;
  cartaoJaLido_ = true;
  ultimoCartao_ = agora;
  pedirTempo(agora, true);
}

void No::pedirTempo(uint32_t agora, bool doCartao) {
  if (!doCartao && (pedidoEstendido_ || pedidoGuardado_ || (fase_ == Fase::PedestreVerde && faseEstendida_)))
    return;  // a câmera repete o aviso a cada comando: um pedido já atendido não gera outro
  emitir(doCartao ? "cartao_lido" : "camera_pediu_tempo", 0);
  if (ambulanciaPerto(agora)) {  // prioridade da ambulância: recusa agora, atende depois
    float eta = etaRestante(agora);
    pedidoGuardado_ = true;
    recusaDesde_ = agora;
    recusaAtiva_ = true;
    emitir("pedido_recusado_ambulancia", static_cast<int32_t>(eta < 0 ? 0 : eta));
    return;
  }
  if (fase_ == Fase::PedestreVerde && !faseEstendida_) {  // já atravessando: estende a fase em curso
    faseEstendida_ = true;
    emitir("travessia_estendida", static_cast<int32_t>(duracao(Fase::PedestreVerde) / 1000));
    return;
  }
  if (!(fase_ == Fase::PedestreVerde && faseEstendida_)) pedidoEstendido_ = true;
}

bool No::recusando(uint32_t agora, uint32_t janela) const {
  return recusaAtiva_ && agora - recusaDesde_ < janela;
}

const char* No::texto(uint32_t agora) const {
  if (recusando(agora, MOSTRA_RECUSA)) return "PRIORIDADE AMBULANCIA";
  if (modo_ == Modo::Ambulancia) return "AMBULANCIA - ABRA CAMINHO";
  const bool atravessando = fase_ == Fase::PedestreVerde || fase_ == Fase::PedestrePisca;
  if (pedidoEstendido_ || (faseEstendida_ && atravessando && modo_ != Modo::Escola)) return "TRAVESSIA ESTENDIDA";
  switch (modo_) {
    case Modo::Chuva: return alagamento_ ? "ALAGAMENTO A FRENTE" : "CHUVA - REDUZA";
    case Modo::Escola: return "ESCOLA - DEVAGAR 30 KM/H";
    case Modo::Pedestre: return "PEDESTRE NA VIA - REDUZA";
    default: return "BETTERWAY";
  }
}

Saida No::passo(uint32_t agora) {
  // 1) sem central por 120 s: volta ao normal (o botão continua funcionando de qualquer jeito)
  if (comandoRecebido_ && modo_ != Modo::Normal && agora - ultimoComando_ > SEM_CENTRAL) {
    emitir("sem_central_volta_normal", 0);
    ultimoComando_ = agora;
    if (modo_ == Modo::Ambulancia) encerrarAmbulancia(agora);
    else mudarModo(Modo::Normal, agora);
  }
  // 2) ambulância sem "fim": termina sozinha em eta + 15 s (o bloqueio do botão nunca fica preso)
  if (modo_ == Modo::Ambulancia && etaS_ >= 0 &&
      agora - etaDesde_ > static_cast<uint32_t>(etaS_ * 1000.0f) + FOLGA_AMBULANCIA) {
    encerrarAmbulancia(agora);
  }
  if (recusaAtiva_ && !recusando(agora, MOSTRA_RECUSA)) recusaAtiva_ = false;
  // 3) ciclo do semáforo
  const uint32_t dec = agora - inicioFase_;
  switch (fase_) {
    case Fase::CarrosVerde:
      if (ambulanciaPerto(agora)) {  // verde no sentido da ambulância até ela passar...
        if (dec < AMBULANCIA_VERDE_MAX) break;
        pedestreForcado_ = true;     // ...por no máximo 60 s seguidos: depois, uma travessia de pedestre
        if (pedidoGuardado_) {       // quem apertou durante a espera atravessa com tempo estendido
          pedidoGuardado_ = false;
          pedidoEstendido_ = true;
        }
        irPara(Fase::CarrosAmarelo, agora);
        break;
      }
      if (dec >= (pedidoEstendido_ ? VERDE_CARROS_MIN : VERDE_CARROS)) irPara(Fase::CarrosAmarelo, agora);
      break;
    case Fase::CarrosAmarelo:
      if (dec >= duracao(fase_)) {
        vermelhoAposPedestre_ = false;
        irPara(Fase::VermelhoTotal, agora);
      }
      break;
    case Fase::VermelhoTotal: {
      uint32_t d = duracao(fase_);
      if (vermelhoAposPedestre_ && modo_ == Modo::Pedestre && faixaOcupada_) d += EXTRA_FAIXA_OCUPADA;
      if (dec >= d) {
        if (vermelhoAposPedestre_ || (ambulanciaPerto(agora) && !pedestreForcado_)) {
          irPara(Fase::CarrosVerde, agora);
        } else {
          pedestreForcado_ = false;
          irPara(Fase::PedestreVerde, agora);
        }
      }
      break;
    }
    case Fase::PedestreVerde:  // nunca interrompida
      if (dec >= duracao(fase_)) irPara(Fase::PedestrePisca, agora);
      break;
    case Fase::PedestrePisca:
      if (dec >= duracao(fase_)) {
        vermelhoAposPedestre_ = true;
        irPara(Fase::VermelhoTotal, agora);
      }
      break;
  }
  // 4) saída
  Saida s{};
  s.fase = fase_;
  s.modo = modo_;
  s.texto = texto(agora);
  const uint32_t d2 = agora - inicioFase_;
  s.carroVd = fase_ == Fase::CarrosVerde;
  s.carroAm = fase_ == Fase::CarrosAmarelo;
  s.carroVm = !s.carroVd && !s.carroAm;
  s.pedVd = fase_ == Fase::PedestreVerde;
  s.pedVm = fase_ == Fase::PedestrePisca ? (d2 / 500) % 2 == 0 : !s.pedVd;
  if (recusando(agora, BIPE_RECUSA)) s.buzzer = BUZ_RECUSA;
  else if (modo_ == Modo::Ambulancia) s.buzzer = BUZ_ALERTA;
  else if (fase_ == Fase::PedestreVerde && faseEstendida_) s.buzzer = BUZ_LENTO;
  else if (fase_ == Fase::PedestrePisca && faseEstendida_) s.buzzer = BUZ_RAPIDO;
  else s.buzzer = BUZ_NADA;
  return s;
}
