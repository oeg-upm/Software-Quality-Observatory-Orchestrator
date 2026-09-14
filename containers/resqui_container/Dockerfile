FROM python:3.11

WORKDIR /app

# dependencias
RUN apt-get update && apt-get install -y --no-install-recommends docker-cli git && rm -rf /var/lib/apt/lists/*

RUN git config --global http.version HTTP/1.1 \
    && git config --global http.lowSpeedLimit 1000 \
    && git config --global http.lowSpeedTime 600 \
    && git config --global http.postBuffer 524288000 \
    && git config --global core.compression 0 \
    && git config --global advice.detachedHead false
    
RUN pip install poetry
RUN poetry config virtualenvs.create false



COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root


# resqui
COPY QualityPipelines-2.0 ./QualityPipelines-2.0
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_RESQUI=2.0.0 pip install -e ./QualityPipelines-2.0


# instalacion de nltk para somef
RUN pip install nltk
RUN python -m nltk.downloader wordnet
RUN python -m nltk.downloader omw-1.4

# resto del runner
COPY resqui_runner ./resqui_runner


CMD ["python","-m","resqui_runner.main"]

