FROM python:3.9
COPY memes.txt .
COPY tarantool.txt .
COPY arial.ttf .
COPY requirements.txt .
RUN pip install -r /requirements.txt
COPY app.py .
CMD ["python", "app.py"]