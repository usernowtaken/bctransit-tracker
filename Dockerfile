FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py fleet_identity.py gps_history.py vehicle_activity.py service_alerts.py ./
COPY web ./web
RUN useradd --system --create-home radar && mkdir /app/cache && chown -R radar:radar /app/cache
USER radar
EXPOSE 8765
CMD ["python", "app.py", "--host", "0.0.0.0", "--no-browser"]
