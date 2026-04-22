# Falcon University Admission Bot

An AI-powered admission pre-assessment system for Falcon University. Students complete an automated interview via a chat interface; admins can review applications, manage knowledge base documents, and view transcripts through a dashboard.

---

## Architecture

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 (App Router, React, Tailwind CSS) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 15 |
| LLM Gateway | LiteLLM (OpenAI-compatible proxy) |
| Embeddings | Ollama (local embedding model) |
| Reverse Proxy | Nginx |
| Deployment | AWS CDK + EC2 (`c7i-flex.large`) |

All services run as Docker containers on a single EC2 instance connected via a named bridge network (`falcon`).

---

## Live Instance

> **Public IP:** `18.118.121.228`

| Route | Purpose | Access |
|-------|---------|--------|
| `http://18.118.121.228/` | **Student Interview** — start the admission pre-assessment | Public |
| `http://18.118.121.228/login` | **Admin Login** — sign in to the admin dashboard | Protected |
| `http://18.118.121.228/admin/applicants` | **Admin Dashboard** — review applicants & transcripts | Requires login |
| `http://18.118.121.228/admin/knowledge-bases` | **Knowledge Base** — upload/manage PDF documents | Requires login |

### Admin Credentials
- **Username:** `admin`
- **Password:** `admin123`

---

## Local Development (Podman / Docker)

### Prerequisites
- Podman or Docker with Compose plugin
- Git
- An OpenAI API key

### 1. Clone the repository

```bash
git clone https://github.com/bhanotr/falcon.git
cd falcon
```

### 2. Create environment file

```bash
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-secret-key
EOF
```

### 3. Start all services

```bash
docker compose up -d --build
```

### 4. Access locally

- Frontend: http://localhost
- Backend API: http://localhost/api/health

---

## AWS Deployment (CDK)

### Prerequisites
- AWS CLI configured with credentials
- Python 3.9+
- Node.js 20+ (for CDK CLI)
- AWS CDK bootstrapped in your target region

### 1. Bootstrap CDK (one-time per region)

```bash
cd cdk
npx cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-2
```

### 2. Deploy the stack

```bash
npx cdk deploy -c openai_key="sk-your-key-here"
```

> **Note:** Do **not** commit your OpenAI API key to git. Pass it via the `-c` CLI flag only.

### 3. Retrieve the instance IP

After deployment completes, CDK outputs the public IP:

```
FalconStack.InstancePublicIp = 18.118.121.228
```

### 4. Wait for bootstrap

The EC2 instance runs a user-data script that installs Docker, clones the repo, and starts containers. This takes **3–5 minutes** after the CloudFormation stack shows `CREATE_COMPLETE`.

### Tear down

```bash
npx cdk destroy --force
```

This terminates the EC2 instance, security group, IAM role, and all associated resources.

---

## Project Structure

```
.
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py          # API routes & interview logic
│   │   ├── knowledge_base.py# Document ingestion & RAG
│   │   ├── database.py      # SQLAlchemy models & session
│   │   └── schemas.py       # Pydantic models
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js 15 application
│   ├── src/
│   │   ├── app/             # App router pages
│   │   ├── components/      # Reusable UI components
│   │   └── lib/api.ts       # API client helper
│   ├── Dockerfile
│   └── package.json
├── llm-gateway/             # LiteLLM proxy configuration
├── ollama/                  # Ollama embedding service
├── nginx/
│   └── nginx.conf           # Reverse proxy config
├── docker-compose.yml       # Local / EC2 orchestration
├── cdk/                     # AWS CDK infrastructure
│   ├── app.py               # CDK app entry point
│   ├── falcon_stack/
│   │   └── falcon_stack.py  # EC2, SG, IAM, user-data
│   └── requirements.txt
└── README.md
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | *(required)* |
| `SECRET_KEY` | JWT / session secret | `supersecretkey` |
| `ADMIN_USERNAME` | Admin dashboard username | `admin` |
| `ADMIN_PASSWORD` | Admin dashboard password | `admin123` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://falcon:falconpass@db:5432/falcon_university` |
| `LLM_GATEWAY_URL` | LiteLLM proxy base URL | `http://llm-gateway:11434/v1` |
| `OLLAMA_URL` | Ollama embeddings base URL | `http://ollama-embedding:11435` |

---

## Tech Stack Details

- **Next.js 15** with `output: "standalone"` for production-optimized Docker builds
- **FastAPI** with SQLAlchemy 2.0 and Pydantic v2
- **PostgreSQL 15** (Alpine image) with health checks
- **LiteLLM** proxying OpenAI-compatible requests
- **Ollama** running a local embedding model (`embeddinggemma:300m`)
- **Nginx** routing `/api/*` to the backend and all other traffic to the frontend
- **AWS CDK (Python)** defining VPC, Security Group, IAM Role, and EC2 instance with user-data bootstrap

---

## Product Thinking Assessment

### 1. Stakeholder Alignment

**Key stakeholders** for the admission pre-assessment tool include:

- **Prospective Students** — Need a low-friction, intuitive way to demonstrate eligibility without bureaucratic hurdles.
- **Admissions Office / Admin Staff** — Need accurate, reviewable data to make informed decisions efficiently.
- **University Leadership / Compliance** — Need fairness, transparency, and adherence to institutional policies and legal standards.
- **IT / DevOps** — Need a maintainable, secure, and cost-effective deployment model.

To ensure their needs are reflected in the product roadmap, I would:
- Run **monthly stakeholder syncs** with admissions staff to identify workflow pain points (e.g., bulk review, transcript search).
- Conduct **usability testing** with a small cohort of prospective students before each major release.
- Maintain a **public changelog** and internal RFC process so IT can review security and infrastructure implications early.
- Prioritize the backlog using a **RICE score** (Reach, Impact, Confidence, Effort) weighted toward student accessibility and admin efficiency.

### 2. Success Metrics

| Metric | Why It Matters | Target |
|--------|----------------|--------|
| **Interview Completion Rate** | Measures whether the chat interface is intuitive enough for students to finish. A low rate signals UX friction. | > 85% |
| **Admin Review Time per Applicant** | Measures operational efficiency. If the AI successfully surfaces key insights, reviewers spend less time reading raw transcripts. | < 3 minutes |
| **Qualitative Feedback Score** | Post-interview NPS or CSAT from students and a weekly Likert-scale survey from admins captures sentiment that raw data misses. | > 4.0 / 5 |

### 3. Risk Awareness

**Major Risk: Algorithmic Bias in Eligibility Screening**

AI models can inadvertently favor or disfavor candidates based on linguistic style, cultural references, or socioeconomic cues embedded in their responses. In an admissions context, this is not just a product risk — it is a legal and reputational liability.

**Mitigation strategies:**
- **Human-in-the-loop review:** The AI acts as a *pre-assessment assistant* that structures and summarizes data; final eligibility decisions are always made by human reviewers.
- **Bias auditing:** Periodically run synthetic applicant profiles through the system to detect disparate outcomes across demographics.
- **Transparency & consent:** Clearly disclose to applicants that an AI is assisting the process, and provide an alternative pathway (e.g., traditional written application) upon request.
- **Grounded outputs:** Use retrieval-augmented generation (RAG) with a controlled knowledge base so the bot does not hallucinate eligibility criteria.

---

## License

MIT
