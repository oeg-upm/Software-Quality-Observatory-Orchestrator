FROM rsmetacheck-bot:latest

ENV NLTK_DATA=/usr/local/share/nltk_data

RUN uv run python -m nltk.downloader -d /usr/local/share/nltk_data \
    wordnet \
    omw-1.4 \
    punkt \
    punkt_tab \
    stopwords

COPY initial_configs.sh /usr/local/bin/initial_configs.sh
RUN chmod +x /usr/local/bin/initial_configs.sh

ENTRYPOINT ["/usr/local/bin/initial_configs.sh"]
