# Copa AMVI - Backend Django

Sistema web para gestão do campeonato de futebol Copa AMVI.

## Pré-requisitos
- Docker e Docker Compose instalados.

## Como rodar o projeto localmente

1. Clone o repositório:
```bash
git clone <URL_DO_REPOSITORIO>
cd copa-amvi
```

2. Crie e aplique as migrações do banco:
```bash
docker compose run --rm web python manage.py migrate
```

3. (Opcional) Crie o usuário administrador para acessar o Django Admin:
```bash
docker compose run --rm web python manage.py createsuperuser
```

4. Suba o servidor:
```bash
docker compose up
```

Acesse a aplicação em `http://localhost:8000` e o painel administrativo em `http://localhost:8000/admin`.