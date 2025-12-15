FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install dependencies including DOSBox-X from Debian Trixie repos
RUN apt-get update && apt-get install -y \
    xvfb \
    dosbox-x \
    ffmpeg \
    xdotool \
    python3 \
    python3-pip \
    python3-flask \
    supervisor \
    openbox \
    && rm -rf /var/lib/apt/lists/*

# Configure openbox to maximize all windows automatically
RUN mkdir -p /root/.config/openbox
COPY openbox-rc.xml /root/.config/openbox/rc.xml

# Flask installed via python3-flask package above

# Copy configuration files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY dosbox-x-config/ /dosbox-x-config/
COPY app/ /app/

# Create directory for game files (will be mounted as volume)
RUN mkdir -p /games

EXPOSE 8081

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
