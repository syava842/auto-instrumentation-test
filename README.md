# auto-instrumentation-test

Демо-проект, который показывает, что трейсы OpenTelemetry можно собирать с цепочки связанных сервисов без добавления OTel-кода в приложение.

## Что демонстрирует проект

- Есть 3 Flask-сервиса: `service-a -> service-b -> service-c`.
- Каждый сервис вызывает следующий по HTTP и пишет событие в PostgreSQL.
- Трейсы собираются через автоинструментацию, а не через ручные `span` в коде.
- Трейсы отправляются в `otel-collector`, после чего видны в Jaeger UI.

## Архитектура

1. Клиент вызывает `service-a` (`/run`).
2. `service-a` вызывает `service-b`, `service-b` вызывает `service-c`.
3. Автоинструментация создаёт спаны для:
   - входящих HTTP-запросов (Flask),
   - исходящих HTTP-запросов (`requests`),
   - SQL-вызовов (`psycopg2`).
4. Контекст трейсинга автоматически пробрасывается между сервисами (W3C Trace Context).
5. SDK отправляет данные по OTLP gRPC в `otel-collector`.
6. Collector экспортирует трейсы в Jaeger (OTLP endpoint `jaeger:4317`).

## Что сделано для автоинструментации (без изменений кода сервисов)

### 1) Подключены нужные пакеты в `requirements.txt`

Во всех сервисах добавлены:

- `opentelemetry-distro`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation`
- `opentelemetry-instrumentation-flask`
- `opentelemetry-instrumentation-requests`
- `opentelemetry-instrumentation-psycopg2`

Это даёт автоинструментацию входящих/исходящих HTTP и SQL-запросов.

### 2) Изменена команда запуска контейнера

Во всех `Dockerfile` сервисов используется запуск через `opentelemetry-instrument`:

```bash
opentelemetry-instrument flask --app app run --host=0.0.0.0 --port=${PORT}
```

За счёт этого OTel-инструментация подключается на старте процесса, без изменения `app.py`.

### 3) Добавлены переменные OTel в `docker-compose.yml`

Для каждого сервиса заданы:

- `OTEL_SERVICE_NAME` — имя сервиса в трассах.
- `OTEL_TRACES_EXPORTER=otlp` — экспорт спанов по OTLP.
- `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:14317` — адрес collector внутри Docker-сети.
- `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` — транспорт OTLP gRPC.
- `OTEL_METRICS_EXPORTER=none`, `OTEL_LOGS_EXPORTER=none` — в этом демо включены только трейсы.

### 4) Настроен OpenTelemetry Collector

Файл: `etc/otel-collector/config.yaml`

- Receiver `otlp` слушает:
  - gRPC: `0.0.0.0:14317`
  - HTTP: `0.0.0.0:14318`
- Processor `batch` агрегирует отправку.
- Exporter `otlp/jaeger` отправляет трейсы в Jaeger:
  - `endpoint: "jaeger:4317"`
  - `tls.insecure: true`
- Pipeline `traces`: `receivers: [otlp] -> processors: [batch] -> exporters: [debug, otlp/jaeger]`

### 5) Подготовлен Jaeger для приёма OTLP

В `docker-compose.yml` у сервиса `jaeger` включено:

```yaml
environment:
  COLLECTOR_OTLP_ENABLED: "true"
```

Это включает OTLP-приёмник Jaeger (gRPC `4317`) внутри docker-сети.

## Важно про код сервисов

В `service-a/app.py`, `service-b/app.py`, `service-c/app.py` нет ручных вызовов OpenTelemetry API/SDK (`trace.get_tracer()`, `start_as_current_span()` и т.д.).

Наблюдаемость добавлена только через:

- зависимости,
- команду запуска процесса,
- переменные окружения,
- инфраструктурные конфиги (`docker-compose` + collector).

Именно это и есть автоинструментация без изменения бизнес-логики.

## Запуск

```bash
cd /home/syava842/testautootel
sudo docker compose up -d --build
```

Проверка ручек:

- `http://localhost:18001/run`
- `http://localhost:18002/run`
- `http://localhost:18003/run`

Jaeger UI:

- `http://localhost:16686`

## Как проверить, что трассировка действительно сквозная

1. Открой `http://localhost:18001/run` несколько раз.
2. Открой Jaeger UI и выбери сервис `service-a`.
3. В одном trace должны быть дочерние спаны от `service-b` и `service-c`.
4. В trace также видны HTTP- и SQL-спаны, созданные автоинструментацией.

## Остановка

```bash
sudo docker compose down
```
