FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/titan
COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt \
    && groupadd --system titan && useradd --system --gid titan titan \
    && mkdir -p /srv/titan/data && chown -R titan:titan /srv/titan
COPY --chown=titan:titan app ./app
COPY --chown=titan:titan migrations ./migrations
COPY --chown=titan:titan alembic.ini ./
USER titan
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
