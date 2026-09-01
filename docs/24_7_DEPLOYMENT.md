# 24/7 Deployment

## Host
Use a continuously powered Linux server.

Starter:
- 8+ vCPU
- 32 GB RAM
- NVMe SSD
- stable wired network
- static outbound IP where provider allowlists are used

For concurrent Kronos-base inference across many active instruments, use an NVIDIA GPU and scale
horizontally before inference queues can violate the 6-second SLA. 16–24 GB VRAM is a practical
starting range, not a universal requirement.

## Prerequisites
- Docker Engine + Compose
- NTP/chrony clock sync
- firewall
- private Postgres/Redis
- automated backups
- production secret manager
- outbound TLS access to providers

## Deploy

```bash
make bootstrap
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,marketdata]"
make genesis
make build
make start
make health
sudo bash scripts/install_systemd.sh
```

Docker uses `restart: unless-stopped`; systemd restores the stack after reboot.

## Six-second SLA
- <3s healthy
- 3–5s degraded
- 5–6s critical
- >6s breach

On stale critical state:
- forbid new risk
- freeze affected new orders
- permit risk reduction when sufficiently informed
- reconnect/replay data
- alert owner only if automatic recovery fails

KCOS runs 24/7 even when specific venues are closed; research, reconciliation, learning and memory
maintenance continue.

Provider MFA/KYC/mandatory authorization cannot be bypassed. Those are exception events.
