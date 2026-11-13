// Lógica do nó da faixa SEM hardware (nada de Arduino aqui): modos, prioridade, ciclo do semáforo, texto da
// matriz, buzzer e decisão do botão. O sketch.ino só lê o botão, aplica a Saida nos pinos e fala MQTT.
// Spec: docs/specs/2026-11-13-no-esp32-design.md §5. Por não depender do ESP32, pode ganhar teste no PC depois.
#pragma once
#include <stdint.h>

enum class Modo : uint8_t { Normal, Pedestre, Escola, Chuva, Ambulancia };
enum class Fase : uint8_t { CarrosVerde, CarrosAmarelo, VermelhoTotal, PedestreVerde, PedestrePisca };

// Buzzer: o sketch traduz em tons
enum Buzzer : uint8_t { BUZ_NADA = 0, BUZ_LENTO = 1, BUZ_RAPIDO = 2, BUZ_RECUSA = 3, BUZ_ALERTA = 4 };

struct Comando {
  Modo modo = Modo::Normal;
  bool faixaOcupada = false;  // modo pedestre: a visão ainda vê gente na faixa
  bool alagamento = false;    // modo chuva
  bool fim = false;           // modo ambulância: ela já passou
  float etaS = -1;            // modo ambulância: segundos até chegar (calculado por quem manda)
};

struct Saida {
  bool carroVm, carroAm, carroVd, pedVm, pedVd;
  const char* texto;  // ASCII maiúsculo (a matriz não tem acentos)
  uint8_t buzzer;     // Buzzer
  Fase fase;
  Modo modo;
};

struct Evento {
  const char* tipo;  // um dos tipos do contrato (mensagens.TIPOS_EVENTO)
  int32_t valor;     // eta em s (recusa), duração em s (estendida), modo novo (modo_alterado)...
};

// Tempos (ms) e velocidades — spec §5. Fora da classe (constexpr de namespace tem ligação interna): constantes
// static da classe usadas em ternários podem dar "undefined reference" no compilador do ESP32 em C++11.
constexpr uint32_t VERDE_CARROS = 20000, VERDE_CARROS_MIN = 8000, AMARELO = 3000, AMARELO_CHUVA = 4000,
                   VERMELHO_TOTAL = 2000, VERMELHO_TOTAL_CHUVA = 3000, PISCA = 4000, EXTRA_FAIXA_OCUPADA = 10000,
                   SEM_CENTRAL = 120000, FOLGA_AMBULANCIA = 15000, MOSTRA_RECUSA = 3000, INTERVALO_BOTAO = 1000;
constexpr float VEL_NORMAL = 1.2f, VEL_ESTENDIDA = 0.8f, ETA_BLOQUEIO_S = 30.0f;

const char* nomeModo(Modo m);
const char* nomeFase(Fase f);

class No {
 public:
  explicit No(float comprimentoM = 10.0f);
  void comando(const Comando& c, uint32_t agoraMs);  // comando já validado
  void comandoInvalido(uint32_t agoraMs);            // o sketch recusou o JSON
  void botao(uint32_t agoraMs);                      // uma pressão (o sketch já tirou o repique elétrico)
  Saida passo(uint32_t agoraMs);                     // chamar a cada ~50 ms
  bool proximoEvento(Evento& e);                     // drena a fila de eventos a publicar

 private:
  float comprimento_;
  Modo modo_ = Modo::Normal;
  Fase fase_ = Fase::VermelhoTotal;
  bool vermelhoAposPedestre_ = true;  // o vermelho total de partida leva aos carros
  uint32_t inicioFase_ = 0;
  bool faixaOcupada_ = false, alagamento_ = false;
  float etaS_ = -1;
  uint32_t etaDesde_ = 0;
  bool pedidoEstendido_ = false;  // botão aceito, aguardando a fase do pedestre
  bool pedidoGuardado_ = false;   // botão recusado pela ambulância, atender depois
  bool faseEstendida_ = false;    // a travessia em curso é estendida
  bool comandoRecebido_ = false;
  uint32_t ultimoComando_ = 0, ultimoBotao_ = 0, recusaAte_ = 0;
  bool botaoJaApertado_ = false;

  static constexpr int FILA = 8;
  Evento fila_[FILA];
  int ini_ = 0, n_ = 0;

  void emitir(const char* tipo, int32_t valor);
  void mudarModo(Modo m, uint32_t agora);
  void encerrarAmbulancia(uint32_t agora);
  bool ambulanciaPerto(uint32_t agora) const;
  float etaRestante(uint32_t agora) const;
  uint32_t duracao(Fase f) const;
  void irPara(Fase f, uint32_t agora);
  const char* texto(uint32_t agora) const;
};
