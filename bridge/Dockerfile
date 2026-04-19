FROM python:3.10-slim

# 그래프 생성을 위한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    libpng-dev libjpeg-dev freetype2-doc \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 라이브러리 설치
RUN pip install fastapi uvicorn httpx pandas matplotlib docker

COPY *.py .

CMD ["python", "main.py"]
