// Nó ESP32 da faixa (Via Segura SP) — casca de hardware e MQTT. NÃO decide nada: lê o botão, repassa comandos à
// lógica (logica.cpp) e aplica a Saida em LEDs, buzzer e matriz. Spec: docs/specs/2026-11-13-no-esp32-design.md
//
// Wokwi (navegador): Wi-Fi "Wokwi-GUEST"; broker público test.mosquitto.org:1883 (sem senha: só demonstração).
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>
#include <math.h>
#include "logica.h"

// ---------------------------------------------------------------- pinos (diagram.json)
const int PIN_CARRO_VM = 25, PIN_CARRO_AM = 26, PIN_CARRO_VD = 27, PIN_PED_VM = 32, PIN_PED_VD = 33;
const int PIN_BOTAO = 14, PIN_BUZZER = 13, PIN_MATRIZ_CS = 5;  // matriz: DIN 23 (MOSI), CLK 18 (SCK)

// ---------------------------------------------------------------- rede e contrato (src/central/mensagens.py)
const char* WIFI_SSID = "Wokwi-GUEST";
const char* BROKER = "test.mosquitto.org";
const int PORTA = 1883;
const char* TOPICO_COMANDO = "viasegura/gs2026/no/largo-concordia/comando";
const char* TOPICO_ESTADO = "viasegura/gs2026/no/largo-concordia/estado";
const char* TOPICO_EVENTO = "viasegura/gs2026/no/largo-concordia/evento";

WiFiClient wifi;
PubSubClient mqtt(wifi);
MD_Parola matriz(MD_MAX72XX::FC16_HW, PIN_MATRIZ_CS, 4);
No no(10.0f);  // comprimento da faixa: 10 m (o do Largo da Concórdia ainda não foi medido)

char boot[8];
uint32_t seq = 0, ultimoPasso = 0, ultimaReconexao = 0;
String ultimoComandoId = "";
const char* textoAtual = nullptr;
Fase faseAnterior = Fase::CarrosAmarelo;
Modo modoAnterior = Modo::Ambulancia;

// ---------------------------------------------------------------- validação do comando (= mensagens.validar_comando)
bool modoDeTexto(const char* s, Modo& m) {
  if (!s) return false;
  if (!strcmp(s, "normal")) m = Modo::Normal;
  else if (!strcmp(s, "pedestre")) m = Modo::Pedestre;
  else if (!strcmp(s, "escola")) m = Modo::Escola;
  else if (!strcmp(s, "chuva")) m = Modo::Chuva;
  else if (!strcmp(s, "ambulancia")) m = Modo::Ambulancia;
  else return false;
  return true;
}

bool validar(JsonDocument& doc, Comando& c) {
  if (!doc.is<JsonObject>()) return false;
  JsonObject o = doc.as<JsonObject>();
  if (!(o["v"].is<int>() && o["v"].as<int>() == 1)) return false;
  if (!o["id"].is<const char*>() || !strlen(o["id"].as<const char*>())) return false;
  if (!o["ts"].is<const char*>()) return false;
  if (!modoDeTexto(o["modo"].as<const char*>(), c.modo)) return false;
  for (JsonPair kv : o) {  // contrato fechado: campo desconhecido ou fora do modo dele = inválido
    const char* k = kv.key().c_str();
    if (!strcmp(k, "v") || !strcmp(k, "id") || !strcmp(k, "ts") || !strcmp(k, "modo")) continue;
    if (!strcmp(k, "faixa_ocupada")) {
      if (c.modo != Modo::Pedestre || !kv.value().is<bool>()) return false;
      c.faixaOcupada = kv.value().as<bool>();
    } else if (!strcmp(k, "alagamento")) {
      if (c.modo != Modo::Chuva || !kv.value().is<bool>()) return false;
      c.alagamento = kv.value().as<bool>();
    } else if (!strcmp(k, "fim")) {
      if (c.modo != Modo::Ambulancia || !kv.value().is<bool>()) return false;
      c.fim = kv.value().as<bool>();
    } else if (!strcmp(k, "eta_s")) {
      if (c.modo != Modo::Ambulancia || kv.value().is<bool>() || !kv.value().is<float>()) return false;
      float e = kv.value().as<float>();
      if (!isfinite(e) || e < 0) return false;
      c.etaS = e;
    } else {
      return false;
    }
  }
  if (c.modo == Modo::Ambulancia && !c.fim && c.etaS < 0) return false;  // ambulância precisa do tempo de chegada
  return true;
}

void aoReceber(char* topico, byte* payload, unsigned int tam) {
  JsonDocument doc;
  Comando c;
  uint32_t agora = millis();
  if (deserializeJson(doc, payload, tam) || !validar(doc, c)) {
    Serial.printf("[%lu] COMANDO INVALIDO: %.*s\n", agora, (int)tam, (const char*)payload);
    no.comandoInvalido(agora);
    return;
  }
  ultimoComandoId = doc["id"].as<String>();
  Serial.printf("[%lu] COMANDO %s (id %s)\n", agora, nomeModo(c.modo), ultimoComandoId.c_str());
  no.comando(c, agora);
}

// ---------------------------------------------------------------- MQTT (não bloqueante: o nó funciona sem rede)
void conectarSePreciso(uint32_t agora) {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected() || agora - ultimaReconexao < 5000) return;
  ultimaReconexao = agora;
  String id = String("no-largo-concordia-") + boot;
  if (mqtt.connect(id.c_str())) {
    mqtt.subscribe(TOPICO_COMANDO, 1);
    Serial.printf("[%lu] MQTT conectado a %s; assinando %s\n", agora, BROKER, TOPICO_COMANDO);
    modoAnterior = Modo::Ambulancia;  // força republicar o estado
    faseAnterior = Fase::CarrosAmarelo;
  } else {
    Serial.printf("[%lu] MQTT falhou (rc=%d); tento de novo em 5 s\n", agora, mqtt.state());
  }
}

void publicarEvento(const Evento& e, const Saida& s, uint32_t agora) {
  JsonDocument doc;
  doc["v"] = 1;
  doc["tipo"] = e.tipo;
  doc["seq"] = seq++;
  doc["boot"] = boot;
  JsonObject d = doc["detalhe"].to<JsonObject>();
  d["valor"] = e.valor;
  d["modo"] = nomeModo(s.modo);
  d["fase"] = nomeFase(s.fase);
  d["ms"] = agora;
  char buf[256];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  Serial.printf("[%lu] EVENTO %s valor=%ld\n", agora, e.tipo, (long)e.valor);
  if (mqtt.connected()) mqtt.publish(TOPICO_EVENTO, (const uint8_t*)buf, n, false);
}

void publicarEstado(const Saida& s) {
  JsonDocument doc;
  doc["v"] = 1;
  doc["modo"] = nomeModo(s.modo);
  doc["fase"] = nomeFase(s.fase);
  doc["ultimo_comando"] = ultimoComandoId;
  doc["boot"] = boot;
  char buf[200];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  if (mqtt.connected()) mqtt.publish(TOPICO_ESTADO, (const uint8_t*)buf, n, true);  // retido
}

// ---------------------------------------------------------------- saída física
void aplicarBuzzer(uint8_t b, uint32_t agora) {
  static uint8_t anterior = BUZ_NADA;
  bool ligado = false;
  unsigned int freq = 880;
  switch (b) {
    case BUZ_LENTO: ligado = agora % 1000 < 120; break;               // travessia estendida: bipe lento
    case BUZ_RAPIDO: ligado = agora % 300 < 100; break;               // pisca: bipe rápido
    case BUZ_RECUSA: ligado = true; freq = 220; break;                // pedido recusado (grave)
    case BUZ_ALERTA: ligado = true; freq = (agora / 400) % 2 ? 660 : 990; break;  // ambulância
    default: break;
  }
  if (ligado) tone(PIN_BUZZER, freq);
  else if (anterior != BUZ_NADA || b != BUZ_NADA) noTone(PIN_BUZZER);
  anterior = b;
}

void aplicar(const Saida& s, uint32_t agora) {
  digitalWrite(PIN_CARRO_VM, s.carroVm);
  digitalWrite(PIN_CARRO_AM, s.carroAm);
  digitalWrite(PIN_CARRO_VD, s.carroVd);
  digitalWrite(PIN_PED_VM, s.pedVm);
  digitalWrite(PIN_PED_VD, s.pedVd);
  aplicarBuzzer(s.buzzer, agora);
  if (s.texto != textoAtual) {  // só reinicia a rolagem quando o texto muda
    textoAtual = s.texto;
    matriz.displayClear();
    matriz.displayText(textoAtual, PA_LEFT, 40, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
    Serial.printf("[%lu] MATRIZ \"%s\"\n", agora, textoAtual);
  }
}

// ---------------------------------------------------------------- comando pela serial (teste sem rede / plano B)
// O mesmo JSON do tópico de comando, uma linha por comando. Serve para testar no Wokwi sem login (sem internet) e
// para a apresentação se o broker público cair.
void lerSerial() {
  static char buf[320];
  static size_t n = 0;
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (n > 0) aoReceber(nullptr, (byte*)buf, n);
      n = 0;
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = ch;
    }
  }
}

// ---------------------------------------------------------------- botão (repique elétrico de 50 ms)
bool botaoApertado(uint32_t agora) {
  static int estavel = HIGH, ultimoLido = HIGH;
  static uint32_t mudouEm = 0;
  int lido = digitalRead(PIN_BOTAO);
  if (lido != ultimoLido) {
    ultimoLido = lido;
    mudouEm = agora;
  }
  if (agora - mudouEm > 50 && lido != estavel) {
    estavel = lido;
    return estavel == LOW;  // borda de descida = uma pressão
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  for (int p : {PIN_CARRO_VM, PIN_CARRO_AM, PIN_CARRO_VD, PIN_PED_VM, PIN_PED_VD}) pinMode(p, OUTPUT);
  pinMode(PIN_BOTAO, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  snprintf(boot, sizeof(boot), "%06lx", (unsigned long)(esp_random() & 0xFFFFFF));
  matriz.begin();
  matriz.setIntensity(4);
  WiFi.begin(WIFI_SSID, "", 6);
  mqtt.setServer(BROKER, PORTA);
  mqtt.setCallback(aoReceber);
  mqtt.setBufferSize(512);
  // keepalive de 60 s (padrão 15 s): no Wokwi a simulação roda abaixo do tempo real e o broker derrubava a
  // conexão a cada ~15 s simulados (visto na aceitação: reconexões em 130, 144, 149 s)
  mqtt.setKeepAlive(60);
  Serial.printf("Via Segura SP - no da faixa (boot %s)\n", boot);
}

void loop() {
  uint32_t agora = millis();
  if (botaoApertado(agora)) {
    Serial.printf("[%lu] BOTAO\n", agora);
    no.botao(agora);
  }
  lerSerial();
  conectarSePreciso(agora);
  mqtt.loop();
  if (agora - ultimoPasso >= 50) {
    ultimoPasso = agora;
    Saida s = no.passo(agora);
    aplicar(s, agora);
    Evento e;
    while (no.proximoEvento(e)) publicarEvento(e, s, agora);
    if (s.fase != faseAnterior || s.modo != modoAnterior) {
      Serial.printf("[%lu] FASE %s | modo %s\n", agora, nomeFase(s.fase), nomeModo(s.modo));
      faseAnterior = s.fase;
      modoAnterior = s.modo;
      publicarEstado(s);
    }
  }
  if (matriz.displayAnimate()) matriz.displayReset();
}
