# Image for the usage viewer service, run as an external JupyterHub service.

# The package version comes from git (through hatch-vcs),
# so build the wheel in a separate stage that has access to .git.
FROM python:3.14-slim-trixie AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src
RUN pip install --no-cache-dir build \
 && python -m build --wheel --outdir /dist


FROM python:3.14-slim-trixie

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
 && rm /tmp/*.whl

ENV PYTHONUNBUFFERED=1
USER 65534
EXPOSE 9000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "jupyterhub_usage_quotas.services.usage_viewer"]
