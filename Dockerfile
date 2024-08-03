FROM python:3.9-slim

WORKDIR /app

# Install ffmpeg, git, and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install git+https://github.com/ytdl-org/youtube-dl.git@master#egg=youtube_dl

COPY . /app

EXPOSE 80

CMD ["python", "main.py"]
