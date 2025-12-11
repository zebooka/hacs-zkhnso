# Интеграция ЖКХНСО для Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

ZKHNSO integration for Home Assistant. Can be used for integrating housing services in Russian Federation, Novosibirsk oblast. 

Интеграция ЖКХНСО.рф для Home Assistant для получения информации о счетчиках и тарифах.

## Установка

### HACS (рекомендованный способ)

1. Установите ЖКХНСО через HACS
2. Перезапустите Home Assistant
3. Добавьте интеграцию через Настройки → Устройства и службы

### Ручная установка

1. Скопируйте папку `zkhnso` в папку `custom_components` в вашем Home Assistant
2. Перезапустите Home Assistant
3. Добавьте интеграцию через Настройки → Устройства и службы

## Настройка

Эта интеграция может быть настроена через пользовательский интерфейс Home Assistant:

1. Откройте Настройки → Устройства и службы
2. Нажмите "+ Добавить интеграцию"
3. Поищите "ЖКХНСО"
4. Заполните параметры учётной записи

## Возможности интеграции

- Получать список активных счетчиков (вкл. серийный номер, тип счетчика, дата следующей поверки, текущее значение, дата предыдущей передачи показаний)
- Получать список тарифов и нормативов

## Поддержка

Отчёты об ошибках и предложения, направляйте через [репозиторий на GitHub](https://github.com/zebooka/hacs-zkhnso).

## Лицензия

Этот проект распространяется под открытой лицензией MIT.

This project is licensed under the MIT License.

