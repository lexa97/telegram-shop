FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System toolchain and services. Python 3.11 (the version the project pins) comes
# from the deadsnakes PPA; PostgreSQL 16 and Redis provide the datastores the bot
# and admin panel talk to. These are slow, stable dependencies, so they live in
# the image rather than the per-repo install step.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl git gnupg \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev \
        postgresql postgresql-contrib \
        redis-server \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pre-create a virtualenv owned by the unprivileged agent user. Project
# dependencies are installed into it by the repo-managed install step, which can
# see the checked-out requirements.txt. Putting the venv on PATH means python,
# pip, pytest and alembic resolve to it in every shell without activation.
RUN python3.11 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && chown -R ubuntu:ubuntu /opt/venv

ENV PATH="/opt/venv/bin:/usr/lib/postgresql/16/bin:${PATH}"

USER ubuntu
