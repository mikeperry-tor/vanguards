FROM dockurr/tor@sha256:c1637d01527fb78e8ba5132671e5607d7e267037756ee112fd33be4382822920

COPY requirements.txt /tmp/vanguards-requirements.txt
RUN python3 -m venv /opt/vanguards && \
    /opt/vanguards/bin/python -m pip install --no-cache-dir --require-hashes \
        -r /tmp/vanguards-requirements.txt

ENV PATH="/opt/vanguards/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1
WORKDIR /checkout
ENTRYPOINT ["/sbin/tini", "--", "python"]
HEALTHCHECK NONE
