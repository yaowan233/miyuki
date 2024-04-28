FROM python:3.11-slim

WORKDIR /app

RUN apt update && apt install -y libzbar0 locales locales-all fonts-noto ffmpeg

RUN apt-get install -y libnss3-dev libxss1 libasound2 libxrandr2\
  libatk1.0-0 libgtk-3-0 libgbm-dev libxshmfence1

ENV TZ Asia/Shanghai
ENV PYTHONPATH=/app
ENV MAX_WORKERS 1


RUN pip install --no-cache-dir pdm
COPY . /app/
RUN pdm install
RUN pdm run playwright install chromium && pdm run playwright install-deps
RUN pdm run nb orm upgrade

CMD ["pdm", "run", "nb", "run"]
