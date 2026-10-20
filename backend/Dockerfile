FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml .
COPY constraints.txt .
COPY app app
RUN pip install --no-cache-dir -c constraints.txt .
COPY alembic.ini .
COPY alembic alembic
RUN useradd --create-home app && chown -R app:app /srv
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
