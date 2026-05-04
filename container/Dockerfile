FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    opencv-python-headless==4.9.0.80 \
    scipy==1.12.0 \
    numpy==1.26.4 \
    boto3==1.34.0

COPY rppg_processor.py .

CMD ["python", "rppg_processor.py"]
