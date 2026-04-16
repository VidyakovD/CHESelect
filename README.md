# SelectVPN

Десктопный VPN-клиент для Windows с раздельным туннелированием.
Через VPN идут только выбранные сайты и приложения — остальной интернет работает напрямую.

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Возможности

- **Раздельное туннелирование по доменам** — добавьте любые сайты, и только они пойдут через VPN, остальное напрямую
- **Раздельное туннелирование по приложениям** — добавьте любые .exe, и весь их трафик пойдёт через VPN (TUN-режим)
- **Два режима:**
  - **Прокси** (по умолчанию) — работает без прав админа, только домены
  - **TUN** — виртуальный адаптер, домены + приложения, нужны права админа
- **VLESS** — xhttp, WebSocket, gRPC, TCP; Reality и TLS
- **Автообновление** через GitHub Releases
- **Системный трей**, защита от дублей, автоочистка прокси

## Установка

Скачайте `SelectVPN-Setup.exe` из [Releases](https://github.com/VidyakovD/CHESelect/releases) и запустите.

## Быстрый старт

1. **Серверы** → вставьте VLESS-ссылку → **Добавить**
2. **ДОМЕНЫ** → введите `youtube.com` → **+**
3. Нажмите кнопку включения

Для роутинга по приложениям: включите **TUN-режим** и запустите от имени администратора.

Подробная инструкция — в файле `Инструкция.txt`.

## Сборка

```bash
pip install -r requirements.txt
python main.py                    # запуск
python -m PyInstaller SelectVPN.spec --noconfirm   # сборка exe
```

Для инсталлятора нужен [Inno Setup 6](https://jrsoftware.org/isinfo.php):
```bash
ISCC.exe installer.iss
```

### Бинарные зависимости (папка bin/)

Скачайте и поместите в `bin/` перед сборкой:
- [xray-core](https://github.com/XTLS/Xray-core/releases) → `xray.exe`
- [sing-box](https://github.com/SagerNet/sing-box/releases) → `sing-box.exe`
- [tun2socks](https://github.com/xjasonlyu/tun2socks/releases) → `tun2socks.exe`
- [wintun](https://www.wintun.net/) → `wintun.dll`
- [Xray geoip/geosite](https://github.com/Loyalsoldier/v2ray-rules-dat/releases) → `geoip.dat`, `geosite.dat`

## Структура

```
main.py               — точка входа
app/core/
  vpn.py              — контроллер (proxy / TUN)
  xray.py             — Xray менеджер (прокси-режим)
  singbox.py           — sing-box менеджер (TUN-режим)
  singbox_config.py    — генератор конфига sing-box
  config.py           — генератор конфига Xray
  vless.py            — парсер VLESS-ссылок
  proxy.py            — системный прокси Windows
  tun.py              — TUN-адаптер (legacy)
  updater.py          — автообновление
app/gui/
  main_window.py      — главное окно
  power_button.py     — кнопка включения
  server_dialog.py    — диалог серверов
  process_picker.py   — выбор процессов
  tray.py             — системный трей
  styles.py           — тёмная тема
app/storage/
  settings.py         — настройки (%APPDATA%)
```

## Лицензия

MIT

Бинарные компоненты: [Xray-core](https://github.com/XTLS/Xray-core) (MPL-2.0), [sing-box](https://github.com/SagerNet/sing-box) (GPL-3.0), [tun2socks](https://github.com/xjasonlyu/tun2socks) (GPL-3.0), [wintun](https://www.wintun.net/) (Prebuilt Binaries License).
