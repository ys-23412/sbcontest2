# Use a light python image para build
ARG PYTHON_VERSION=3.10.12
FROM python:${PYTHON_VERSION}-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-cache-dir -r requirements.txt

# Instala dependencias del sistema necesarias para compilar y ejecutar
RUN apt-get update && apt-get install -y wget xvfb libgtk-3-0 libx11-xcb1 libasound2 \
    && apt-get clean

# Copia el código fuente
COPY . .

# Compila todo el código Python a bytecode (.pyc)
RUN python -m compileall -b .

# Elimina todos los archivos fuente .py (excepto requirements.txt y recursos necesarios)
RUN find . -type f -name "*.py" ! -name "requirements.txt" -delete

# --- Imagen final ---
FROM python:${PYTHON_VERSION}-slim as final
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=builder /app/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-cache-dir -r requirements.txt

# Instala solo las dependencias del sistema necesarias para ejecutar
RUN apt-get update && apt-get install -y wget xvfb libgtk-3-0 libx11-xcb1 libasound2 \
    && apt-get clean

RUN pip install pydoll-python
RUN pip install -U camoufox[geoip]
RUN pip install requests
RUN pip install camoufox-captcha
RUN python -m camoufox fetch

# Copy your Python requirements file and install them
# This leverages Docker's build cache: if requirements.txt doesn't change,
# this layer won't be rebuilt.
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
# This includes scraper.py, any other scripts, and your examples/ directory
COPY . .

# Create directories for output (screenshots and videos)
RUN mkdir -p screenshots video_recordings
CMD ["python", "handle_tenders.py"]

# If you want to expose a port for debugging or other purposes (unlikely for this specific use case)
# EXPOSE 8080