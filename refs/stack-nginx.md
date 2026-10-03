# Правила nginx

1. `server_tokens off`.
2. Заголовки безопасности на уровне `server` с `always`. `X-Content-Type-Options nosniff`, `Referrer-Policy`, `frame-ancestors` в CSP или `X-Frame-Options`, `Strict-Transport-Security` на HTTPS.
3. `add_header` внутри `location` отменяет все заголовки уровня выше. Нужен свой заголовок в `location`, повтори общие или вынеси их в `include`.
4. Слэш в конце `proxy_pass` меняет путь. `proxy_pass http://api/;` срезает префикс `location`, `proxy_pass http://api;` передает путь как есть. Выбор осознанный и проверен запросом.
5. Прокси передает `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`. За балансировщиком `set_real_ip_from` и `real_ip_header`.
6. Websocket. `proxy_http_version 1.1`, заголовки `Upgrade` и `Connection` через `map $http_upgrade`.
7. SPA. `try_files $uri $uri/ /index.html`, а API и статика с хешем в этот fallback не попадают.
8. Статика с хешем в имени кешируется на год с `immutable`. `index.html` с `no-cache`.
9. gzip включен для текстовых типов, в `gzip_types` есть JS, CSS, JSON, SVG.
10. `client_max_body_size` задан явно под загрузки сервиса.
11. `proxy_read_timeout` и `proxy_connect_timeout` заданы под реальные ответы бэка.
12. Upstream в переменной требует `resolver`. Имена сервисов compose резолвятся через `resolver 127.0.0.11`.
13. `alias` и `location` с префиксом оба заканчиваются слэшем, иначе возможен выход из каталога.
14. В `location` нет `if`, кроме `return` и `rewrite ... last`.
