# Stage 1: Export a version-independent locked dependency list so bumping
# project.version in pyproject.toml does not invalidate the runtime venv cache.
FROM m.daocloud.io/docker.io/library/archlinux:base AS lock-exporter

RUN sed -i '1iServer = https://mirror.nju.edu.cn/archlinux/$repo/os/$arch' /etc/pacman.d/mirrorlist \
    && pacman -Syu --noconfirm --needed uv \
    && pacman -Scc --noconfirm

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --no-header -o /requirements.lock \
    && chmod 0644 /requirements.lock \
    && touch -d @0 /requirements.lock

# Stage 2: Runtime image with cached virtualenv installation.
FROM m.daocloud.io/docker.io/library/archlinux:base AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_DEFAULT_INDEX=https://mirror.nju.edu.cn/pypi/web/simple

RUN sed -i '1iServer = https://mirror.nju.edu.cn/archlinux/$repo/os/$arch' /etc/pacman.d/mirrorlist \
    && stdbuf -oL -eL pacman -Syu --noconfirm --needed \
        chromium \
        noto-fonts-cjk \
        python \
        ripgrep \
        uv \
    && pacman -Scc --noconfirm

WORKDIR /app

COPY --from=lock-exporter /requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv \
    && uv pip sync --python /app/.venv/bin/python --require-hashes requirements.lock

COPY pyproject.toml ./
COPY agibot ./agibot
COPY bot.py ./bot.py

EXPOSE 8080

CMD ["python", "bot.py"]
