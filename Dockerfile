FROM archlinux:base AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN sed -i '1iServer = https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch' /etc/pacman.d/mirrorlist \
    && pacman -Syu --noconfirm --needed python uv \
    && pacman -Scc --noconfirm

WORKDIR /app

# Install locked production dependencies in a separate layer so source changes do
# not invalidate the dependency cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM archlinux:base AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN sed -i '1iServer = https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch' /etc/pacman.d/mirrorlist \
    && pacman -Syu --noconfirm --needed \
        chromium \
        noto-fonts-cjk \
        python \
        ripgrep \
    && pacman -Scc --noconfirm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY agibot ./agibot
COPY bot.py ./bot.py

EXPOSE 8080

CMD ["python", "bot.py"]
