FROM python:3.12

# hadolint ignore=DL3008,DL3015,DL3009
RUN apt-get update && apt-get install -y \
    curl \
    wget
# Deliberately not removing the lists because the models
# don't seem to understand `apt-get update`.

RUN --mount=type=bind,source=main.c,target=/main.c \
    gcc -o /main /main.c

RUN --mount=type=bind,source=pyproject.toml,target=/pyproject.toml \
    pip3 install --no-cache-dir poetry==1.8.2 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

COPY ./immutable /app/immutable

ENV PYTHONPATH=/app
ENV PS1="\$? \\u@\\h:\\w \\$ "

ENV POCKET_ASI_PYTHON=/usr/local/bin/python
ENV POCKET_ASI_ROOT=/app/immutable
ENV POCKET_ASI_MODULE=immutable
ENV POCKET_ASI_LOADER=loader.py

WORKDIR /app

CMD ["/main"]
