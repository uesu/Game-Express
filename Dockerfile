# Game-Express — bot / 24-7 loop image (GitHub Actions does NOT need this).
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt requirements-bot.txt ./
RUN pip install --no-cache-dir -r requirements-bot.txt
COPY gamexpress ./gamexpress
COPY config ./config
COPY state ./state
# Mount a volume on /app/state so dedup survives restarts/redeploys.
VOLUME ["/app/state"]
# "bot" = slash commands + monitor loop (needs DISCORD_BOT_TOKEN)
# "loop" = monitor loop only (webhooks, no bot token)
CMD ["python", "-m", "gamexpress", "bot"]
