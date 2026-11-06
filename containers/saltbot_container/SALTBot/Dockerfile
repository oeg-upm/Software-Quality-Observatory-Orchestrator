FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY configure_from_env.sh ./configure_from_env.sh

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /app/configure_from_env.sh \
    && mkdir -p /app/operations /app/results /app/somef_outputs

ENTRYPOINT ["/app/configure_from_env.sh"]
CMD ["saltbot", "--help"]
