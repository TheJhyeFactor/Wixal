# Optional execution image. Build explicitly; Wixal never pulls/builds it during a run.
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 nmap nftables util-linux ca-certificates && rm -rf /var/lib/apt/lists/*
COPY entrypoint.py /opt/wixal/entrypoint.py
ENTRYPOINT ["python3", "-I", "/opt/wixal/entrypoint.py"]
