# Stage 1: ephemeris data (self-contained build, no external registry dependency)
#
# Rationale:
# Railway builds have repeatedly failed when pulling a remote base image from GHCR.
# This stage downloads and verifies Swiss Ephemeris files during build so deployments
# do not depend on registry permissions/tag availability.
#
# IMPORTANT: upstream URL is pinned to a specific commit SHA of aloistr/swisseph, NOT
# the mutable `master` branch. Pinning to `master` caused repeated build failures every
# time the upstream maintainer refreshed ephemeris binaries. To update:
#   1. Pick the target commit SHA from https://github.com/aloistr/swisseph/commits/master
#   2. Bump EPHE_COMMIT below to that SHA.
#   3. Re-verify all 4 SHA256 hashes against that commit via:
#        for f in sepl_18.se1 semo_18.se1 seas_18.se1 seplm06.se1; do
#          curl -fsSL "https://raw.githubusercontent.com/aloistr/swisseph/<SHA>/ephe/$f" | sha256sum
#        done
#   4. Replace the 4 hash lines at the bottom of the RUN block.
FROM debian:bookworm-slim AS ephe

ARG EPHE_COMMIT=2f18c14c37ecf96264e87b2b6ed67b2028ae0c96

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/swisseph && \
    base="https://raw.githubusercontent.com/aloistr/swisseph/${EPHE_COMMIT}/ephe" && \
    echo "Pinned upstream commit: ${EPHE_COMMIT}" && \
    for f in sepl_18.se1 semo_18.se1 seas_18.se1 seplm06.se1; do \
        echo "Downloading $f from pinned commit..." && \
        curl -fL --retry 5 --retry-delay 3 \
             -o /usr/local/share/swisseph/$f $base/$f && \
        echo "  -> $(wc -c < /usr/local/share/swisseph/$f) bytes"; \
        if od -A n -t x1 -N 1 /usr/local/share/swisseph/$f | grep -qi "^ *3c"; then \
            echo "ERROR: $f looks like HTML, not binary ephemeris data" && exit 1; \
        fi; \
    done && \
    echo "b8e657c1f5a9c51821ef973baf233a3c07137101e35b95e00ac0e9eeea7fbeb8  /usr/local/share/swisseph/sepl_18.se1" | sha256sum -c - && \
    echo "7034c7825a0fef2f660d99161aa8e60429adfa315d269ac68042ef5a5e6319bf  /usr/local/share/swisseph/semo_18.se1" | sha256sum -c - && \
    echo "6559b0fc637eaed42ae747187cfd1426540d12b08114603bc39fd13f3bf80c83  /usr/local/share/swisseph/seas_18.se1" | sha256sum -c - && \
    echo "bd6c47f96abf2876a825500a3b09594b9d7887f52e67389d4ff25e25f9d37497  /usr/local/share/swisseph/seplm06.se1" | sha256sum -c - && \
    find /usr/local/share/swisseph -type d -exec chmod 755 {} \; && \
    find /usr/local/share/swisseph -type f -exec chmod 644 {} \; && \
    echo "All ephemeris files verified against pinned commit ${EPHE_COMMIT}."

# Stage 2: application
FROM python:3.14-slim

WORKDIR /app

# Copy ephemeris files from builder stage (already verified binary)
COPY --from=ephe /usr/local/share/swisseph /usr/local/share/swisseph

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set Python environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV SE_EPHE_PATH=/usr/local/share/swisseph

# Install Python dependencies from pinned lockfile (deterministic builds)
COPY requirements.lock .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.lock

# Copy application code LAST (invalidates on every code change)
COPY pyproject.toml .
COPY bazi_engine/ ./bazi_engine/
COPY spec/ ./spec/

# Install package (non-editable so it uses the copied files directly)
RUN pip install --no-deps .

# Expose port
EXPOSE 8080

COPY start.py .

# Start the application using the dedicated startup script.
CMD ["python", "start.py"]
