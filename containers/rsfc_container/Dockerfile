FROM python:3.11

WORKDIR /app

# dependencias
RUN apt-get update
RUN pip install poetry
RUN poetry config virtualenvs.create false



# instalamos UNICAMENTE entorno (--no-root), si no fallo de que no este el paquete rsfc_runner
COPY pyproject.toml poetry.lock ./
COPY rsfc-0.2.0 ./rsfc-0.2.0
RUN poetry install --no-root

# instalacion de nltk para somef de soca
RUN pip install nltk
RUN python -m nltk.downloader wordnet
RUN python -m nltk.downloader omw-1.4




# resto del runner
COPY rsfc_runner ./rsfc_runner


CMD ["python","-m","rsfc_runner.main"]

