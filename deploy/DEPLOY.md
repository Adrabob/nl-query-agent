# Phase 4 — Deploy Runbook (OCI Compute VM)

Goal: the app reachable at `http://<PUBLIC_IP>:8000/` with `/health` returning
`{"status":"ok"}`. One FastAPI process serves both the API and the static UI.

**Architecture chosen:** single OCI Compute VM (Oracle Linux 9, default user `opc`),
uvicorn on port 8000, systemd-managed, instance-principal auth for OCI GenAI.
No nginx, no containers — fewest moving parts.

> ⏱️ If smooth: ~45 min. Do the IAM step (3) carefully — it is the #1 silent failure.

---

## 0. Before you start — values you'll need (all non-secret, from CLAUDE.md §6)
- Region: `uk-london-1`
- Compartment / tenancy OCID:
  `ocid1.tenancy.oc1..aaaaaaaazfq2ozmyhggult7w6klzhev3s6itnauhxdbdgazelea6hv3rtodq`
- Secrets (DB password, wallet, full .env) are **copied to the VM by hand** (scp),
  never committed. Have the local `.env` and `wallet/` folder ready.

---

## 1. Create the VM (OCI Console)
1. Compute → Instances → **Create instance**.
2. Name: `nlquery-vm`.
3. Image & shape: **Oracle Linux 9** (default), shape **VM.Standard.E3.Flex**, 1 OCPU /
   8 GB (cheap, comfortable; 1 GB Micro risks OOM during `uv sync`). E4.Flex needs a
   PAYG upgrade on Free Trial — E3.Flex is the available equivalent.
4. Networking: a VCN with a **public subnet**; **Assign a public IPv4 address = Yes**.
5. SSH keys: paste your public key (`~/.ssh/id_ed25519.pub`).
6. Create. Wait for **Running**, note the **Public IP** → this is `<PUBLIC_IP>`.

*Verify:* `ssh opc@<PUBLIC_IP>` connects (Oracle Linux default user is `opc`).

---

## 2. Open port 8000 (BOTH layers — this is a classic gotcha)

### 2a. Security List (OCI virtual firewall)
Networking → your VCN → the public subnet's **Security List** → **Add Ingress Rule**:
- Source CIDR: `0.0.0.0/0`
- IP Protocol: TCP, Destination port range: `8000`
- (Port 22 ingress already exists by default.)

### 2b. OS firewall (Oracle Linux runs firewalld, which blocks non-SSH ports)
On the VM:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```
> If you ever can't reach the port, 90% of the time it's one of these two layers.

---

## 3. IAM — instance principal for OCI GenAI (MANDATORY, do not skip)

`backend/rag.py` uses instance principal on the VM. Without this, the GenAI client
constructs but **every `/chat` call fails** (the router classifier needs it too).

1. Identity → **Domains** → default domain → **Dynamic groups** → **Create**:
   - Name: `nlquery-compute-dg`
   - Rule: `ALL {instance.compartment.id = 'ocid1.tenancy.oc1..aaaaaaaazfq2ozmyhggult7w6klzhev3s6itnauhxdbdgazelea6hv3rtodq'}`
2. Identity → **Policies** → **Create policy** (in the root compartment):
   - Name: `nlquery-compute-genai`
   - Statement: `Allow dynamic-group nlquery-compute-dg to use generative-ai-family in tenancy`

*(If your tenancy uses the legacy non-domain IAM, the dynamic group lives under
Identity → Dynamic Groups directly — same rule and policy.)*

---

## 4. Install runtime + code on the VM
SSH in (`ssh opc@<PUBLIC_IP>`), then:
```bash
sudo dnf install -y git
curl -LsSf https://astral.sh/uv/install.sh | sh        # installs uv to ~/.local/bin
source ~/.bashrc

# Clone from your GitHub repo (recommended for easy `git pull` updates).
git clone https://github.com/Adrabob/nl-query-agent.git ~/Hackathon
cd ~/Hackathon

uv sync                                                 # uv fetches Python 3.11+ and deps
```

### 4a. Copy the secrets the repo does NOT contain (run from your LAPTOP)
```powershell
scp -r "C:\Users\Arda Kaya\Desktop\Hackathon\wallet" opc@<PUBLIC_IP>:~/Hackathon/wallet
scp     "C:\Users\Arda Kaya\Desktop\Hackathon\.env"   opc@<PUBLIC_IP>:~/Hackathon/.env
```

### 4b. Fix paths inside the VM's `.env`
Edit `~/Hackathon/.env` on the VM so `WALLET_DIR` is the absolute VM path:
```
WALLET_DIR=/home/opc/Hackathon/wallet
```
(Other values — ADB_*, OCI_* — stay as they are in your local .env.)

---

## 5. Run it as a service
```bash
sudo cp ~/Hackathon/deploy/nlquery.service /etc/systemd/system/nlquery.service
sudo systemctl daemon-reload
sudo systemctl enable --now nlquery
systemctl status nlquery            # should be active (running)
journalctl -u nlquery -f            # live logs; Ctrl+C to stop tailing
```

---

## 6. Verify end-to-end
On the VM:
```bash
curl -s localhost:8000/health        # {"status":"ok"}
```
From your laptop / browser:
```
http://<PUBLIC_IP>:8000/             # the Sales Buddy UI loads
http://<PUBLIC_IP>:8000/health       # {"status":"ok"}
```
Then in the UI ask a SQL question and a docs question. If docs/SQL both answer,
instance principal (step 3) is working. **Smoke test the whole set from your laptop:**
```powershell
uv run python -m scripts.baseline_chat after   # point BASE_URL at the public IP first
```
(Temporarily set `BASE_URL = "http://<PUBLIC_IP>:8000"` in scripts/baseline_chat.py.)

Record the URL in CLAUDE.md §6 "Deployed app public URL".

---

## 7. Updating after deploy (easy)
- **Frontend only** (index.html / index.css / images): FastAPI serves them from disk,
  so no restart needed.
  ```bash
  cd ~/Hackathon && git pull        # (or scp the changed file)
  ```
  Then hard-refresh the browser (Ctrl+F5).
- **Backend** (.py): restart the service.
  ```bash
  cd ~/Hackathon && git pull && sudo systemctl restart nlquery
  ```

---

## 8. Troubleshooting
- **Can't reach :8000** → re-check BOTH step 2a (Security List) and 2b (iptables).
- **`/chat` returns DOCS_FAILED / QUERY_FAILED on the VM but worked locally** →
  instance principal not authorized. Re-check step 3 (dynamic group rule + policy);
  IAM can take a minute to propagate. `journalctl -u nlquery -e` shows the real error.
- **DB connection errors** → `WALLET_DIR` wrong in the VM `.env`, or wallet not copied.
- **`uv: command not found` in systemd** → fix the `ExecStart` path in nlquery.service
  to match `which uv` on the VM.
- **Port 80 instead of 8000** → optional; would need nginx or running uvicorn as root.
  Not worth the risk before submission; `:8000` is fine for the demo.
