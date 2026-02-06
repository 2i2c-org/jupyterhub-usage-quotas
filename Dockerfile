# build

FROM python:3.14-slim-bookworm AS builder

RUN apt-get update && apt-get install -y pipx git
RUN pipx install hatch && rm -rf /root/.cache/
ENV PATH="${PATH}:/root/.local/bin"
RUN mkdir /build
COPY . /build
WORKDIR /build
RUN rm -rf dist && hatch build

# run

FROM python:3.14-slim-bookworm
RUN apt-get update && apt-get install -y tini curl htop git man-db zip file tree vim
RUN pip install --upgrade pip
RUN mkdir /opt/jupyterhub_usage_quotas
WORKDIR /opt/jupyterhub_usage_quotas
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp
COPY . /opt/jupyterhub_usage_quotas
WORKDIR /opt/jupyterhub_usage_quotas/src/jupyterhub_usage_quotas
EXPOSE 8080
USER 65534
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["fastapi", "run", "--port", "8080", "--host", "0.0.0.0"]
