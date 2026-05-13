# AttackGPT

**Just-in-Time malware generation framework using LLM-driven adaptive payloads.**

AttackGPT demonstrates autonomous C2 frameworks that generate attack payloads on-demand using Large Language Models, adapting to each victim's environment in real-time. This is not made to be an operational C2 framework.

---

## ⚠️ Legal Disclaimer

**FOR AUTHORIZED SECURITY TESTING AND RESEARCH ONLY.**

Unauthorized access to computer systems is illegal. Users are solely responsible for obtaining proper authorization and complying with all applicable laws. Misuse may result in criminal prosecution.

Intended use: Authorized penetration testing, red team exercises, security research in controlled environments.

---

## 🚀 Quick Start

### Prerequisites
- Windows OS (C2 server requires PowerShell)
- Python 3.8+
- API keys: OpenAI and/or Anthropic (or use Ollama for local models)

### Installation

**1. Install dependencies**
```powershell
pip install -r requirements.txt
```

**2. Set API keys**
```powershell
#Set the following environment variables for the LLM API keys
$env:OPENAI_API_KEY = 'your-key-here'
$env:ANTHROPIC_API_KEY = 'your-key-here'
```

**3. (Optional) Install Ollama for open-source models**
```powershell
# Download: https://ollama.ai/download
ollama serve
ollama pull qwen2.5-coder:32b
```

**4. Configure C2 address in stub.py**
```python
C2_SERVER = "http://YOUR_SERVER_IP:8888"
```

**5. Configure attack campaign in tactics_config.py**
```python
"discovery": {
    "implemented": True,        # Enable this tactic
    "model": "gpt-5",           # Choose LLM model
    "commercial": True,         # True = API, False = Ollama
    "techniques": [
        {
            "name": "Browser Data Discovery",
            "mitre_id": "T1217",
            "persona": "You are a System Administrator...",
            "objective": "Task: Find Chrome database files..."
        }
    ]
}
```

See `tactics_config.py` for detailed field documentation.

---

## 🎯 Running AttackGPT

**Start C2 server:**
```powershell
cd agentic_attackgpt
python server.py
```

**Deploy agent (authorized systems only):**
```powershell
python stub.py
```

The agent polls C2 every 5 seconds, executes generated payloads, and returns results.

---

## 🏗️ Architecture

| Component | Description |
|-----------|-------------|
| **server.py** | Flask C2 server, manages the agent and commands |
| **stub.py** | Lightweight agent deployed on targets |
| **orchestrator_agentic.py** | Campaign manager, sequences tactics |
| **engine_agentic.py** | LLM integration with self-healing loop |
| **tactics_config.py** | User-configurable MITRE ATT&CK tactics |
| **sandbox.py** | PowerShell sandbox for payload validation |

---

## 🔑 Key Features

**Split-Brain Architecture**
- Commercial LLMs (GPT, Claude) for techniques framed as legitimate tasks
- Open-source LLMs (Qwen, Llama) for explicitly malicious operations

**Self-Healing Validation Loop**
- Generated code validated in local PowerShell sandbox
- Failures fed back to LLM with error context
- Auto-regenerates corrected code (up to 5 attempts)

**Context-Aware Generation**
- Payloads adapt to victim OS, privileges, installed software
- Previous technique results feed into subsequent prompts
- No hardcoded templates—fully dynamic

**Modular Prompting**
- Attack chains decomposed into isolated techniques
- LLM never sees full malicious intent
- Bypasses commercial LLM safety guardrails

**Modular Execution**
- Can possibly bypass EDR detection since each malicious code is executed in different PowerShell instance.

---

## 📋 Configuration Fields

Each technique in `tactics_config.py`:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Technique name |
| `mitre_id` | Yes | MITRE ATT&CK ID (e.g., T1547.001) |
| `persona` | Yes | Role-play framing for LLM |
| `objective` | Yes | Detailed task instructions |
| `skip_verification` | No | Skip sandbox (default: False) |
| `required` | No | Abort if fails (default: True) |

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Acknowledgments

This research explores LLM capabilities in cybersecurity, demonstrating both offensive potential and the need for defensive awareness.

**Use responsibly and legally.**
