# Integração Home Assistant para BlueRetro — Design

**Data:** 2026-05-25
**Status:** Aprovado, pronto para plano de implementação

## Objetivo

Criar uma integração custom do Home Assistant que **descobre automaticamente** um adaptador
BlueRetro via Bluetooth (BLE), expõe **sensores de leitura** com informações do aparelho e
oferece **controles** (reiniciar, dormir). Estruturada como uma biblioteca Python pura
(`blueretro-ble`) mais um `custom_component` fino.

BlueRetro = adaptador ESP32 open-source (darthcloud) que conecta controles Bluetooth a
consoles retro. Ele expõe um servidor GATT BLE de configuração (o mesmo usado pelo web config
em `blueretro.io`).

## Contexto e restrições (confirmados via pesquisa)

1. **Sem bateria, sem input ao vivo.** O serviço de config GATT não tem característico de
   bateria nem telemetria do pad em tempo real. BlueRetro é alimentado pelo console; bateria
   do controle não é exposta.
2. **Config BLE só anuncia/aceita conexão quando NENHUM controle está conectado** — de
   propósito, para liberar o rádio durante o jogo. Logo, o HA só lê/controla com o aparelho
   **ocioso**. Durante o jogo o aparelho não é conectável, então tentativas de conexão falham
   rápido e **não interrompem a partida**.
3. **Plataforma do host HA:** decidido que o HA roda em Pi/servidor com adaptador Bluetooth
   embutido, perto do console. A integração `bluetooth` nativa do HA cuida do transporte e do
   discovery. (Docker no macOS não passa BLE e está fora.)

## Protocolo BLE confirmado

Extraído do código-fonte de `darthcloud/BlueRetroWebCfg` (`utils/constants.js` e helpers).

**Service UUID:** `56830f56-5180-fab0-314b-2fa176799a00`

Os característicos seguem o mesmo prefixo, variando os 2 últimos hex (`a00`..`a0c`):

| Característico (sufixo) | Uso | Acesso |
|---|---|---|
| `...a06` | Versão ABI/API (inteiro) | leitura direta |
| `...a07` | Característico de comando: escreve 1 byte de comando, depois lê o resultado | escrita+leitura |
| `...a09` | Versão do app/firmware (string UTF-8) | leitura direta |
| `...a0c` | Endereço BD (MAC), 6 bytes em ordem reversa (byte 5 primeiro) | leitura direta |
| `...a01`,`a02`,`a04`,`a05` | Config global/output/input (não usado nesta integração) | — |

**Bytes de comando (escrever em `...a07`, depois ler `...a07`):**

| Byte | Comando | Usado aqui |
|---|---|---|
| `0x04` | get gameid | sim (sensor) |
| `0x05` | get cfg src | sim (sensor) |
| `0x07` | get fw name | sim (sensor) |
| `0x38` | sys reset (reiniciar) | sim (botão) |
| `0x37` | sys deep sleep (dormir) | sim (botão) |
| `0x39` | sys factory reset | **fora** (destrutivo) |
| `0x01/0x02/0x03` | get abi/fw/bdaddr | redundantes — usamos leitura direta de `a06/a09/a0c` |
| `0x10/0x11` | set default/gameid cfg | fora (config por jogo, YAGNI) |
| `0x12/0x13/0x14` | dir/file ops | fora |
| `0xA5/0x5A/0xDE` | OTA start/end/abort | fora |

**Decode do endereço BD:** ler 6 bytes de `...a0c`; formatar como
`hex(b5):hex(b4):hex(b3):hex(b2):hex(b1):hex(b0)`, cada byte com 2 dígitos.

## Arquitetura

Monorepo `blueretro-homeassistant` com dois pacotes que se entendem por interface bem definida:

```
blueretro-homeassistant/
  blueretro_ble/                 # lib Python pura (publicável no PyPI)
  custom_components/blueretro/   # integração HA fina (HACS)
  tests/
  docs/superpowers/
```

A integração depende da lib. Em desenvolvimento, a lib é instalada em modo editável; no
`manifest.json` ela entra como `requirements`.

## Componente 1: lib `blueretro-ble`

Pura: não importa nada do `homeassistant`. Recebe um `BLEDevice` do bleak e opera.

```
blueretro_ble/
  __init__.py     # reexporta API pública
  const.py        # SERVICE_UUID, CHAR_ABI, CHAR_CMD, CHAR_APP, CHAR_BDADDR, CMD_*
  models.py       # dataclass BlueRetroState
  parser.py       # funções puras de decode (bdaddr, string, int)
  discovery.py    # supports(service_info) -> bool
  device.py       # classe BlueRetroDevice (conecta, lê, age)
```

**`models.BlueRetroState`** (dataclass, todos opcionais exceto `available`):
`available: bool`, `fw_version: str | None`, `abi_version: int | None`,
`bdaddr: str | None`, `game_id: str | None`, `game_name: str | None`,
`cfg_src: str | None`.

**`parser.py`** (funções puras, sem BLE — alvo principal de testes unitários):
- `decode_bdaddr(raw: bytes) -> str` — 6 bytes reversos → `aa:bb:cc:dd:ee:ff`.
- `decode_string(raw: bytes) -> str` — UTF-8.
- `decode_abi(raw: bytes) -> int` — primeiro byte como inteiro.

**`discovery.supports(service_info) -> bool`** — `True` se o nome começa com `BlueRetro`
**e** o `SERVICE_UUID` está nos service_uuids anunciados.

**`device.BlueRetroDevice`**:
- `async_update(ble_device) -> BlueRetroState` — conecta via
  `bleak_retry_connector.establish_connection`; lê `a06`, `a09`, `a0c` direto; escreve `0x04`,
  `0x05`, `0x07` em `a07` e lê cada resposta; **desconecta**; devolve `BlueRetroState`. Em falha
  de conexão devolve `BlueRetroState(available=False)`.
- `async_reboot(ble_device) -> None` — conecta, escreve `0x38` em `a07`, desconecta.
- `async_deep_sleep(ble_device) -> None` — conecta, escreve `0x37` em `a07`, desconecta.

**`game_name`** (opcional): mapeamento Game ID → nome via arquivo `gameid.db` empacotado (vindo
do repo web). Se o lookup falhar ou o arquivo não existir, `game_name = None` — não é erro.

A conexão é sempre curta (conecta → opera → desconecta) para não segurar o rádio.

## Componente 2: integração `custom_components/blueretro`

```
custom_components/blueretro/
  __init__.py        # async_setup_entry / async_unload_entry; cria coordinator
  manifest.json      # domain, requirements [blueretro-ble], bluetooth matcher
  const.py           # DOMAIN, intervalo de poll
  config_flow.py     # async_step_bluetooth (autodiscover) + async_step_user
  coordinator.py     # BlueRetroCoordinator (DataUpdateCoordinator de BlueRetroState)
  entity.py          # base CoordinatorEntity com device_info
  sensor.py          # sensores
  binary_sensor.py   # "Config disponível"
  button.py          # Reiniciar, Dormir
```

**`manifest.json`** — matcher de descoberta por nome:
```json
{
  "domain": "blueretro",
  "name": "BlueRetro",
  "bluetooth": [{ "local_name": "BlueRetro*" }],
  "config_flow": true,
  "dependencies": ["bluetooth_adapters"],
  "iot_class": "local_polling",
  "requirements": ["blueretro-ble"]
}
```

**`config_flow.py`**:
- `async_step_bluetooth(discovery_info)` — disparado pelo matcher; valida via
  `discovery.supports`; usa o endereço BLE como `unique_id`; mostra passo de confirmação.
- `async_step_user` — fallback: lista dispositivos BlueRetro descobertos para adicionar
  manualmente.

**`coordinator.py`** — `DataUpdateCoordinator[BlueRetroState]`:
- A cada intervalo (`SCAN_INTERVAL`, padrão **5 min**) pega o `BLEDevice` por endereço com
  `bluetooth.async_ble_device_from_address(hass, address, connectable=True)`.
- Se não houver device conectável → `BlueRetroState(available=False)` (ocupado/fora de alcance).
- Senão chama `device.async_update`. Repassa o coordinator para os botões agirem.

## Entidades no HA

**Sensores** (`sensor.py`), todos `available` espelhando `state.available`:
- `firmware` — versão do firmware (`fw_version`).
- `abi_version` — versão ABI (diagnóstico, `entity_category=diagnostic`).
- `game_id` — Game ID atual.
- `game_name` — nome do jogo (se resolvido).
- `cfg_src` — fonte de configuração.
- `bdaddr` — endereço BD (diagnóstico).

**Binary sensor** (`binary_sensor.py`):
- `config_available` — `on` quando a última conexão funcionou (aparelho ocioso/conectável),
  `off` quando não (jogando/fora de alcance). `device_class=connectivity`.

**Botões** (`button.py`):
- `reboot` — chama `coordinator.device.async_reboot`.
- `deep_sleep` — chama `coordinator.device.async_deep_sleep`.

Todas as entidades compartilham o mesmo `DeviceInfo` (identificada pelo endereço BLE; modelo
"BlueRetro"; versão de firmware preenchida quando disponível).

## Fluxo de dados

1. Adaptador anuncia BLE → integração `bluetooth` do HA → matcher `BlueRetro*` →
   `async_step_bluetooth` → card de descoberta no HA.
2. Usuário confirma → cria config entry → `async_setup_entry` cria `BlueRetroCoordinator`.
3. Coordinator, a cada 5 min: resolve `BLEDevice` → `device.async_update` → `BlueRetroState` →
   entidades atualizam.
4. Jogando: aparelho não conectável → `available=False` → sensores `unavailable`,
   `config_available=off`. Sem interrupção do jogo.
5. Botões: usuário clica → `device.async_reboot/deep_sleep` (escreve em `a07`).

## Tratamento de erros

- Falha de conexão (ocupado / fora de alcance) → estado `available=False`, log em nível debug,
  novo retry no próximo ciclo. `bleak-retry-connector` cuida de retries transientes.
- Resposta de característico inesperada/curta → parser devolve `None` para aquele campo, sem
  derrubar o update inteiro.
- Botão com aparelho indisponível → levanta `HomeAssistantError` com mensagem clara
  ("BlueRetro ocupado ou fora de alcance").

## Estratégia de testes

**Lib (`tests/lib/`)** — sem BLE real:
- `parser.py`: `decode_bdaddr` (ordem reversa correta), `decode_string`, `decode_abi`.
- `discovery.supports`: aceita nome+uuid certos, rejeita os errados.
- `device.async_update`: `BleakClient` mockado devolvendo bytes fixos por característico;
  verifica leituras diretas, sequência escrita-então-leitura em `a07`, e
  `available=False` em falha de conexão.
- `device.async_reboot/deep_sleep`: verifica o byte de comando escrito.

**Integração (`tests/integration/`)** — `pytest-homeassistant-custom-component`:
- Config flow: discovery via `bluetooth` mockado cria entry com `unique_id` = endereço;
  evita duplicado.
- `async_setup_entry`: cria as entidades esperadas.
- Botão: clique chama o método certo da lib (lib mockada).
- Coordinator: device não conectável → entidades `unavailable`.

## Stack

- Python 3.12+
- `bleak`, `bleak-retry-connector`, `habluetooth` / API `homeassistant.components.bluetooth`
- `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`
- Distribuição: HACS (custom repository) para a integração; lib publicável no PyPI

## Fora de escopo (YAGNI)

- Bateria e input/status do controle ao vivo (não expostos pelo hardware).
- Reset de fábrica (`0x39`) — destrutivo; pode entrar depois atrás de confirmação.
- Atualização OTA de firmware (`0xA5`).
- Config por jogo / set default cfg (`0x10`/`0x11`).
- Gerência de arquivos (N64 pak, DC VMU).

## Suposições a validar no aparelho real

- Que `a06`/`a09`/`a0c` são legíveis por leitura direta sem handshake (o web config faz assim).
- Que o aparelho de fato anuncia o `SERVICE_UUID` no advertisement (necessário para o matcher;
  se anunciar só o nome, o matcher por `local_name` ainda funciona).
- Comportamento exato de "config indisponível durante o jogo" — confirmar que a conexão
  simplesmente falha (e não trava).
