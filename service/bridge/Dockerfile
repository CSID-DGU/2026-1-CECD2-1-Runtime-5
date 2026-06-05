FROM python:3.10-slim

# 파이썬 라이브러리 설치
RUN pip install fastapi uvicorn httpx pandas docker xgboost numpy

COPY *.py .

CMD ["python", "main.py"]
