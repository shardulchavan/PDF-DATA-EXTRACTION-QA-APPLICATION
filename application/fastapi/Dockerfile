FROM python:3.11.5

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .
COPY ../.env.example ./.env

EXPOSE 80

# Run app.py when the container launches
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]