FROM python:3.11
WORKDIR /app

RUN apt update && apt install -y ffmpeg

ENV TZ Asia/Shanghai
ENV PYTHONPATH=/app
ENV MAX_WORKERS 1


RUN curl -LsSf https://astral.sh/uv/install.sh | sh
COPY . /app/
ENV PATH="/root/.local/bin:$PATH"
RUN uv sync
RUN uv run nb orm upgrade

CMD ["uv", "run", "nb", "run"]
